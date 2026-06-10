from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import json
import os
import re
import shutil
import subprocess
import sys
from typing import Any, Callable


ENGINE_KOKORO = "kokoro"
ENGINE_PIPER = "piper"
DEFAULT_ENGINE = ENGINE_KOKORO
DEFAULT_PIPER_MODEL_SOURCE = "Trelis/piper-pt-br-faber-medium"
DEFAULT_MODEL_SOURCE = DEFAULT_PIPER_MODEL_SOURCE
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
    engine: str = DEFAULT_ENGINE
    model_source: str = DEFAULT_MODEL_SOURCE
    espeak_command: str = DEFAULT_ESPEAK_COMMAND
    espeak_voice: str = ""
    kokoro_voice: str = DEFAULT_KOKORO_VOICE
    kokoro_speed: float = 1.0
    noise_scale: float | None = None
    length_scale: float | None = None
    noise_w: float | None = None
    chunk_long_text: bool = True
    max_chunk_chars: int = DEFAULT_MAX_CHUNK_CHARS
    silence_ms: int = 180


@dataclass(frozen=True)
class GenerationResult:
    output_path: Path
    sample_rate: int
    chunk_count: int
    engine: str
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


def phonemes_to_ids(phonemes: list[str], phoneme_id_map: dict[str, list[int]]) -> list[int]:
    ids = [phoneme_id_map["^"][0], phoneme_id_map["_"][0]]
    for phoneme in phonemes:
        mapped = phoneme_id_map.get(phoneme)
        if mapped:
            ids.extend(mapped)
            ids.append(phoneme_id_map["_"][0])
    ids.append(phoneme_id_map["$"][0])
    return ids


def find_espeak_command(configured_command: str = "") -> str | None:
    commands = [
        configured_command.strip(),
        os.environ.get("PIPER_ESPEAK", "").strip(),
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


class LocalTTSEngine:
    def __init__(self) -> None:
        self._piper_runtime: dict[str, Any] | None = None
        self._piper_session: Any | None = None
        self._piper_config: dict[str, Any] | None = None
        self._loaded_piper_model_source: str | None = None
        self._kokoro_runtime: dict[str, Any] | None = None
        self._kokoro_pipeline: Any | None = None

    def generate(
        self,
        options: GenerationOptions,
        progress: ProgressCallback | None = None,
    ) -> GenerationResult:
        progress = progress or (lambda _message: None)
        text = options.text.strip()
        if not text:
            raise ValueError("Informe um texto para gerar audio.")

        engine = options.engine.strip().lower()
        if engine == ENGINE_KOKORO:
            return self._generate_kokoro(options, text, progress)
        if engine == ENGINE_PIPER:
            return self._generate_piper(options, text, progress)
        raise ValueError("Engine deve ser kokoro ou piper.")

    def _generate_piper(
        self,
        options: GenerationOptions,
        text: str,
        progress: ProgressCallback,
    ) -> GenerationResult:
        runtime = self._ensure_piper_runtime(progress)
        numpy = runtime["numpy"]
        soundfile = runtime["soundfile"]
        session, config = self._ensure_piper_model(options.model_source, runtime, progress)

        espeak_command = self._resolve_espeak_command(options.espeak_command)
        espeak_voice = options.espeak_voice.strip() or str(config["espeak"]["voice"])
        chunks = (
            split_text_for_generation(text, options.max_chunk_chars)
            if options.chunk_long_text
            else [text]
        )
        if not chunks:
            raise ValueError("Informe um texto para gerar audio.")

        noise_scale = _option_or_config(options.noise_scale, config, "noise_scale")
        length_scale = _option_or_config(options.length_scale, config, "length_scale")
        noise_w = _option_or_config(options.noise_w, config, "noise_w")
        sample_rate = int(config["audio"]["sample_rate"])
        phoneme_id_map = config["phoneme_id_map"]

        audio_chunks = []
        for chunk_index, chunk in enumerate(chunks, start=1):
            progress(f"Fonemizando trecho {chunk_index}/{len(chunks)} com {espeak_voice}...")
            phoneme_sentences = self._phonemize(chunk, espeak_command, espeak_voice)
            for sentence_index, phonemes in enumerate(phoneme_sentences, start=1):
                ids = phonemes_to_ids(phonemes, phoneme_id_map)
                if len(ids) < 3:
                    continue

                progress(
                    f"Gerando audio do trecho {chunk_index}/{len(chunks)} "
                    f"frase {sentence_index}/{len(phoneme_sentences)}..."
                )
                inputs = {
                    "input": numpy.array([ids], dtype=numpy.int64),
                    "input_lengths": numpy.array([len(ids)], dtype=numpy.int64),
                    "scales": numpy.array([noise_scale, length_scale, noise_w], dtype=numpy.float32),
                }
                if int(config.get("num_speakers", 1)) > 1:
                    inputs["sid"] = numpy.array([0], dtype=numpy.int64)

                audio = session.run(None, inputs)[0].squeeze().astype(numpy.float32)
                audio_chunks.append(audio)
                if options.silence_ms > 0:
                    silence_samples = int(sample_rate * (options.silence_ms / 1000))
                    audio_chunks.append(numpy.zeros(silence_samples, dtype=numpy.float32))

        if not audio_chunks:
            raise RuntimeError("O Piper nao retornou audio. Confira o texto e a instalacao do espeak-ng.")

        audio = numpy.concatenate(audio_chunks).astype(numpy.float32)
        output_path = options.output_path.expanduser().resolve()
        output_path.parent.mkdir(parents=True, exist_ok=True)

        progress(f"Salvando WAV em {output_path}...")
        soundfile.write(str(output_path), audio, sample_rate)

        return GenerationResult(
            output_path=output_path,
            sample_rate=sample_rate,
            chunk_count=len(chunks),
            engine=ENGINE_PIPER,
            model_source=options.model_source,
            voice_label=f"Piper {espeak_voice}",
        )

    def _generate_kokoro(
        self,
        options: GenerationOptions,
        text: str,
        progress: ProgressCallback,
    ) -> GenerationResult:
        runtime = self._ensure_kokoro_runtime(progress)
        numpy = runtime["numpy"]
        soundfile = runtime["soundfile"]
        pipeline = self._ensure_kokoro_pipeline(runtime, options.espeak_command, progress)

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
            progress(f"Gerando Kokoro trecho {chunk_index}/{len(chunks)} com voz {voice}...")
            generator = pipeline(chunk, voice=voice, speed=options.kokoro_speed)
            for sentence_index, (_gs, _ps, audio) in enumerate(generator, start=1):
                progress(
                    f"Processando audio Kokoro do trecho {chunk_index}/{len(chunks)} "
                    f"frase {sentence_index}..."
                )
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
            engine=ENGINE_KOKORO,
            model_source=KOKORO_REPO_ID,
            voice_label=f"{voice} - {KOKORO_VOICES[voice]}",
        )

    def _ensure_piper_runtime(self, progress: ProgressCallback) -> dict[str, Any]:
        if self._piper_runtime is not None:
            return self._piper_runtime

        try:
            import numpy
            import onnxruntime
            import soundfile
            from huggingface_hub import hf_hub_download
        except Exception as exc:  # pragma: no cover - depends on optional runtime deps
            raise RuntimeError(
                "Falha ao importar dependencias do Piper. "
                "Rode scripts/bootstrap para instalar onnxruntime, soundfile e huggingface_hub."
            ) from exc

        progress("Runtime Piper carregado: onnxruntime CPU + soundfile.")
        self._piper_runtime = {
            "numpy": numpy,
            "onnxruntime": onnxruntime,
            "soundfile": soundfile,
            "hf_hub_download": hf_hub_download,
        }
        return self._piper_runtime

    def _ensure_kokoro_runtime(self, progress: ProgressCallback) -> dict[str, Any]:
        if self._kokoro_runtime is not None:
            return self._kokoro_runtime

        try:
            import numpy
            import soundfile
            from kokoro import KPipeline
        except Exception as exc:  # pragma: no cover - depends on optional runtime deps
            raise RuntimeError(
                "Falha ao importar dependencias do Kokoro. "
                "Rode scripts/bootstrap para instalar kokoro, torch e soundfile."
            ) from exc

        progress("Runtime Kokoro carregado.")
        self._kokoro_runtime = {
            "numpy": numpy,
            "soundfile": soundfile,
            "KPipeline": KPipeline,
        }
        return self._kokoro_runtime

    def _ensure_piper_model(
        self,
        model_source: str,
        runtime: dict[str, Any],
        progress: ProgressCallback,
    ) -> tuple[Any, dict[str, Any]]:
        model_source = model_source.strip() or DEFAULT_MODEL_SOURCE
        if (
            self._piper_session is not None
            and self._piper_config is not None
            and self._loaded_piper_model_source == model_source
        ):
            return self._piper_session, self._piper_config

        hf_hub_download = runtime["hf_hub_download"]
        onnxruntime = runtime["onnxruntime"]

        if Path(model_source).expanduser().exists():
            model_path = Path(model_source).expanduser().resolve()
            if model_path.is_dir():
                onnx_path = model_path / "model.onnx"
                config_path = model_path / "model.onnx.json"
            else:
                onnx_path = model_path
                config_path = model_path.with_suffix(model_path.suffix + ".json")
        else:
            progress(f"Baixando/carregando modelo {model_source} do cache Hugging Face...")
            onnx_path = Path(hf_hub_download(model_source, "model.onnx"))
            config_path = Path(hf_hub_download(model_source, "model.onnx.json"))

        if not onnx_path.exists():
            raise FileNotFoundError(f"Modelo ONNX nao encontrado: {onnx_path}")
        if not config_path.exists():
            raise FileNotFoundError(f"Config do modelo nao encontrada: {config_path}")

        with config_path.open("r", encoding="utf-8") as config_file:
            config = json.load(config_file)

        progress(f"Carregando ONNX em CPU: {onnx_path}")
        session = onnxruntime.InferenceSession(str(onnx_path), providers=["CPUExecutionProvider"])

        self._piper_session = session
        self._piper_config = config
        self._loaded_piper_model_source = model_source
        return session, config

    def _ensure_kokoro_pipeline(
        self,
        runtime: dict[str, Any],
        espeak_command: str,
        progress: ProgressCallback,
    ) -> Any:
        if self._kokoro_pipeline is not None:
            return self._kokoro_pipeline

        resolved_espeak = self._resolve_espeak_command(espeak_command)
        _prepend_path_once(Path(resolved_espeak).parent)
        progress("Carregando Kokoro lang_code='p' para pt_BR...")
        self._kokoro_pipeline = runtime["KPipeline"](lang_code=KOKORO_LANG_CODE, repo_id=KOKORO_REPO_ID)
        return self._kokoro_pipeline

    def _phonemize(self, text: str, espeak_command: str, espeak_voice: str) -> list[list[str]]:
        completed = subprocess.run(
            [espeak_command, "-v", espeak_voice, "-q", "--ipa=2", "-x", text],
            capture_output=True,
            check=False,
            encoding="utf-8",
            errors="replace",
            text=True,
        )
        if completed.returncode != 0:
            raise RuntimeError(
                "Falha ao executar espeak-ng. "
                f"Comando: {espeak_command}; stderr: {completed.stderr.strip()}"
            )

        output = completed.stdout.strip()
        return [list(line.replace("_", " ")) for line in output.split("\n") if line.strip()]

    def _resolve_espeak_command(self, configured_command: str) -> str:
        resolved = find_espeak_command(configured_command)
        if resolved:
            return resolved
        raise FileNotFoundError(
            "Nao encontrei o executavel espeak-ng. Instale o espeak-ng e garanta que ele esteja no PATH, "
            "ou informe o caminho do executavel na app."
        )


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


def _option_or_config(option_value: float | None, config: dict[str, Any], key: str) -> float:
    if option_value is not None:
        return float(option_value)
    return float(config["inference"][key])


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


PiperTTSEngine = LocalTTSEngine
