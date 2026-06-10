from __future__ import annotations

from pathlib import Path
import subprocess
import sys
import traceback

from PySide6.QtCore import QObject, QThread, Qt, Signal, Slot
from PySide6.QtGui import QCloseEvent
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QDoubleSpinBox,
    QFileDialog,
    QFormLayout,
    QFrame,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPlainTextEdit,
    QProgressBar,
    QPushButton,
    QSpinBox,
    QSplitter,
    QStyle,
    QVBoxLayout,
    QWidget,
)

from .engine import (
    DEFAULT_ESPEAK_COMMAND,
    DEFAULT_KOKORO_VOICE,
    DEFAULT_MAX_CHUNK_CHARS,
    GenerationOptions,
    KOKORO_REPO_ID,
    KOKORO_VOICES,
    KokoroTTSEngine,
    find_espeak_command,
)


class GenerationWorker(QObject):
    progress = Signal(str)
    finished = Signal(object)
    failed = Signal(str)

    def __init__(self, engine: KokoroTTSEngine, options: GenerationOptions) -> None:
        super().__init__()
        self._engine = engine
        self._options = options

    @Slot()
    def run(self) -> None:
        try:
            result = self._engine.generate(self._options, progress=self.progress.emit)
        except Exception:
            self.failed.emit("".join(traceback.format_exc()))
            return
        self.finished.emit(result)


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("Kokoro pt_BR Desktop Local")
        self.resize(1080, 700)

        self._engine = KokoroTTSEngine()
        self._thread: QThread | None = None
        self._worker: GenerationWorker | None = None
        self._last_output: Path | None = None

        self._build_ui()
        self._connect_signals()
        self._update_char_count()

    def closeEvent(self, event: QCloseEvent) -> None:
        if self._thread and self._thread.isRunning():
            QMessageBox.warning(
                self,
                "Geracao em andamento",
                "Aguarde a geracao terminar antes de fechar a app.",
            )
            event.ignore()
            return
        event.accept()

    def _build_ui(self) -> None:
        root = QWidget()
        root_layout = QVBoxLayout(root)
        root_layout.setContentsMargins(18, 18, 18, 18)
        root_layout.setSpacing(14)

        header = QHBoxLayout()
        title_block = QVBoxLayout()
        title = QLabel("Kokoro pt_BR Desktop Local")
        title.setObjectName("Title")
        subtitle = QLabel("Texto em voz local com vozes brasileiras do Kokoro")
        subtitle.setObjectName("Subtitle")
        title_block.addWidget(title)
        title_block.addWidget(subtitle)
        header.addLayout(title_block, 1)

        self.status_label = QLabel("Pronto")
        self.status_label.setObjectName("StatusLabel")
        header.addWidget(self.status_label, 0, Qt.AlignRight | Qt.AlignVCenter)
        root_layout.addLayout(header)

        warning = QLabel(
            f"Modelo: {KOKORO_REPO_ID}. A primeira execucao baixa os pesos do Kokoro. "
            "A fonemizacao pt_BR requer espeak-ng instalado no sistema."
        )
        warning.setObjectName("WarningBanner")
        warning.setWordWrap(True)
        root_layout.addWidget(warning)

        splitter = QSplitter(Qt.Horizontal)
        splitter.addWidget(self._build_text_panel())
        splitter.addWidget(self._build_settings_panel())
        splitter.setStretchFactor(0, 3)
        splitter.setStretchFactor(1, 2)
        root_layout.addWidget(splitter, 1)

        action_bar = QHBoxLayout()
        self.generate_button = QPushButton("Gerar WAV")
        self.generate_button.setObjectName("PrimaryButton")
        self.generate_button.setIcon(self.style().standardIcon(QStyle.SP_MediaPlay))
        self.open_file_button = QPushButton("Abrir WAV")
        self.open_file_button.setIcon(self.style().standardIcon(QStyle.SP_FileIcon))
        self.open_file_button.setEnabled(False)
        self.open_folder_button = QPushButton("Abrir pasta")
        self.open_folder_button.setIcon(self.style().standardIcon(QStyle.SP_DirOpenIcon))
        self.open_folder_button.setEnabled(False)
        self.clear_log_button = QPushButton("Limpar log")
        self.clear_log_button.setIcon(self.style().standardIcon(QStyle.SP_DialogResetButton))

        action_bar.addWidget(self.generate_button)
        action_bar.addWidget(self.open_file_button)
        action_bar.addWidget(self.open_folder_button)
        action_bar.addStretch(1)
        action_bar.addWidget(self.clear_log_button)
        root_layout.addLayout(action_bar)

        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 1)
        self.progress_bar.setValue(0)
        self.progress_bar.setTextVisible(False)
        root_layout.addWidget(self.progress_bar)

        log_group = QGroupBox("Log")
        log_layout = QVBoxLayout(log_group)
        self.log_view = QPlainTextEdit()
        self.log_view.setReadOnly(True)
        self.log_view.setMaximumBlockCount(500)
        self.log_view.setPlaceholderText("Os eventos de download, carga do modelo e geracao aparecem aqui.")
        log_layout.addWidget(self.log_view)
        root_layout.addWidget(log_group, 0)

        self.setCentralWidget(root)
        self.setStyleSheet(APP_STYLES)

    def _build_text_panel(self) -> QWidget:
        panel = QFrame()
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        label_row = QHBoxLayout()
        label = QLabel("Texto em portugues do Brasil")
        label.setObjectName("SectionTitle")
        self.char_count_label = QLabel()
        self.char_count_label.setObjectName("MutedLabel")
        label_row.addWidget(label)
        label_row.addStretch(1)
        label_row.addWidget(self.char_count_label)
        layout.addLayout(label_row)

        self.text_edit = QPlainTextEdit()
        self.text_edit.setPlaceholderText("Digite o texto em pt_BR que sera convertido em audio local.")
        self.text_edit.setPlainText(
            "Ola, este e um teste de sintese de voz local em portugues do Brasil usando Kokoro."
        )
        layout.addWidget(self.text_edit, 1)

        return panel

    def _build_settings_panel(self) -> QWidget:
        panel = QWidget()
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(12, 0, 0, 0)
        layout.setSpacing(12)

        runtime_group = QGroupBox("Modelo e runtime")
        runtime_form = QFormLayout(runtime_group)
        runtime_form.setFieldGrowthPolicy(QFormLayout.AllNonFixedFieldsGrow)

        self.kokoro_voice_combo = QComboBox()
        for voice_id, label in KOKORO_VOICES.items():
            self.kokoro_voice_combo.addItem(f"{voice_id} - {label}", voice_id)
        self.kokoro_voice_combo.setCurrentIndex(max(0, self.kokoro_voice_combo.findData(DEFAULT_KOKORO_VOICE)))
        runtime_form.addRow("Voz Kokoro", self.kokoro_voice_combo)

        self.espeak_command_edit = QLineEdit(find_espeak_command() or DEFAULT_ESPEAK_COMMAND)
        runtime_form.addRow("Executavel espeak-ng", self._path_row(self.espeak_command_edit, self._browse_espeak))

        layout.addWidget(runtime_group)

        generation_group = QGroupBox("Geracao")
        generation_form = QFormLayout(generation_group)
        generation_form.setFieldGrowthPolicy(QFormLayout.AllNonFixedFieldsGrow)

        self.speed_spin = QDoubleSpinBox()
        self.speed_spin.setRange(0.5, 2.0)
        self.speed_spin.setSingleStep(0.05)
        self.speed_spin.setValue(1.0)
        generation_form.addRow("Velocidade", self.speed_spin)

        self.silence_spin = QSpinBox()
        self.silence_spin.setRange(0, 2000)
        self.silence_spin.setSingleStep(25)
        self.silence_spin.setValue(180)
        generation_form.addRow("Pausa entre frases (ms)", self.silence_spin)

        self.chunk_checkbox = QCheckBox("Dividir textos longos")
        self.chunk_checkbox.setChecked(True)
        generation_form.addRow("", self.chunk_checkbox)

        self.chunk_chars_spin = QSpinBox()
        self.chunk_chars_spin.setRange(120, 1800)
        self.chunk_chars_spin.setValue(DEFAULT_MAX_CHUNK_CHARS)
        self.chunk_chars_spin.setSingleStep(50)
        generation_form.addRow("Max chars por trecho", self.chunk_chars_spin)

        layout.addWidget(generation_group)

        output_group = QGroupBox("Saida")
        output_form = QFormLayout(output_group)
        output_form.setFieldGrowthPolicy(QFormLayout.AllNonFixedFieldsGrow)

        self.output_dir_edit = QLineEdit(str(Path.cwd() / "outputs"))
        output_form.addRow("Pasta", self._path_row(self.output_dir_edit, self._browse_output_dir))

        self.file_name_edit = QLineEdit("kokoro_ptbr_output.wav")
        output_form.addRow("Arquivo", self.file_name_edit)

        layout.addWidget(output_group)
        layout.addStretch(1)

        return panel

    def _path_row(self, line_edit: QLineEdit, browse_callback) -> QWidget:
        row = QWidget()
        layout = QHBoxLayout(row)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)
        browse_button = QPushButton()
        browse_button.setToolTip("Selecionar caminho")
        browse_button.setIcon(self.style().standardIcon(QStyle.SP_DirOpenIcon))
        browse_button.clicked.connect(browse_callback)
        layout.addWidget(line_edit, 1)
        layout.addWidget(browse_button, 0)
        return row

    def _connect_signals(self) -> None:
        self.text_edit.textChanged.connect(self._update_char_count)
        self.generate_button.clicked.connect(self._start_generation)
        self.open_file_button.clicked.connect(self._open_last_file)
        self.open_folder_button.clicked.connect(self._open_last_folder)
        self.clear_log_button.clicked.connect(self.log_view.clear)

    def _browse_espeak(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Selecionar executavel espeak-ng",
            str(Path.cwd()),
            "Executaveis (*);;Todos os arquivos (*.*)",
        )
        if path:
            self.espeak_command_edit.setText(path)

    def _browse_output_dir(self) -> None:
        path = QFileDialog.getExistingDirectory(self, "Selecionar pasta de saida", self.output_dir_edit.text())
        if path:
            self.output_dir_edit.setText(path)

    def _start_generation(self) -> None:
        if self._thread and self._thread.isRunning():
            return

        try:
            options = self._collect_options()
        except ValueError as exc:
            QMessageBox.warning(self, "Configuracao incompleta", str(exc))
            return

        self._set_running(True)
        self._append_log("Iniciando geracao local com Kokoro...")

        self._thread = QThread()
        self._worker = GenerationWorker(self._engine, options)
        self._worker.moveToThread(self._thread)

        self._thread.started.connect(self._worker.run)
        self._worker.progress.connect(self._append_log)
        self._worker.finished.connect(self._generation_finished)
        self._worker.failed.connect(self._generation_failed)
        self._worker.finished.connect(self._thread.quit)
        self._worker.failed.connect(self._thread.quit)
        self._thread.finished.connect(self._worker.deleteLater)
        self._thread.finished.connect(self._thread.deleteLater)
        self._thread.finished.connect(self._clear_thread_refs)
        self._thread.start()

    def _collect_options(self) -> GenerationOptions:
        text = self.text_edit.toPlainText().strip()
        if not text:
            raise ValueError("Informe um texto para gerar audio.")

        output_dir = Path(self.output_dir_edit.text().strip() or "outputs").expanduser()
        file_name = self.file_name_edit.text().strip() or "kokoro_ptbr_output.wav"
        if not file_name.lower().endswith(".wav"):
            file_name = f"{file_name}.wav"

        return GenerationOptions(
            text=text,
            output_path=output_dir / file_name,
            espeak_command=self.espeak_command_edit.text().strip() or DEFAULT_ESPEAK_COMMAND,
            kokoro_voice=self.kokoro_voice_combo.currentData() or DEFAULT_KOKORO_VOICE,
            kokoro_speed=self.speed_spin.value(),
            chunk_long_text=self.chunk_checkbox.isChecked(),
            max_chunk_chars=self.chunk_chars_spin.value(),
            silence_ms=self.silence_spin.value(),
        )

    @Slot(object)
    def _generation_finished(self, result: object) -> None:
        self._last_output = result.output_path
        self._append_log(
            f"Concluido: {result.output_path} | {result.sample_rate} Hz | "
            f"{result.chunk_count} trecho(s) | voz {result.voice_label}"
        )
        self.status_label.setText("Concluido")
        self.open_file_button.setEnabled(True)
        self.open_folder_button.setEnabled(True)
        self._set_running(False)

    @Slot(str)
    def _generation_failed(self, details: str) -> None:
        self._append_log(details)
        self.status_label.setText("Erro")
        self._set_running(False)
        QMessageBox.critical(
            self,
            "Falha ao gerar audio",
            "A geracao falhou. Veja o log para os detalhes tecnicos.",
        )

    @Slot()
    def _clear_thread_refs(self) -> None:
        self._thread = None
        self._worker = None

    @Slot(str)
    def _append_log(self, message: str) -> None:
        self.log_view.appendPlainText(message.rstrip())

    def _set_running(self, running: bool) -> None:
        self.generate_button.setEnabled(not running)
        self.status_label.setText("Gerando..." if running else self.status_label.text())
        if running:
            self.progress_bar.setRange(0, 0)
        else:
            self.progress_bar.setRange(0, 1)
            self.progress_bar.setValue(0)

    def _update_char_count(self) -> None:
        count = len(self.text_edit.toPlainText())
        self.char_count_label.setText(f"{count} caracteres")

    def _open_last_file(self) -> None:
        if self._last_output:
            open_path(self._last_output)

    def _open_last_folder(self) -> None:
        if self._last_output:
            open_path(self._last_output.parent)


def open_path(path: Path) -> None:
    path = path.resolve()
    if sys.platform.startswith("win"):
        os.startfile(str(path))  # type: ignore[attr-defined]
    elif sys.platform == "darwin":
        subprocess.Popen(["open", str(path)])
    else:
        subprocess.Popen(["xdg-open", str(path)])


APP_STYLES = """
QWidget {
    font-family: "Segoe UI", "Inter", "Arial", sans-serif;
    font-size: 13px;
    color: #202124;
}
QMainWindow {
    background: #f6f7f8;
}
QPlainTextEdit, QLineEdit, QComboBox, QSpinBox, QDoubleSpinBox {
    background: #ffffff;
    border: 1px solid #c9ced6;
    border-radius: 6px;
    padding: 7px;
    selection-background-color: #0f766e;
}
QPlainTextEdit {
    line-height: 1.35;
}
QGroupBox {
    border: 1px solid #d9dde3;
    border-radius: 8px;
    margin-top: 12px;
    padding: 12px;
    background: #ffffff;
    font-weight: 600;
}
QGroupBox::title {
    subcontrol-origin: margin;
    left: 10px;
    padding: 0 4px;
}
QPushButton {
    background: #ffffff;
    border: 1px solid #c9ced6;
    border-radius: 6px;
    padding: 8px 11px;
}
QPushButton:hover {
    background: #eef4f3;
}
QPushButton:disabled {
    color: #8b949e;
    background: #edf0f2;
}
QPushButton#PrimaryButton {
    background: #0f766e;
    border-color: #0f766e;
    color: #ffffff;
    font-weight: 700;
    padding: 9px 16px;
}
QPushButton#PrimaryButton:hover {
    background: #0b5f59;
}
QLabel#Title {
    font-size: 24px;
    font-weight: 750;
}
QLabel#Subtitle, QLabel#MutedLabel {
    color: #5b6470;
}
QLabel#StatusLabel {
    background: #e8f1ef;
    color: #0b5f59;
    border: 1px solid #b9d7d3;
    border-radius: 6px;
    padding: 6px 10px;
    font-weight: 650;
}
QLabel#WarningBanner {
    background: #fff7e6;
    color: #5f4600;
    border: 1px solid #f0d38a;
    border-radius: 8px;
    padding: 10px 12px;
}
QLabel#SectionTitle {
    font-size: 15px;
    font-weight: 700;
}
QProgressBar {
    border: 1px solid #d9dde3;
    border-radius: 4px;
    background: #ffffff;
    height: 8px;
}
QProgressBar::chunk {
    background: #0f766e;
    border-radius: 4px;
}
"""


def main() -> int:
    app = QApplication(sys.argv)
    app.setApplicationName("Kokoro pt_BR Desktop Local")
    window = MainWindow()
    window.show()
    return app.exec()
