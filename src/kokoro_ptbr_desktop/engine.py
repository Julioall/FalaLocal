from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import os
import re
import shutil
import sys
from typing import Any, Callable


KOKORO_REPO_ID = "hexgrad/Kokoro-82M"
KOKORO_SAMPLE_RATE = 24_000
KOKORO_LANG_CODE = "p"
KOKORO_VOICES = {
    "pf_dora": "Dora (feminina)",
    "pm_alex": "Alex (masculina)",
    "pm_santa": "Santa (masculina)",
}
DEFAULT_KOKORO_VOICE = "pf_dora"
DEFAULT_MAX_CHUNK_CHARS = 600
DEFAULT_ESPEAK_COMMAND = "espeak-ng"

ProgressCallback = Callable[[str], None]


@dataclass(frozen=True)
class GenerationOptions:
    text: str
    output_path: Path
    espeak_command: str = DEFAULT_ESPEAK_COMMAND
    kokoro_voice: str = DEFAULT_KOKORO_VOICE
    kokoro_speed: float = 1.0
    chunk_long_text: bool = True
    max_chunk_chars: int = DEFAULT_MAX_CHUNK_CHARS
    silence_ms: int = 180


@dataclass(frozen=True)
class GenerationResult:
    output_path: Path
    sample_rate: int
    chunk_count: int
    model_source: str
    voice_label: str


def split_text_for_generation(text: str, max_chars: int = DEFAULT_MAX_CHUNK_CHARS) -> list[str]:
    normalized = re.sub(r"[ \t]+", " ", text.replace("\r\n", "\n")).strip()
    if not normalized:
        return []
    if max_chars < 120:
        raise ValueError("max_chars must be at least 120")
    if len(normalized) <= max_chars:
        return [normalized]

    chunks: list[str] = []
    paragraphs = [part.strip() for part in re.split(r"\n\s*\n+", normalized) if part.strip()]
    for paragraph in paragraphs:
        sentences = [part.strip() for part in re.split(r"(?<=[.!?;:])\s+", paragraph) if part.strip()]
        if not sentences:
            sentences = [paragraph]

        current = ""
        for sentence in sentences:
            if len(sentence) > max_chars:
                if current:
                    chunks.append(current)
                    current = ""
                chunks.extend(_split_long_sentence(sentence, max_chars))
                continue

            candidate = f"{current} {sentence}".strip()
            if len(candidate) <= max_chars:
                current = candidate
            else:
                if current:
                    chunks.append(current)
                current = sentence

        if current:
            chunks.append(current)

    return chunks


def find_espeak_command(configured_command: str = "") -> str | None:
    commands = [
        configured_command.strip(),
        os.environ.get("TTS_ESPEAK", "").strip(),
        DEFAULT_ESPEAK_COMMAND,
        "espeak-ng.exe",
    ]
    for command in commands:
        if not command:
            continue
        command_path = Path(command).expanduser()
        if command_path.exists():
            return str(command_path.resolve())
        resolved = shutil.which(command)
        if resolved:
            return resolved

    for candidate in _common_windows_espeak_paths():
        if candidate.exists():
            return str(candidate.resolve())

    return None


class KokoroTTSEngine:
    def __init__(self) -> None:
        self._runtime: dict[str, Any] | None = None
        self._pipeline: Any | None = None

    def generate(
        self,
        options: GenerationOptions,
        progress: ProgressCallback | None = None,
    ) -> GenerationResult:
        progress = progress or (lambda _message: None)
        text = options.text.strip()
        if not text:
            raise ValueError("Informe um texto para gerar audio.")

        runtime = self._ensure_runtime(progress)
        numpy = runtime["numpy"]
        soundfile = runtime["soundfile"]
        pipeline = self._ensure_pipeline(runtime, options.espeak_command, progress)

        voice = options.kokoro_voice if options.kokoro_voice in KOKORO_VOICES else DEFAULT_KOKORO_VOICE
        chunks = (
            split_text_for_generation(text, options.max_chunk_chars)
            if options.chunk_long_text
            else [text]
        )
        if not chunks:
            raise ValueError("Informe um texto para gerar audio.")

        audio_chunks = []
        for chunk_index, chunk in enumerate(chunks, start=1):
            progress(f"Gerando trecho {chunk_index}/{len(chunks)} com voz {voice}...")
            generator = pipeline(chunk, voice=voice, speed=options.kokoro_speed)
            for sentence_index, (_gs, _ps, audio) in enumerate(generator, start=1):
                progress(f"Processando audio do trecho {chunk_index}/{len(chunks)} frase {sentence_index}...")
                audio_array = _audio_to_numpy(audio, numpy)
                if audio_array.size == 0:
                    continue
                audio_chunks.append(audio_array)
                if options.silence_ms > 0:
                    silence_samples = int(KOKORO_SAMPLE_RATE * (options.silence_ms / 1000))
                    audio_chunks.append(numpy.zeros(silence_samples, dtype=numpy.float32))

        if not audio_chunks:
            raise RuntimeError("O Kokoro nao retornou audio. Confira o texto e a instalacao do espeak-ng.")

        audio = numpy.concatenate(audio_chunks).astype(numpy.float32)
        output_path = options.output_path.expanduser().resolve()
        output_path.parent.mkdir(parents=True, exist_ok=True)

        progress(f"Salvando WAV em {output_path}...")
        soundfile.write(str(output_path), audio, KOKORO_SAMPLE_RATE)

        return GenerationResult(
            output_path=output_path,
            sample_rate=KOKORO_SAMPLE_RATE,
            chunk_count=len(chunks),
            model_source=KOKORO_REPO_ID,
            voice_label=f"{voice} - {KOKORO_VOICES[voice]}",
        )

    def _ensure_runtime(self, progress: ProgressCallback) -> dict[str, Any]:
        if self._runtime is not None:
            return self._runtime

        try:
            import numpy
            import soundfile
            from kokoro import KPipeline
        except Exception as exc:  # pragma: no cover - depends on optional runtime deps
            raise RuntimeError(
                "Falha ao importar dependencias do Kokoro. "
                "Rode scripts/bootstrap para instalar kokoro, torch, click e soundfile."
            ) from exc

        progress("Runtime Kokoro carregado.")
        self._runtime = {
            "numpy": numpy,
            "soundfile": soundfile,
            "KPipeline": KPipeline,
        }
        return self._runtime

    def _ensure_pipeline(
        self,
        runtime: dict[str, Any],
        espeak_command: str,
        progress: ProgressCallback,
    ) -> Any:
        if self._pipeline is not None:
            return self._pipeline

        resolved_espeak = self._resolve_espeak_command(espeak_command)
        _prepend_path_once(Path(resolved_espeak).parent)
        progress("Carregando Kokoro lang_code='p' para pt_BR...")
        self._pipeline = runtime["KPipeline"](lang_code=KOKORO_LANG_CODE, repo_id=KOKORO_REPO_ID)
        return self._pipeline

    def _resolve_espeak_command(self, configured_command: str) -> str:
        resolved = find_espeak_command(configured_command)
        if resolved:
            return resolved
        raise FileNotFoundError(
            "Nao encontrei o executavel espeak-ng. Instale o espeak-ng e garanta que ele esteja no PATH, "
            "ou informe o caminho do executavel na app."
        )


def _split_long_sentence(sentence: str, max_chars: int) -> list[str]:
    pieces: list[str] = []
    current = ""
    for word in sentence.split(" "):
        if len(word) > max_chars:
            if current:
                pieces.append(current)
                current = ""
            pieces.extend(word[index : index + max_chars] for index in range(0, len(word), max_chars))
            continue

        candidate = f"{current} {word}".strip()
        if len(candidate) <= max_chars:
            current = candidate
        else:
            if current:
                pieces.append(current)
            current = word

    if current:
        pieces.append(current)
    return pieces


def _common_windows_espeak_paths() -> list[Path]:
    if not sys.platform.startswith("win"):
        return []

    candidates: list[Path] = []
    for env_name in ("ProgramFiles", "ProgramFiles(x86)", "LOCALAPPDATA"):
        root = os.environ.get(env_name)
        if not root:
            continue
        root_path = Path(root)
        candidates.extend(
            [
                root_path / "eSpeak NG" / "espeak-ng.exe",
                root_path / "eSpeak-NG" / "espeak-ng.exe",
                root_path / "espeak-ng" / "espeak-ng.exe",
            ]
        )

    winget_root = Path(os.environ.get("LOCALAPPDATA", "")) / "Microsoft" / "WinGet" / "Packages"
    if winget_root.exists():
        candidates.extend(winget_root.glob("eSpeak-NG.eSpeak-NG_*/*/espeak-ng.exe"))
        candidates.extend(winget_root.glob("eSpeak-NG.eSpeak-NG_*/espeak-ng.exe"))

    return candidates


def _audio_to_numpy(audio: Any, numpy: Any) -> Any:
    if hasattr(audio, "detach"):
        audio = audio.detach()
    if hasattr(audio, "cpu"):
        audio = audio.cpu()
    if hasattr(audio, "numpy"):
        audio = audio.numpy()
    return numpy.asarray(audio, dtype=numpy.float32).squeeze().reshape(-1)


def _prepend_path_once(path: Path) -> None:
    path_text = str(path.resolve())
    current_paths = os.environ.get("PATH", "").split(os.pathsep)
    if path_text not in current_paths:
        os.environ["PATH"] = os.pathsep.join([path_text, *current_paths])


LocalTTSEngine = KokoroTTSEngine
