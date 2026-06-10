from __future__ import annotations

from dataclasses import dataclass
from datetime import date
import json
import math
from pathlib import Path
import os
import subprocess
import sys
import traceback
import uuid
import wave

from PySide6.QtCore import QObject, QThread, Qt, QTimer, QUrl, Signal, Slot
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
    QInputDialog,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPlainTextEdit,
    QProgressBar,
    QPushButton,
    QScrollArea,
    QSlider,
    QSpinBox,
    QSplitter,
    QStackedWidget,
    QStyle,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

try:  # QtMultimedia is optional in some minimal PySide6 installs.
    from PySide6.QtMultimedia import QAudioOutput, QMediaPlayer
except Exception:  # pragma: no cover - environment dependent
    QAudioOutput = None  # type: ignore[assignment]
    QMediaPlayer = None  # type: ignore[assignment]

try:  # Optional icon pack; standard Qt icons remain as fallback.
    import qtawesome as qta
except Exception:  # pragma: no cover - optional dependency
    qta = None  # type: ignore[assignment]

from .engine import (
    DEFAULT_ESPEAK_COMMAND,
    DEFAULT_KOKORO_VOICE,
    DEFAULT_MAX_CHUNK_CHARS,
    GenerationOptions,
    GenerationResult,
    KOKORO_REPO_ID,
    KOKORO_SAMPLE_RATE,
    KOKORO_VOICES,
    KokoroTTSEngine,
    find_espeak_command,
)


@dataclass
class AudioItem:
    id: str
    title: str
    project: str
    folder: str
    duration_seconds: int
    created_at: str
    voice: str
    status: str = "completed"
    audio_path: Path | None = None

    @property
    def duration_label(self) -> str:
        return format_seconds(self.duration_seconds)

    def to_dict(self) -> dict[str, object]:
        return {
            "id": self.id,
            "title": self.title,
            "project": self.project,
            "folder": self.folder,
            "duration_seconds": self.duration_seconds,
            "created_at": self.created_at,
            "voice": self.voice,
            "status": self.status,
            "audio_path": str(self.audio_path) if self.audio_path else "",
        }

    @classmethod
    def from_dict(cls, data: dict[str, object]) -> "AudioItem":
        audio_path = str(data.get("audio_path") or "")
        return cls(
            id=str(data.get("id") or unique_id("audio")),
            title=str(data.get("title") or "Audio sem titulo"),
            project=str(data.get("project") or DEFAULT_PROJECT_NAME),
            folder=str(data.get("folder") or DEFAULT_FOLDER_NAME),
            duration_seconds=int(data.get("duration_seconds") or 1),
            created_at=str(data.get("created_at") or date.today().isoformat()),
            voice=str(data.get("voice") or "Audio local"),
            status=str(data.get("status") or "completed"),
            audio_path=Path(audio_path) if audio_path else None,
        )


@dataclass
class ProjectItem:
    id: str
    name: str
    total_audios: int
    last_updated: str

    def to_dict(self) -> dict[str, object]:
        return {
            "id": self.id,
            "name": self.name,
            "total_audios": self.total_audios,
            "last_updated": self.last_updated,
        }

    @classmethod
    def from_dict(cls, data: dict[str, object]) -> "ProjectItem":
        return cls(
            id=str(data.get("id") or unique_id("project")),
            name=str(data.get("name") or DEFAULT_PROJECT_NAME),
            total_audios=int(data.get("total_audios") or 0),
            last_updated=str(data.get("last_updated") or date.today().isoformat()),
        )


APP_STATE_VERSION = 1
APP_NAME = "Vocalis"
APP_SLUG = "vocalis"
LEGACY_APP_NAME = "FalaLocal"
LEGACY_APP_SLUG = "falalocal"
DEFAULT_PROJECT_NAME = "Projeto exemplo"
DEFAULT_FOLDER_NAME = "Audios"
TEST_AUDIO_FILE_NAME = "audio_teste_vocalis.wav"


FOLDERS = [
    "Todos",
    "Comunicados",
    "Conteudos",
    "Aberturas",
    "Campanhas",
    "Roteiros",
    "Rascunhos",
]


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


class StatusBadge(QLabel):
    def __init__(self, text: str = "Pronto", tone: str = "neutral") -> None:
        super().__init__(text)
        self.setObjectName("StatusBadge")
        self.set_tone(tone)

    def set_tone(self, tone: str) -> None:
        self.setProperty("tone", tone)
        refresh_style(self)


class PlaybackButton(QPushButton):
    def __init__(self, tooltip: str = "Reproduzir") -> None:
        super().__init__()
        self.setObjectName("IconButton")
        self.setToolTip(tooltip)
        self.setFixedSize(34, 34)
        self.set_playing(False)

    def set_playing(self, playing: bool) -> None:
        icon_name = "fa5s.pause" if playing else "fa5s.play"
        fallback = QStyle.SP_MediaPause if playing else QStyle.SP_MediaPlay
        self.setIcon(professional_icon(self, icon_name, fallback, "#1457d9"))
        self.setToolTip("Pausar" if playing else "Reproduzir")


class AudioProgressBar(QWidget):
    moved = Signal(int)

    def __init__(self, interactive: bool = False) -> None:
        super().__init__()
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        self.current_label = QLabel("00:00")
        self.current_label.setObjectName("TinyMutedLabel")
        self.slider = QSlider(Qt.Horizontal)
        self.slider.setRange(0, 1)
        self.slider.setEnabled(interactive)
        self.slider.setObjectName("AudioSlider")
        self.duration_label = QLabel("00:00")
        self.duration_label.setObjectName("TinyMutedLabel")

        layout.addWidget(self.current_label)
        layout.addWidget(self.slider, 1)
        layout.addWidget(self.duration_label)

        self.slider.sliderMoved.connect(self.moved.emit)

    def set_interactive(self, interactive: bool) -> None:
        self.slider.setEnabled(interactive)

    def set_duration(self, seconds: int) -> None:
        self.slider.setRange(0, max(1, seconds))
        self.duration_label.setText(format_seconds(seconds))

    def set_position(self, seconds: int) -> None:
        self.slider.blockSignals(True)
        self.slider.setValue(max(0, min(seconds, self.slider.maximum())))
        self.slider.blockSignals(False)
        self.current_label.setText(format_seconds(seconds))


class VolumeControl(QWidget):
    changed = Signal(int)

    def __init__(self) -> None:
        super().__init__()
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)

        icon = QPushButton()
        icon.setObjectName("FlatIconButton")
        icon.setIcon(professional_icon(icon, "fa5s.volume-up", QStyle.SP_MediaVolume, "#334155"))
        icon.setFixedSize(26, 26)
        icon.setToolTip("Volume")

        self.slider = QSlider(Qt.Horizontal)
        self.slider.setObjectName("VolumeSlider")
        self.slider.setRange(0, 100)
        self.slider.setValue(82)
        self.slider.setFixedWidth(92)
        self.slider.valueChanged.connect(self.changed.emit)

        layout.addWidget(icon)
        layout.addWidget(self.slider)

    def value(self) -> int:
        return self.slider.value()


class MetricCard(QFrame):
    def __init__(self, label: str, value: str, accent: str = "blue") -> None:
        super().__init__()
        self.setObjectName("MetricCard")
        self.setProperty("accent", accent)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 12, 14, 12)
        layout.setSpacing(4)

        value_label = QLabel(value)
        value_label.setObjectName("MetricValue")
        text_label = QLabel(label)
        text_label.setObjectName("MutedLabel")

        layout.addWidget(value_label)
        layout.addWidget(text_label)


class EmptyState(QFrame):
    def __init__(self, title: str, message: str) -> None:
        super().__init__()
        self.setObjectName("EmptyState")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(28, 28, 28, 28)
        layout.setSpacing(8)
        layout.setAlignment(Qt.AlignCenter)

        icon = QLabel()
        icon.setPixmap(professional_icon(self, "fa5s.file-audio", QStyle.SP_FileDialogContentsView, "#64748b").pixmap(36, 36))
        icon.setAlignment(Qt.AlignCenter)

        title_label = QLabel(title)
        title_label.setObjectName("EmptyTitle")
        title_label.setAlignment(Qt.AlignCenter)

        message_label = QLabel(message)
        message_label.setObjectName("MutedLabel")
        message_label.setWordWrap(True)
        message_label.setAlignment(Qt.AlignCenter)

        layout.addWidget(icon)
        layout.addWidget(title_label)
        layout.addWidget(message_label)


class Sidebar(QFrame):
    page_selected = Signal(str)
    project_selected = Signal(str)
    create_project_requested = Signal()
    rename_project_requested = Signal(str)
    delete_project_requested = Signal(str)

    def __init__(self, projects: list[ProjectItem], selected_project: str) -> None:
        super().__init__()
        self.setObjectName("Sidebar")
        self.setFixedWidth(264)
        self._projects = projects
        self._selected_project = selected_project
        self._project_buttons: dict[str, QPushButton] = {}

        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 14, 14, 12)
        layout.setSpacing(12)

        brand_row = QHBoxLayout()
        logo = QLabel()
        logo.setObjectName("LogoMark")
        logo.setPixmap(professional_icon(self, "fa5s.wave-square", QStyle.SP_MediaVolume, "#ffffff").pixmap(20, 20))
        logo.setAlignment(Qt.AlignCenter)
        brand_text = QVBoxLayout()
        app_name = QLabel(APP_NAME)
        app_name.setObjectName("SidebarTitle")
        brand_text.addWidget(app_name)
        brand_row.addWidget(logo)
        brand_row.addLayout(brand_text, 1)
        layout.addLayout(brand_row)

        '''self.new_audio_button = QPushButton("Novo audio")
        self.new_audio_button.setObjectName("SidebarPrimaryButton")
        self.new_audio_button.setIcon(professional_icon(self.new_audio_button, "fa5s.plus", QStyle.SP_FileIcon, "#ffffff"))
        self.new_audio_button.clicked.connect(lambda: self.page_selected.emit("create"))
        layout.addWidget(self.new_audio_button)'''

        project_header = QHBoxLayout()
        project_label = QLabel("Projetos")
        project_label.setObjectName("SidebarSectionLabel")
        project_header.addWidget(project_label)
        project_header.addStretch(1)

        self.add_project_button = self._make_icon_button("Criar projeto", QStyle.SP_FileDialogNewFolder)
        self.rename_project_button = self._make_icon_button("Renomear projeto selecionado", QStyle.SP_FileDialogDetailedView)
        self.delete_project_button = self._make_icon_button("Excluir projeto selecionado", QStyle.SP_TrashIcon)
        self.add_project_button.clicked.connect(self.create_project_requested.emit)
        self.rename_project_button.clicked.connect(self._request_rename_selected)
        self.delete_project_button.clicked.connect(self._request_delete_selected)
        project_header.addWidget(self.add_project_button)
        project_header.addWidget(self.rename_project_button)
        project_header.addWidget(self.delete_project_button)
        layout.addLayout(project_header)

        self.project_scroll = QScrollArea()
        self.project_scroll.setObjectName("SidebarProjectScroll")
        self.project_scroll.setWidgetResizable(True)
        self.project_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.project_container = QWidget()
        self.project_layout = QVBoxLayout(self.project_container)
        self.project_layout.setContentsMargins(0, 0, 0, 0)
        self.project_layout.setSpacing(5)
        self.project_scroll.setWidget(self.project_container)
        layout.addWidget(self.project_scroll, 1)

        quick = QFrame()
        quick.setObjectName("SidebarPanel")
        quick_layout = QVBoxLayout(quick)
        quick_layout.setContentsMargins(10, 10, 10, 10)
        quick_layout.setSpacing(4)
        quick_title = QLabel("Sistema")
        quick_title.setObjectName("SidebarPanelTitle")
        self.runtime_label = QLabel("Kokoro pt_BR pronto")
        self.runtime_label.setObjectName("SidebarSubtitle")
        quick_layout.addWidget(quick_title)
        quick_layout.addWidget(self.runtime_label)
        layout.addWidget(quick)

        settings_button = self._make_nav_button("Configuracoes", QStyle.SP_FileDialogDetailedView)
        settings_button.clicked.connect(lambda: self.page_selected.emit("settings"))
        layout.addWidget(settings_button)
        self.settings_button = settings_button
        self._rebuild_projects()

    def set_active(self, page: str) -> None:
        self.settings_button.setChecked(page == "settings")
        self.new_audio_button.setProperty("active", page == "create")
        refresh_style(self.new_audio_button)

    def set_projects(self, projects: list[ProjectItem], selected_project: str) -> None:
        self._projects = projects
        self._selected_project = selected_project
        self._rebuild_projects()

    def selected_project(self) -> str:
        return self._selected_project

    def set_runtime_status(self, text: str) -> None:
        self.runtime_label.setText(text)

    def _make_nav_button(self, text: str, icon: QStyle.StandardPixmap) -> QPushButton:
        button = QPushButton(text)
        button.setObjectName("SidebarButton")
        button.setIcon(professional_icon(button, "fa5s.cog", icon, "#cbd5e1"))
        button.setCheckable(True)
        button.setCursor(Qt.PointingHandCursor)
        return button

    def _make_icon_button(self, tooltip: str, icon: QStyle.StandardPixmap) -> QPushButton:
        button = QPushButton()
        button.setObjectName("SidebarIconButton")
        button.setToolTip(tooltip)
        icon_name = {
            QStyle.SP_FileDialogNewFolder: "fa5s.folder-plus",
            QStyle.SP_FileDialogDetailedView: "fa5s.pen",
            QStyle.SP_TrashIcon: "fa5s.trash",
        }.get(icon, "fa5s.circle")
        button.setIcon(professional_icon(button, icon_name, icon, "#cbd5e1"))
        button.setFixedSize(26, 26)
        button.setCursor(Qt.PointingHandCursor)
        return button

    def _rebuild_projects(self) -> None:
        clear_layout(self.project_layout)
        self._project_buttons.clear()
        for project in self._projects:
            label = f"{project.name}\n{project.total_audios} audio{'s' if project.total_audios != 1 else ''}"
            button = QPushButton(label)
            button.setObjectName("SidebarProjectButton")
            button.setCheckable(True)
            button.setChecked(project.name == self._selected_project)
            button.setCursor(Qt.PointingHandCursor)
            button.clicked.connect(lambda _checked=False, name=project.name: self._select_project(name))
            self._project_buttons[project.name] = button
            self.project_layout.addWidget(button)
        self.project_layout.addStretch(1)
        self.rename_project_button.setEnabled(bool(self._projects))
        self.delete_project_button.setEnabled(len(self._projects) > 1)

    def _select_project(self, name: str) -> None:
        self._selected_project = name
        for project_name, button in self._project_buttons.items():
            button.setChecked(project_name == name)
        self.settings_button.setChecked(False)
        self.new_audio_button.setProperty("active", False)
        refresh_style(self.new_audio_button)
        self.project_selected.emit(name)

    def _request_rename_selected(self) -> None:
        if self._selected_project:
            self.rename_project_requested.emit(self._selected_project)

    def _request_delete_selected(self) -> None:
        if self._selected_project:
            self.delete_project_requested.emit(self._selected_project)


class PageHeader(QFrame):
    def __init__(
        self,
        title: str,
        subtitle: str,
        *,
        search_placeholder: str | None = None,
        primary_text: str | None = None,
        primary_icon: QStyle.StandardPixmap | None = None,
    ) -> None:
        super().__init__()
        self.setObjectName("PageHeader")
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(14)

        title_block = QVBoxLayout()
        self.title_label = QLabel(title)
        self.title_label.setObjectName("PageTitle")
        self.subtitle_label = QLabel(subtitle)
        self.subtitle_label.setObjectName("MutedLabel")
        title_block.addWidget(self.title_label)
        title_block.addWidget(self.subtitle_label)
        layout.addLayout(title_block, 1)

        self.search_input: QLineEdit | None = None
        if search_placeholder:
            self.search_input = QLineEdit()
            self.search_input.setObjectName("SearchInput")
            self.search_input.setPlaceholderText(search_placeholder)
            self.search_input.setClearButtonEnabled(True)
            self.search_input.setFixedWidth(280)
            layout.addWidget(self.search_input)

        self.primary_button: QPushButton | None = None
        if primary_text:
            self.primary_button = QPushButton(primary_text)
            self.primary_button.setObjectName("PrimaryButton")
            if primary_icon is not None:
                self.primary_button.setIcon(professional_icon(self.primary_button, "fa5s.plus", primary_icon, "#ffffff"))
            layout.addWidget(self.primary_button)


class AudioCard(QFrame):
    play_requested = Signal(str)
    download_requested = Signal(str)
    delete_requested = Signal(str)
    move_requested = Signal(str)

    def __init__(self, audio: AudioItem) -> None:
        super().__init__()
        self.audio = audio
        self.setObjectName("AudioCard")
        self.setProperty("active", False)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 12, 14, 12)
        layout.setSpacing(10)

        header = QHBoxLayout()
        title_block = QVBoxLayout()
        title = QLabel(audio.title)
        title.setObjectName("CardTitle")
        meta = QLabel(f"{audio.project} / {audio.folder}  |  {audio.created_at}  |  {audio.voice}")
        meta.setObjectName("MutedLabel")
        meta.setWordWrap(True)
        title_block.addWidget(title)
        title_block.addWidget(meta)
        header.addLayout(title_block, 1)

        self.badge = StatusBadge("Concluido", "success")
        header.addWidget(self.badge)
        layout.addLayout(header)

        player_row = QHBoxLayout()
        self.play_button = PlaybackButton()
        self.play_button.clicked.connect(lambda: self.play_requested.emit(self.audio.id))
        self.progress = AudioProgressBar(interactive=False)
        self.progress.set_duration(audio.duration_seconds)
        self.duration_pill = QLabel(audio.duration_label)
        self.duration_pill.setObjectName("DurationPill")

        player_row.addWidget(self.play_button)
        player_row.addWidget(self.progress, 1)
        player_row.addWidget(self.duration_pill)
        layout.addLayout(player_row)

        action_row = QHBoxLayout()
        action_row.addStretch(1)
        for tooltip, icon, signal in (
            ("Mover para pasta", QStyle.SP_DirIcon, self.move_requested),
            ("Baixar ou abrir arquivo", QStyle.SP_DialogSaveButton, self.download_requested),
            ("Excluir audio", QStyle.SP_TrashIcon, self.delete_requested),
        ):
            button = QPushButton()
            button.setObjectName("FlatIconButton")
            button.setToolTip(tooltip)
            icon_name = {
                QStyle.SP_DirIcon: "fa5s.folder-open",
                QStyle.SP_DialogSaveButton: "fa5s.download",
                QStyle.SP_TrashIcon: "fa5s.trash",
            }.get(icon, "fa5s.circle")
            button.setIcon(professional_icon(button, icon_name, icon, "#475569"))
            button.setFixedSize(30, 30)
            button.clicked.connect(lambda _checked=False, signal=signal: signal.emit(self.audio.id))
            action_row.addWidget(button)
        layout.addLayout(action_row)

    def set_playback_state(self, active: bool, playing: bool, position: int, duration: int) -> None:
        self.setProperty("active", active)
        refresh_style(self)
        self.play_button.set_playing(active and playing)
        self.progress.set_duration(duration if active else self.audio.duration_seconds)
        self.progress.set_position(position if active else 0)


class GalleryPage(QWidget):
    new_audio_requested = Signal()
    play_audio_requested = Signal(str)
    download_audio_requested = Signal(str)
    delete_audio_requested = Signal(str)
    move_audio_requested = Signal(str)

    def __init__(self, audios: list[AudioItem], selected_project: str) -> None:
        super().__init__()
        self._audios = audios
        self._cards: dict[str, AudioCard] = {}
        self._active_project = selected_project
        self._active_audio_id: str | None = None
        self._is_playing = False
        self._position = 0
        self._duration = 0

        layout = QVBoxLayout(self)
        layout.setContentsMargins(22, 14, 22, 0)
        layout.setSpacing(12)

        self.header = PageHeader(
            selected_project,
            "Biblioteca do projeto, com busca, filtros e reproducao direta.",
            search_placeholder="Buscar audios",
            primary_text="Novo audio",
            primary_icon=QStyle.SP_FileIcon,
        )
        self.header.primary_button.clicked.connect(self.new_audio_requested.emit)
        self.header.search_input.textChanged.connect(self._rebuild_cards)
        layout.addWidget(self.header)

        self.metrics_row = QHBoxLayout()
        layout.addLayout(self.metrics_row)

        library = QFrame()
        library.setObjectName("Panel")
        library_layout = QVBoxLayout(library)
        library_layout.setContentsMargins(14, 14, 14, 14)
        library_layout.setSpacing(10)

        filter_row = QHBoxLayout()
        section_title = QLabel("Biblioteca")
        section_title.setObjectName("SectionTitle")
        filter_row.addWidget(section_title)
        filter_row.addStretch(1)

        self.folder_filter = QComboBox()
        self.folder_filter.setObjectName("CompactInput")
        self.folder_filter.addItems(FOLDERS)
        self.folder_filter.currentTextChanged.connect(self._rebuild_cards)
        filter_row.addWidget(QLabel("Pasta"))
        filter_row.addWidget(self.folder_filter)

        self.date_filter = QComboBox()
        self.date_filter.setObjectName("CompactInput")
        self.date_filter.addItems(["Todas as datas", "Hoje", "Ultimos 7 dias"])
        self.date_filter.currentTextChanged.connect(self._rebuild_cards)
        filter_row.addWidget(QLabel("Data"))
        filter_row.addWidget(self.date_filter)
        library_layout.addLayout(filter_row)

        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setObjectName("ScrollArea")
        self.cards_container = QWidget()
        self.cards_layout = QVBoxLayout(self.cards_container)
        self.cards_layout.setContentsMargins(0, 0, 0, 0)
        self.cards_layout.setSpacing(10)
        self.scroll.setWidget(self.cards_container)
        library_layout.addWidget(self.scroll, 1)

        self.empty_state = EmptyState(
            "Nenhum audio encontrado",
            "Crie um novo audio para este projeto ou ajuste os filtros.",
        )
        self.empty_state.hide()
        library_layout.addWidget(self.empty_state)

        layout.addWidget(library, 1)

        self._rebuild_metrics()
        self._rebuild_cards()

    def set_audios(self, audios: list[AudioItem]) -> None:
        self._audios = audios
        self._rebuild_metrics()
        self._rebuild_cards()

    def set_project(self, project_name: str) -> None:
        self._active_project = project_name
        self.header.title_label.setText(project_name)
        self.header.subtitle_label.setText("Biblioteca do projeto, com busca, filtros e reproducao direta.")
        self._rebuild_metrics()
        self._rebuild_cards()

    def set_playback(self, audio_id: str | None, playing: bool, position: int, duration: int) -> None:
        self._active_audio_id = audio_id
        self._is_playing = playing
        self._position = position
        self._duration = duration
        for card in self._cards.values():
            active = card.audio.id == audio_id
            card.set_playback_state(active, playing, position, duration)

    def _rebuild_metrics(self) -> None:
        clear_layout(self.metrics_row)
        project_audios = [audio for audio in self._audios if audio.project == self._active_project]
        today = date.today().isoformat()
        total_duration = sum(audio.duration_seconds for audio in project_audios)
        completed = sum(1 for audio in project_audios if audio.status == "completed")
        metrics = [
            ("Audios no projeto", str(len(project_audios)), "blue"),
            ("Gerados hoje", str(sum(1 for audio in project_audios if audio.created_at == today)), "green"),
            ("Concluidos", str(completed), "purple"),
            ("Tempo total", format_seconds(total_duration), "slate"),
        ]
        for label, value, accent in metrics:
            self.metrics_row.addWidget(MetricCard(label, value, accent))

    def _filtered_audios(self) -> list[AudioItem]:
        query = self.header.search_input.text().strip().lower() if self.header.search_input else ""
        folder = self.folder_filter.currentText()
        date_filter = self.date_filter.currentText()
        today = date.today().isoformat()

        filtered: list[AudioItem] = []
        for audio in self._audios:
            if audio.project != self._active_project:
                continue
            if folder != "Todos" and audio.folder != folder:
                continue
            if query and query not in f"{audio.title} {audio.project} {audio.folder} {audio.voice}".lower():
                continue
            if date_filter == "Hoje" and audio.created_at != today:
                continue
            filtered.append(audio)
        return filtered

    def _rebuild_cards(self) -> None:
        clear_layout(self.cards_layout)
        self._cards.clear()
        filtered = self._filtered_audios()

        for audio in filtered:
            card = AudioCard(audio)
            card.play_requested.connect(self.play_audio_requested.emit)
            card.download_requested.connect(self.download_audio_requested.emit)
            card.delete_requested.connect(self.delete_audio_requested.emit)
            card.move_requested.connect(self.move_audio_requested.emit)
            self.cards_layout.addWidget(card)
            self._cards[audio.id] = card

        self.cards_layout.addStretch(1)
        self.empty_state.setVisible(not filtered)
        self.scroll.setVisible(bool(filtered))
        self.set_playback(self._active_audio_id, self._is_playing, self._position, self._duration)


class TextEditorPanel(QFrame):
    def __init__(self) -> None:
        super().__init__()
        self.setObjectName("Panel")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        top = QHBoxLayout()
        title = QLabel("Editor de texto")
        title.setObjectName("SectionTitle")
        self.char_count_label = QLabel("0 caracteres")
        self.char_count_label.setObjectName("MutedLabel")
        top.addWidget(title)
        top.addStretch(1)
        top.addWidget(self.char_count_label)
        layout.addLayout(top)

        self.text_edit = QPlainTextEdit()
        self.text_edit.setObjectName("LargeTextEdit")
        self.text_edit.setPlaceholderText("Digite o texto em pt_BR que sera convertido em audio.")
        self.text_edit.setPlainText(
            "Ola, este e um teste de sintese de voz local em portugues do Brasil usando Kokoro."
        )
        self.text_edit.textChanged.connect(self._update_count)
        layout.addWidget(self.text_edit, 1)

        bottom = QHBoxLayout()
        self.limit_label = QLabel("Sugestao: ate 4.000 caracteres por geracao para revisao rapida.")
        self.limit_label.setObjectName("TinyMutedLabel")
        bottom.addWidget(self.limit_label, 1)

        clear_button = QPushButton("Limpar")
        clear_button.setIcon(professional_icon(clear_button, "fa5s.eraser", QStyle.SP_DialogResetButton))
        clear_button.clicked.connect(self.text_edit.clear)
        paste_button = QPushButton("Colar")
        paste_button.setIcon(professional_icon(paste_button, "fa5s.clipboard", QStyle.SP_DialogOpenButton))
        paste_button.clicked.connect(self._paste_clipboard)
        bottom.addWidget(clear_button)
        bottom.addWidget(paste_button)
        layout.addLayout(bottom)
        self._update_count()

    def text(self) -> str:
        return self.text_edit.toPlainText()

    def set_text(self, text: str) -> None:
        self.text_edit.setPlainText(text)

    def _paste_clipboard(self) -> None:
        text = QApplication.clipboard().text()
        if text:
            self.text_edit.insertPlainText(text)

    def _update_count(self) -> None:
        count = len(self.text_edit.toPlainText())
        self.char_count_label.setText(f"{count} caracteres")


class VoiceSettingsPanel(QFrame):
    def __init__(self, projects: list[ProjectItem]) -> None:
        super().__init__()
        self.setObjectName("Panel")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        title = QLabel("Configuracoes de voz")
        title.setObjectName("SectionTitle")
        layout.addWidget(title)

        form = QFormLayout()
        form.setFieldGrowthPolicy(QFormLayout.AllNonFixedFieldsGrow)
        form.setLabelAlignment(Qt.AlignLeft)

        self.voice_combo = QComboBox()
        for voice_id, label in KOKORO_VOICES.items():
            self.voice_combo.addItem(f"{voice_id} - {label}", voice_id)
        self.voice_combo.setCurrentIndex(max(0, self.voice_combo.findData(DEFAULT_KOKORO_VOICE)))
        form.addRow("Voz", self.voice_combo)

        self.language_combo = QComboBox()
        self.language_combo.addItems(["pt_BR - Portugues do Brasil"])
        form.addRow("Idioma", self.language_combo)

        self.tone_combo = QComboBox()
        self.tone_combo.addItems(["Natural", "Institucional", "Narrativo", "Energetico", "Calmo"])
        form.addRow("Tom", self.tone_combo)

        self.speed_spin = QDoubleSpinBox()
        self.speed_spin.setRange(0.5, 2.0)
        self.speed_spin.setSingleStep(0.05)
        self.speed_spin.setValue(1.0)
        form.addRow("Velocidade", self.speed_spin)

        self.stability_slider = self._slider(72)
        form.addRow("Estabilidade", self.stability_slider)
        self.similarity_slider = self._slider(68)
        form.addRow("Similaridade", self.similarity_slider)
        self.clarity_slider = self._slider(82)
        form.addRow("Clareza", self.clarity_slider)

        self.style_combo = QComboBox()
        self.style_combo.addItems(["Aula", "Comunicado", "Podcast", "Video", "Institucional"])
        form.addRow("Estilo", self.style_combo)

        self.pause_spin = QSpinBox()
        self.pause_spin.setRange(0, 2000)
        self.pause_spin.setSingleStep(25)
        self.pause_spin.setValue(180)
        form.addRow("Pausas (ms)", self.pause_spin)

        self.emotion_slider = self._slider(42)
        form.addRow("Intensidade", self.emotion_slider)

        layout.addLayout(form)

        output_title = QLabel("Organizacao")
        output_title.setObjectName("SectionTitle")
        layout.addWidget(output_title)

        output_form = QFormLayout()
        output_form.setFieldGrowthPolicy(QFormLayout.AllNonFixedFieldsGrow)

        self.project_combo = QComboBox()
        self.project_combo.addItems([project.name for project in projects])
        output_form.addRow("Projeto", self.project_combo)

        self.folder_combo = QComboBox()
        self.folder_combo.addItems(FOLDERS[1:])
        output_form.addRow("Pasta", self.folder_combo)

        self.file_name_edit = QLineEdit("vocalis_audio.wav")
        output_form.addRow("Arquivo", self.file_name_edit)

        layout.addLayout(output_form)
        layout.addStretch(1)

    def selected_voice(self) -> str:
        return self.voice_combo.currentData() or DEFAULT_KOKORO_VOICE

    def selected_voice_label(self) -> str:
        return self.voice_combo.currentText()

    def speed(self) -> float:
        return self.speed_spin.value()

    def pause_ms(self) -> int:
        return self.pause_spin.value()

    def project(self) -> str:
        return self.project_combo.currentText()

    def set_projects(self, projects: list[ProjectItem], selected_project: str | None = None) -> None:
        current = selected_project or self.project_combo.currentText()
        self.project_combo.blockSignals(True)
        self.project_combo.clear()
        self.project_combo.addItems([project.name for project in projects])
        index = self.project_combo.findText(current)
        self.project_combo.setCurrentIndex(max(0, index))
        self.project_combo.blockSignals(False)

    def set_current_project(self, project_name: str) -> None:
        index = self.project_combo.findText(project_name)
        if index >= 0:
            self.project_combo.setCurrentIndex(index)

    def folder(self) -> str:
        return self.folder_combo.currentText()

    def file_name(self) -> str:
        return self.file_name_edit.text().strip()

    def set_running(self, running: bool) -> None:
        self.setEnabled(not running)

    def _slider(self, value: int) -> QSlider:
        slider = QSlider(Qt.Horizontal)
        slider.setRange(0, 100)
        slider.setValue(value)
        return slider


class AudioPlayer(QFrame):
    play_requested = Signal(str)
    download_requested = Signal(str)
    save_requested = Signal(str)
    retry_requested = Signal()

    def __init__(self, title: str) -> None:
        super().__init__()
        self.setObjectName("PreviewPlayer")
        self._audio: AudioItem | None = None

        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 14, 14, 14)
        layout.setSpacing(10)

        top = QHBoxLayout()
        title_label = QLabel(title)
        title_label.setObjectName("SectionTitle")
        self.state_badge = StatusBadge("Aguardando", "neutral")
        top.addWidget(title_label)
        top.addStretch(1)
        top.addWidget(self.state_badge)
        layout.addLayout(top)

        self.audio_title = QLabel("Nenhum audio gerado")
        self.audio_title.setObjectName("CardTitle")
        self.audio_meta = QLabel("Gere um audio para ouvir o preview antes de salvar.")
        self.audio_meta.setObjectName("MutedLabel")
        self.audio_meta.setWordWrap(True)
        layout.addWidget(self.audio_title)
        layout.addWidget(self.audio_meta)

        row = QHBoxLayout()
        self.play_button = PlaybackButton()
        self.play_button.setEnabled(False)
        self.play_button.clicked.connect(self._emit_play)
        self.progress = AudioProgressBar(interactive=True)
        self.volume = VolumeControl()
        row.addWidget(self.play_button)
        row.addWidget(self.progress, 1)
        row.addWidget(self.volume)
        layout.addLayout(row)

        actions = QHBoxLayout()
        actions.addStretch(1)
        self.download_button = QPushButton("Baixar")
        self.download_button.setIcon(professional_icon(self.download_button, "fa5s.download", QStyle.SP_DialogSaveButton))
        self.download_button.setEnabled(False)
        self.download_button.clicked.connect(self._emit_download)
        self.save_button = QPushButton("Salvar em pasta")
        self.save_button.setIcon(professional_icon(self.save_button, "fa5s.check", QStyle.SP_DialogApplyButton))
        self.save_button.setEnabled(False)
        self.save_button.clicked.connect(self._emit_save)
        self.retry_button = QPushButton("Gerar novamente")
        self.retry_button.setIcon(professional_icon(self.retry_button, "fa5s.redo", QStyle.SP_BrowserReload))
        self.retry_button.clicked.connect(self.retry_requested.emit)
        actions.addWidget(self.download_button)
        actions.addWidget(self.save_button)
        actions.addWidget(self.retry_button)
        layout.addLayout(actions)

    def set_audio(self, audio: AudioItem | None, status: str = "ready") -> None:
        self._audio = audio
        enabled = audio is not None
        self.play_button.setEnabled(enabled)
        self.download_button.setEnabled(enabled)
        self.save_button.setEnabled(enabled)
        self.retry_button.setEnabled(True)

        if audio is None:
            self.audio_title.setText("Nenhum audio gerado")
            self.audio_meta.setText("Gere um audio para ouvir o preview antes de salvar.")
            self.state_badge.setText("Aguardando")
            self.state_badge.set_tone("neutral")
            self.progress.set_duration(1)
            self.progress.set_position(0)
            return

        self.audio_title.setText(audio.title)
        self.audio_meta.setText(f"{audio.project} / {audio.folder}  |  {audio.duration_label}  |  {audio.voice}")
        self.state_badge.setText("Pronto" if status == "ready" else status)
        self.state_badge.set_tone("success" if status == "ready" else "neutral")
        self.progress.set_duration(audio.duration_seconds)
        self.progress.set_position(0)

    def set_loading(self) -> None:
        self.state_badge.setText("Gerando")
        self.state_badge.set_tone("warning")
        self.play_button.setEnabled(False)
        self.download_button.setEnabled(False)
        self.save_button.setEnabled(False)

    def set_error(self) -> None:
        self.state_badge.setText("Erro")
        self.state_badge.set_tone("danger")

    def set_playback(self, audio_id: str | None, playing: bool, position: int, duration: int) -> None:
        active = self._audio is not None and self._audio.id == audio_id
        self.play_button.set_playing(active and playing)
        self.progress.set_duration(duration if active else (self._audio.duration_seconds if self._audio else 1))
        self.progress.set_position(position if active else 0)

    def _emit_play(self) -> None:
        if self._audio:
            self.play_requested.emit(self._audio.id)

    def _emit_download(self) -> None:
        if self._audio:
            self.download_requested.emit(self._audio.id)

    def _emit_save(self) -> None:
        if self._audio:
            self.save_requested.emit(self._audio.id)


class CreateAudioPage(QWidget):
    generate_requested = Signal()
    preview_requested = Signal()
    save_draft_requested = Signal()
    cancel_requested = Signal()

    def __init__(self, projects: list[ProjectItem]) -> None:
        super().__init__()
        layout = QVBoxLayout(self)
        layout.setContentsMargins(22, 14, 22, 0)
        layout.setSpacing(12)

        header = QHBoxLayout()
        title_block = QVBoxLayout()
        title = QLabel("Criar Audio")
        title.setObjectName("PageTitle")
        subtitle = QLabel("Escreva, ajuste a voz e gere um preview antes de salvar.")
        subtitle.setObjectName("MutedLabel")
        title_block.addWidget(title)
        title_block.addWidget(subtitle)
        header.addLayout(title_block, 1)
        self.status_badge = StatusBadge("Pronto", "success")
        header.addWidget(self.status_badge)
        layout.addLayout(header)

        splitter = QSplitter(Qt.Horizontal)
        self.editor_panel = TextEditorPanel()
        self.voice_panel = VoiceSettingsPanel(projects)
        splitter.addWidget(self.editor_panel)
        splitter.addWidget(self.voice_panel)
        splitter.setStretchFactor(0, 3)
        splitter.setStretchFactor(1, 2)
        layout.addWidget(splitter, 1)

        self.preview_player = AudioPlayer("Preview")
        layout.addWidget(self.preview_player)

        actions = QHBoxLayout()
        self.progress_bar = QProgressBar()
        self.progress_bar.setTextVisible(False)
        self.progress_bar.setRange(0, 1)
        self.progress_bar.setValue(0)
        actions.addWidget(self.progress_bar, 1)

        self.cancel_button = QPushButton("Cancelar")
        self.cancel_button.setIcon(professional_icon(self.cancel_button, "fa5s.times", QStyle.SP_DialogCancelButton))
        self.preview_button = QPushButton("Pre-visualizar")
        self.preview_button.setIcon(professional_icon(self.preview_button, "fa5s.play", QStyle.SP_MediaPlay))
        self.save_draft_button = QPushButton("Salvar rascunho")
        self.save_draft_button.setIcon(professional_icon(self.save_draft_button, "fa5s.save", QStyle.SP_DialogSaveButton))
        self.generate_button = QPushButton("Gerar audio")
        self.generate_button.setObjectName("PrimaryButton")
        self.generate_button.setIcon(professional_icon(self.generate_button, "fa5s.bolt", QStyle.SP_MediaPlay, "#ffffff"))

        actions.addWidget(self.cancel_button)
        actions.addWidget(self.preview_button)
        actions.addWidget(self.save_draft_button)
        actions.addWidget(self.generate_button)
        layout.addLayout(actions)

        self.generate_button.clicked.connect(self.generate_requested.emit)
        self.preview_button.clicked.connect(self.preview_requested.emit)
        self.save_draft_button.clicked.connect(self.save_draft_requested.emit)
        self.cancel_button.clicked.connect(self.cancel_requested.emit)

    def text(self) -> str:
        return self.editor_panel.text()

    def set_status(self, text: str, tone: str) -> None:
        self.status_badge.setText(text)
        self.status_badge.set_tone(tone)

    def set_running(self, running: bool) -> None:
        self.generate_button.setEnabled(not running)
        self.preview_button.setEnabled(not running)
        self.save_draft_button.setEnabled(not running)
        self.voice_panel.set_running(running)
        if running:
            self.set_status("Gerando...", "warning")
            self.progress_bar.setRange(0, 0)
            self.preview_player.set_loading()
        else:
            self.progress_bar.setRange(0, 1)
            self.progress_bar.setValue(0)

    def show_preview(self, audio: AudioItem | None) -> None:
        self.preview_player.set_audio(audio)


class SettingsSection(QGroupBox):
    def __init__(self, title: str) -> None:
        super().__init__(title)
        self.setObjectName("SettingsSection")
        self.form = QFormLayout(self)
        self.form.setFieldGrowthPolicy(QFormLayout.AllNonFixedFieldsGrow)
        self.form.setLabelAlignment(Qt.AlignLeft)


class SettingsPage(QWidget):
    test_requested = Signal()

    def __init__(self) -> None:
        super().__init__()
        outer = QVBoxLayout(self)
        outer.setContentsMargins(22, 14, 22, 0)
        outer.setSpacing(12)

        header = PageHeader(
            "Configuracoes",
            "Preferencias globais, audio, geracao, runtime e logs tecnicos.",
        )
        outer.addWidget(header)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setObjectName("ScrollArea")
        content = QWidget()
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(0, 0, 0, 18)
        content_layout.setSpacing(14)

        top_grid = QHBoxLayout()
        top_grid.setSpacing(14)
        top_grid.addWidget(self._build_general_section(), 1)
        top_grid.addWidget(self._build_audio_section(), 1)
        content_layout.addLayout(top_grid)

        middle_grid = QHBoxLayout()
        middle_grid.setSpacing(14)
        middle_grid.addWidget(self._build_generation_section(), 1)
        middle_grid.addWidget(self._build_technical_section(), 1)
        content_layout.addLayout(middle_grid)

        bottom_grid = QHBoxLayout()
        bottom_grid.setSpacing(14)
        bottom_grid.addWidget(self._build_appearance_section(), 1)
        bottom_grid.addWidget(self._build_logs_section(), 2)
        content_layout.addLayout(bottom_grid)

        scroll.setWidget(content)
        outer.addWidget(scroll, 1)

    def output_dir(self) -> str:
        return self.output_dir_edit.text().strip() or str(Path.cwd() / "outputs")

    def espeak_command(self) -> str:
        return self.espeak_command_edit.text().strip() or DEFAULT_ESPEAK_COMMAND

    def chunk_long_text(self) -> bool:
        return self.chunk_checkbox.isChecked()

    def max_chunk_chars(self) -> int:
        return self.chunk_chars_spin.value()

    def append_log(self, message: str) -> None:
        self.log_view.append(message.rstrip())

    def _build_general_section(self) -> SettingsSection:
        section = SettingsSection("Preferencias gerais")
        self.file_pattern_edit = QLineEdit("vocalis_audio.wav")
        section.form.addRow("Nome padrao", self.file_pattern_edit)

        self.output_dir_edit = QLineEdit(str(Path.cwd() / "outputs"))
        section.form.addRow("Pasta padrao", self._path_row(self.output_dir_edit, self._browse_output_dir))

        self.export_format_combo = QComboBox()
        self.export_format_combo.addItems(["WAV", "MP3", "OGG"])
        section.form.addRow("Formato", self.export_format_combo)

        language_combo = QComboBox()
        language_combo.addItems(["pt_BR"])
        section.form.addRow("Idioma padrao", language_combo)

        default_voice_combo = QComboBox()
        for voice_id, label in KOKORO_VOICES.items():
            default_voice_combo.addItem(f"{voice_id} - {label}", voice_id)
        section.form.addRow("Voz padrao", default_voice_combo)
        return section

    def _build_audio_section(self) -> SettingsSection:
        section = SettingsSection("Configuracoes de audio")
        quality_combo = QComboBox()
        quality_combo.addItems(["Alta", "Media", "Rascunho"])
        section.form.addRow("Qualidade", quality_combo)

        sample_combo = QComboBox()
        sample_combo.addItems([f"{KOKORO_SAMPLE_RATE} Hz", "44100 Hz", "48000 Hz"])
        section.form.addRow("Taxa", sample_combo)

        normalization = QCheckBox("Normalizar volume")
        normalization.setChecked(True)
        section.form.addRow("", normalization)

        remove_silence = QCheckBox("Remover silencio excessivo")
        section.form.addRow("", remove_silence)

        volume = QSlider(Qt.Horizontal)
        volume.setRange(0, 100)
        volume.setValue(82)
        section.form.addRow("Volume padrao", volume)
        return section

    def _build_generation_section(self) -> SettingsSection:
        section = SettingsSection("Configuracoes de geracao")
        model_edit = QLineEdit(KOKORO_REPO_ID)
        model_edit.setReadOnly(True)
        section.form.addRow("Modelo", model_edit)

        speed = QDoubleSpinBox()
        speed.setRange(0.5, 2.0)
        speed.setSingleStep(0.05)
        speed.setValue(1.0)
        section.form.addRow("Velocidade padrao", speed)

        stability = QSlider(Qt.Horizontal)
        stability.setRange(0, 100)
        stability.setValue(72)
        section.form.addRow("Estabilidade", stability)

        similarity = QSlider(Qt.Horizontal)
        similarity.setRange(0, 100)
        similarity.setValue(68)
        section.form.addRow("Similaridade", similarity)

        self.chunk_checkbox = QCheckBox("Dividir textos longos")
        self.chunk_checkbox.setChecked(True)
        section.form.addRow("", self.chunk_checkbox)

        self.chunk_chars_spin = QSpinBox()
        self.chunk_chars_spin.setRange(120, 1800)
        self.chunk_chars_spin.setSingleStep(50)
        self.chunk_chars_spin.setValue(DEFAULT_MAX_CHUNK_CHARS)
        section.form.addRow("Limite por trecho", self.chunk_chars_spin)
        return section

    def _build_technical_section(self) -> SettingsSection:
        section = SettingsSection("Configuracoes tecnicas")
        self.espeak_command_edit = QLineEdit(find_espeak_command() or DEFAULT_ESPEAK_COMMAND)
        section.form.addRow("espeak-ng", self._path_row(self.espeak_command_edit, self._browse_espeak))

        api_key = QLineEdit()
        api_key.setPlaceholderText("Opcional para futuras integracoes")
        api_key.setEchoMode(QLineEdit.Password)
        section.form.addRow("Chave de API", api_key)

        endpoint = QLineEdit("local://kokoro")
        section.form.addRow("Endpoint", endpoint)

        timeout = QSpinBox()
        timeout.setRange(5, 180)
        timeout.setValue(60)
        section.form.addRow("Timeout (s)", timeout)

        logs = QCheckBox("Registrar logs de geracao")
        logs.setChecked(True)
        section.form.addRow("", logs)

        test_button = QPushButton("Testar conexao local")
        test_button.setIcon(professional_icon(test_button, "fa5s.plug", QStyle.SP_DialogApplyButton))
        test_button.clicked.connect(self.test_requested.emit)
        section.form.addRow("", test_button)
        return section

    def _build_appearance_section(self) -> SettingsSection:
        section = SettingsSection("Aparencia")
        theme = QComboBox()
        theme.addItems(["Claro", "Escuro futuro", "Sistema"])
        section.form.addRow("Tema", theme)

        density = QComboBox()
        density.addItems(["Confortavel", "Compacta"])
        section.form.addRow("Densidade", density)

        ui_language = QComboBox()
        ui_language.addItems(["Portugues", "English futuro"])
        section.form.addRow("Idioma da interface", ui_language)
        return section

    def _build_logs_section(self) -> QGroupBox:
        group = QGroupBox("Logs de geracao")
        group.setObjectName("SettingsSection")
        layout = QVBoxLayout(group)
        self.log_view = QTextEdit()
        self.log_view.setReadOnly(True)
        self.log_view.setPlaceholderText("Eventos de download, carga do modelo e geracao aparecem aqui.")
        layout.addWidget(self.log_view)
        return group

    def _path_row(self, line_edit: QLineEdit, browse_callback) -> QWidget:
        row = QWidget()
        layout = QHBoxLayout(row)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)
        browse_button = QPushButton()
        browse_button.setObjectName("FlatIconButton")
        browse_button.setToolTip("Selecionar caminho")
        browse_button.setIcon(professional_icon(browse_button, "fa5s.folder-open", QStyle.SP_DirOpenIcon))
        browse_button.setFixedSize(30, 30)
        browse_button.clicked.connect(browse_callback)
        layout.addWidget(line_edit, 1)
        layout.addWidget(browse_button)
        return row

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


class MiniPlayer(QFrame):
    play_toggled = Signal()
    scrubbed = Signal(int)
    volume_changed = Signal(int)
    download_requested = Signal()
    details_requested = Signal()

    def __init__(self) -> None:
        super().__init__()
        self.setObjectName("MiniPlayer")
        self.setFixedHeight(70)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(14, 8, 14, 8)
        layout.setSpacing(12)

        self.play_button = PlaybackButton()
        self.play_button.clicked.connect(self.play_toggled.emit)
        layout.addWidget(self.play_button)

        info = QVBoxLayout()
        self.title_label = QLabel("Nenhum audio em reproducao")
        self.title_label.setObjectName("MiniPlayerTitle")
        self.meta_label = QLabel("Selecione um audio da biblioteca ou gere um novo preview.")
        self.meta_label.setObjectName("MutedLabel")
        info.addWidget(self.title_label)
        info.addWidget(self.meta_label)
        layout.addLayout(info, 0)

        self.progress = AudioProgressBar(interactive=True)
        self.progress.moved.connect(self.scrubbed.emit)
        layout.addWidget(self.progress, 1)

        self.volume = VolumeControl()
        self.volume.changed.connect(self.volume_changed.emit)
        layout.addWidget(self.volume)

        self.download_button = QPushButton()
        self.download_button.setObjectName("FlatIconButton")
        self.download_button.setToolTip("Baixar ou abrir arquivo")
        self.download_button.setIcon(professional_icon(self.download_button, "fa5s.download", QStyle.SP_DialogSaveButton))
        self.download_button.setFixedSize(30, 30)
        self.download_button.clicked.connect(self.download_requested.emit)
        layout.addWidget(self.download_button)

        self.details_button = QPushButton()
        self.details_button.setObjectName("FlatIconButton")
        self.details_button.setToolTip("Abrir detalhes")
        self.details_button.setIcon(professional_icon(self.details_button, "fa5s.info-circle", QStyle.SP_FileDialogInfoView))
        self.details_button.setFixedSize(30, 30)
        self.details_button.clicked.connect(self.details_requested.emit)
        layout.addWidget(self.details_button)

        self.set_audio(None)

    def set_audio(self, audio: AudioItem | None) -> None:
        enabled = audio is not None
        self.play_button.setEnabled(enabled)
        self.download_button.setEnabled(enabled)
        self.details_button.setEnabled(enabled)
        self.progress.set_interactive(enabled)
        if audio is None:
            self.title_label.setText("Nenhum audio em reproducao")
            self.meta_label.setText("Selecione um audio da biblioteca ou gere um novo preview.")
            self.progress.set_duration(1)
            self.progress.set_position(0)
            self.play_button.set_playing(False)
            return

        self.title_label.setText(audio.title)
        self.meta_label.setText(f"{audio.project} / {audio.folder}  |  {audio.voice}")
        self.progress.set_duration(audio.duration_seconds)
        self.progress.set_position(0)

    def set_playback(self, playing: bool, position: int, duration: int) -> None:
        self.play_button.set_playing(playing)
        self.progress.set_duration(duration)
        self.progress.set_position(position)


class TitleBar(QFrame):
    minimize_requested = Signal()
    maximize_requested = Signal()
    close_requested = Signal()

    def __init__(self) -> None:
        super().__init__()
        self.setObjectName("TitleBar")
        self.setFixedHeight(38)
        self._drag_position = None

        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 0, 8, 0)
        layout.setSpacing(8)

        title = QLabel(APP_NAME)
        title.setObjectName("WindowTitle")
        layout.addWidget(title)
        layout.addStretch(1)

        self.minimize_button = self._window_button("Minimizar", QStyle.SP_TitleBarMinButton)
        self.maximize_button = self._window_button("Maximizar", QStyle.SP_TitleBarMaxButton)
        self.close_button = self._window_button("Fechar", QStyle.SP_TitleBarCloseButton)
        self.minimize_button.clicked.connect(self.minimize_requested.emit)
        self.maximize_button.clicked.connect(self.maximize_requested.emit)
        self.close_button.clicked.connect(self.close_requested.emit)
        layout.addWidget(self.minimize_button)
        layout.addWidget(self.maximize_button)
        layout.addWidget(self.close_button)

    def mousePressEvent(self, event) -> None:  # type: ignore[override]
        if event.button() == Qt.LeftButton:
            self._drag_position = event.globalPosition().toPoint()
            event.accept()

    def mouseMoveEvent(self, event) -> None:  # type: ignore[override]
        if self._drag_position is None or not event.buttons() & Qt.LeftButton:
            return
        window = self.window()
        delta = event.globalPosition().toPoint() - self._drag_position
        window.move(window.pos() + delta)
        self._drag_position = event.globalPosition().toPoint()
        event.accept()

    def mouseDoubleClickEvent(self, event) -> None:  # type: ignore[override]
        if event.button() == Qt.LeftButton:
            self.maximize_requested.emit()

    def _window_button(self, tooltip: str, icon: QStyle.StandardPixmap) -> QPushButton:
        button = QPushButton()
        button.setObjectName("WindowButton")
        button.setToolTip(tooltip)
        icon_name = {
            QStyle.SP_TitleBarMinButton: "fa5s.minus",
            QStyle.SP_TitleBarMaxButton: "fa5s.square",
            QStyle.SP_TitleBarCloseButton: "fa5s.times",
        }.get(icon, "fa5s.circle")
        button.setIcon(professional_icon(button, icon_name, icon, "#334155"))
        button.setFixedSize(30, 28)
        return button


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        if QApplication.instance() is not None:
            QApplication.instance().setApplicationName(APP_NAME)
        self.setWindowTitle(APP_NAME)
        self.setWindowFlag(Qt.FramelessWindowHint, True)
        self.setMinimumSize(1040, 680)
        self._custom_maximized = False
        self._normal_geometry = None
        self._fit_to_available_screen()

        self._engine = KokoroTTSEngine()
        self._thread: QThread | None = None
        self._worker: GenerationWorker | None = None
        self._last_output: Path | None = None
        self._projects, self._audios, self._first_run = load_app_state()
        self._selected_project = self._projects[0].name if self._projects else DEFAULT_PROJECT_NAME
        self._preview_audio: AudioItem | None = None
        self._active_audio: AudioItem | None = None
        self._is_playing = False
        self._playback_position = 0
        self._playback_duration = 1

        self._sim_timer = QTimer(self)
        self._sim_timer.setInterval(1000)
        self._sim_timer.timeout.connect(self._advance_simulated_playback)

        self._media_player = None
        self._audio_output = None
        self._init_media_player()

        self._build_ui()
        self._connect_signals()
        if self._first_run:
            self._append_log(f"Primeira execucao: projeto '{self._selected_project}' e audio de teste criados.")

    def _fit_to_available_screen(self) -> None:
        screen = QApplication.primaryScreen()
        if screen is None:
            self.resize(1280, 760)
            return
        available = screen.availableGeometry()
        width = min(1280, max(1040, int(available.width() * 0.92)))
        height = min(760, max(680, int(available.height() * 0.9)))
        self.resize(width, height)
        self.move(
            available.x() + (available.width() - width) // 2,
            available.y() + (available.height() - height) // 2,
        )

    def _toggle_maximized(self) -> None:
        if self._custom_maximized and self._normal_geometry is not None:
            self.setGeometry(self._normal_geometry)
            self._custom_maximized = False
            return

        screen = QApplication.screenAt(self.frameGeometry().center()) or QApplication.primaryScreen()
        if screen is None:
            return
        self._normal_geometry = self.geometry()
        self.setGeometry(screen.availableGeometry())
        self._custom_maximized = True

    def closeEvent(self, event: QCloseEvent) -> None:
        if self._thread and self._thread.isRunning():
            QMessageBox.warning(
                self,
                "Geracao em andamento",
                "Aguarde a geracao terminar antes de fechar o app.",
            )
            event.ignore()
            return
        save_app_state(self._projects, self._audios)
        event.accept()

    def _build_ui(self) -> None:
        root = QWidget()
        root_layout = QVBoxLayout(root)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)

        self.title_bar = TitleBar()
        root_layout.addWidget(self.title_bar)

        workspace = QFrame()
        workspace.setObjectName("Workspace")
        workspace_layout = QHBoxLayout(workspace)
        workspace_layout.setContentsMargins(0, 0, 0, 0)
        workspace_layout.setSpacing(0)

        self.sidebar = Sidebar(self._projects, self._selected_project)
        workspace_layout.addWidget(self.sidebar)

        shell = QFrame()
        shell.setObjectName("MainShell")
        shell_layout = QVBoxLayout(shell)
        shell_layout.setContentsMargins(0, 0, 0, 0)
        shell_layout.setSpacing(0)

        self.stack = QStackedWidget()
        self.gallery_page = GalleryPage(self._audios, self._selected_project)
        self.create_page = CreateAudioPage(self._projects)
        self.settings_page = SettingsPage()
        self.stack.addWidget(self.gallery_page)
        self.stack.addWidget(self.create_page)
        self.stack.addWidget(self.settings_page)
        shell_layout.addWidget(self.stack, 1)

        self.mini_player = MiniPlayer()
        shell_layout.addWidget(self.mini_player)

        workspace_layout.addWidget(shell, 1)
        root_layout.addWidget(workspace, 1)
        self.setCentralWidget(root)
        self.setStyleSheet(APP_STYLES)

    def _connect_signals(self) -> None:
        self.title_bar.minimize_requested.connect(self.showMinimized)
        self.title_bar.maximize_requested.connect(self._toggle_maximized)
        self.title_bar.close_requested.connect(self.close)

        self.sidebar.page_selected.connect(self._show_page)
        self.sidebar.project_selected.connect(self._select_project)
        self.sidebar.create_project_requested.connect(self._create_project)
        self.sidebar.rename_project_requested.connect(self._rename_project)
        self.sidebar.delete_project_requested.connect(self._delete_project)

        self.gallery_page.new_audio_requested.connect(lambda: self._show_page("create"))
        self.gallery_page.play_audio_requested.connect(self._play_audio_by_id)
        self.gallery_page.download_audio_requested.connect(self._download_audio_by_id)
        self.gallery_page.delete_audio_requested.connect(self._delete_audio_by_id)
        self.gallery_page.move_audio_requested.connect(self._move_audio_by_id)

        self.create_page.generate_requested.connect(self._start_generation)
        self.create_page.preview_requested.connect(self._simulate_preview)
        self.create_page.save_draft_requested.connect(self._save_draft)
        self.create_page.cancel_requested.connect(lambda: self._show_page("gallery"))
        self.create_page.preview_player.play_requested.connect(self._play_audio_by_id)
        self.create_page.preview_player.download_requested.connect(self._download_audio_by_id)
        self.create_page.preview_player.save_requested.connect(self._save_preview_to_gallery)
        self.create_page.preview_player.retry_requested.connect(self._start_generation)
        self.create_page.preview_player.progress.moved.connect(self._seek_playback)
        self.create_page.preview_player.volume.changed.connect(self._set_volume)

        self.settings_page.test_requested.connect(self._test_runtime)

        self.mini_player.play_toggled.connect(self._toggle_playback)
        self.mini_player.scrubbed.connect(self._seek_playback)
        self.mini_player.volume_changed.connect(self._set_volume)
        self.mini_player.download_requested.connect(self._download_active_audio)
        self.mini_player.details_requested.connect(self._show_active_details)

    def _init_media_player(self) -> None:
        if QMediaPlayer is None or QAudioOutput is None:
            return
        self._media_player = QMediaPlayer()
        self._audio_output = QAudioOutput()
        self._audio_output.setVolume(0.82)
        self._media_player.setAudioOutput(self._audio_output)
        self._media_player.positionChanged.connect(self._media_position_changed)
        self._media_player.durationChanged.connect(self._media_duration_changed)

    def _show_page(self, page: str) -> None:
        if page == "create":
            self.stack.setCurrentWidget(self.create_page)
            self.sidebar.set_active("create")
            self.create_page.voice_panel.set_current_project(self._selected_project)
        elif page == "settings":
            self.stack.setCurrentWidget(self.settings_page)
            self.sidebar.set_active("settings")
        else:
            self.stack.setCurrentWidget(self.gallery_page)
            self.gallery_page.set_project(self._selected_project)
            self.sidebar.set_active("library")

    def _select_project(self, project_name: str) -> None:
        self._selected_project = project_name
        self.gallery_page.set_project(project_name)
        self.create_page.voice_panel.set_current_project(project_name)
        self.stack.setCurrentWidget(self.gallery_page)

    def _create_project(self) -> None:
        name, accepted = QInputDialog.getText(self, "Novo projeto", "Nome do projeto:")
        name = name.strip()
        if not accepted or not name:
            return
        if any(project.name.lower() == name.lower() for project in self._projects):
            QMessageBox.warning(self, "Projeto existente", "Ja existe um projeto com esse nome.")
            return

        project = ProjectItem(unique_id("project"), name, 0, date.today().isoformat())
        self._projects.append(project)
        self._selected_project = project.name
        self._sync_project_ui(save=True)
        self._select_project(project.name)

    def _rename_project(self, project_name: str) -> None:
        project = self._project_by_name(project_name)
        if project is None:
            return
        name, accepted = QInputDialog.getText(self, "Renomear projeto", "Novo nome:", text=project.name)
        name = name.strip()
        if not accepted or not name or name == project.name:
            return
        if any(item.name.lower() == name.lower() and item.name != project.name for item in self._projects):
            QMessageBox.warning(self, "Projeto existente", "Ja existe um projeto com esse nome.")
            return

        old_name = project.name
        project.name = name
        for audio in self._audios:
            if audio.project == old_name:
                audio.project = name
        self._selected_project = name
        self._sync_project_ui(save=True)
        self._select_project(name)

    def _delete_project(self, project_name: str) -> None:
        if len(self._projects) <= 1:
            QMessageBox.information(self, "Projeto unico", "Crie outro projeto antes de excluir este.")
            return
        project = self._project_by_name(project_name)
        if project is None:
            return
        project_audio_count = sum(1 for audio in self._audios if audio.project == project.name)
        answer = QMessageBox.question(
            self,
            "Excluir projeto",
            f"Excluir '{project.name}' e remover {project_audio_count} audio(s) da biblioteca?",
        )
        if answer != QMessageBox.Yes:
            return

        self._projects = [item for item in self._projects if item.name != project.name]
        self._audios = [audio for audio in self._audios if audio.project != project.name]
        if self._active_audio and self._active_audio.project == project.name:
            self._active_audio = None
            self._is_playing = False
            self._sim_timer.stop()
            self.mini_player.set_audio(None)
        self._selected_project = self._projects[0].name
        self._sync_project_ui(save=True)
        self._select_project(self._selected_project)

    def _project_by_name(self, project_name: str) -> ProjectItem | None:
        for project in self._projects:
            if project.name == project_name:
                return project
        return None

    def _sync_project_ui(self, *, save: bool = False) -> None:
        self._projects = refresh_project_counts(self._projects, self._audios)
        if not any(project.name == self._selected_project for project in self._projects) and self._projects:
            self._selected_project = self._projects[0].name
        self.sidebar.set_projects(self._projects, self._selected_project)
        self.gallery_page.set_audios(self._audios)
        self.gallery_page.set_project(self._selected_project)
        self.create_page.voice_panel.set_projects(self._projects, self._selected_project)
        if save:
            save_app_state(self._projects, self._audios)

    def _collect_options(self) -> GenerationOptions:
        text = self.create_page.text().strip()
        if not text:
            raise ValueError("Informe um texto para gerar audio.")

        file_name = self.create_page.voice_panel.file_name() or self.settings_page.file_pattern_edit.text().strip()
        if not file_name:
            file_name = "vocalis_audio.wav"
        if not file_name.lower().endswith(".wav"):
            file_name = f"{file_name}.wav"

        output_dir = Path(self.settings_page.output_dir()).expanduser()
        return GenerationOptions(
            text=text,
            output_path=output_dir / file_name,
            espeak_command=self.settings_page.espeak_command(),
            kokoro_voice=self.create_page.voice_panel.selected_voice(),
            kokoro_speed=self.create_page.voice_panel.speed(),
            chunk_long_text=self.settings_page.chunk_long_text(),
            max_chunk_chars=self.settings_page.max_chunk_chars(),
            silence_ms=self.create_page.voice_panel.pause_ms(),
        )

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

    @Slot(object)
    def _generation_finished(self, result: object) -> None:
        if not isinstance(result, GenerationResult):
            self._generation_failed("Resultado inesperado retornado pelo gerador.")
            return

        self._last_output = result.output_path
        duration = wav_duration_seconds(result.output_path) or estimate_duration_seconds(self.create_page.text())
        audio = AudioItem(
            id=f"generated-{len(self._audios) + 1:03d}",
            title=result.output_path.stem.replace("_", " ").strip().title() or "Audio gerado",
            project=self.create_page.voice_panel.project(),
            folder=self.create_page.voice_panel.folder(),
            duration_seconds=duration,
            created_at=date.today().isoformat(),
            voice=result.voice_label,
            status="completed",
            audio_path=result.output_path,
        )
        self._preview_audio = audio
        self._audios.insert(0, audio)
        self._sync_project_ui(save=True)
        self.create_page.show_preview(audio)
        self.create_page.set_status("Concluido", "success")
        self.sidebar.set_runtime_status("Ultimo audio concluido")
        self._append_log(
            f"Concluido: {result.output_path} | {result.sample_rate} Hz | "
            f"{result.chunk_count} trecho(s) | voz {result.voice_label}"
        )
        self._set_running(False)

    @Slot(str)
    def _generation_failed(self, details: str) -> None:
        self._append_log(details)
        self.create_page.set_status("Erro", "danger")
        self.create_page.preview_player.set_error()
        self.sidebar.set_runtime_status("Erro na geracao")
        self._set_running(False)
        QMessageBox.critical(
            self,
            "Falha ao gerar audio",
            "A geracao falhou. Veja os logs em Configuracoes para os detalhes tecnicos.",
        )

    @Slot()
    def _clear_thread_refs(self) -> None:
        self._thread = None
        self._worker = None

    @Slot(str)
    def _append_log(self, message: str) -> None:
        self.settings_page.append_log(message)

    def _set_running(self, running: bool) -> None:
        self.create_page.set_running(running)
        self.sidebar.set_runtime_status("Gerando audio..." if running else "Kokoro pt_BR pronto")

    def _simulate_preview(self) -> None:
        text = self.create_page.text().strip()
        if not text:
            QMessageBox.warning(self, "Texto vazio", "Informe um texto para pre-visualizar.")
            return

        preview_path = app_data_dir() / "audio" / "preview_teste_vocalis.wav"
        ensure_test_audio_file(preview_path)
        audio = AudioItem(
            id="preview-current",
            title="Preview de teste",
            project=self.create_page.voice_panel.project(),
            folder=self.create_page.voice_panel.folder(),
            duration_seconds=wav_duration_seconds(preview_path) or estimate_duration_seconds(text),
            created_at=date.today().isoformat(),
            voice="WAV local de teste",
            status="draft",
            audio_path=preview_path,
        )
        self._preview_audio = audio
        self.create_page.show_preview(audio)
        self.create_page.set_status("Preview pronto", "success")
        self._append_log("Preview de teste criado com um WAV local reproduzivel.")

    def _save_draft(self) -> None:
        text = self.create_page.text().strip()
        if not text:
            QMessageBox.warning(self, "Texto vazio", "Informe um texto antes de salvar o rascunho.")
            return
        self.create_page.set_status("Rascunho salvo", "success")
        self._append_log("Rascunho salvo na sessao atual da interface.")

    def _save_preview_to_gallery(self, audio_id: str) -> None:
        audio = self._find_audio(audio_id)
        if audio is not None:
            QMessageBox.information(self, "Audio salvo", "Este audio ja esta na biblioteca.")
            return
        if self._preview_audio is None:
            return
        saved = AudioItem(
            id=f"draft-{len(self._audios) + 1:03d}",
            title=self._preview_audio.title,
            project=self._preview_audio.project,
            folder=self._preview_audio.folder,
            duration_seconds=self._preview_audio.duration_seconds,
            created_at=self._preview_audio.created_at,
            voice=self._preview_audio.voice,
            status="draft",
            audio_path=self._preview_audio.audio_path,
        )
        self._audios.insert(0, saved)
        self._sync_project_ui(save=True)
        self._append_log(f"Preview salvo na biblioteca como {saved.title}.")

    def _play_audio_by_id(self, audio_id: str) -> None:
        audio = self._find_audio(audio_id)
        if audio is None and self._preview_audio and self._preview_audio.id == audio_id:
            audio = self._preview_audio
        if audio is None:
            return

        if self._active_audio and self._active_audio.id == audio.id:
            self._toggle_playback()
            return

        self._active_audio = audio
        self._playback_position = 0
        self._playback_duration = max(1, audio.duration_seconds)
        self.mini_player.set_audio(audio)
        self._start_playback_for_active()

    def _start_playback_for_active(self) -> None:
        if self._active_audio is None:
            return

        self._sim_timer.stop()
        if self._media_player is not None:
            self._media_player.stop()
        if self._media_player is not None and self._active_audio.audio_path and self._active_audio.audio_path.exists():
            self._media_player.setSource(QUrl.fromLocalFile(str(self._active_audio.audio_path)))
            self._media_player.play()
        else:
            self._sim_timer.start()
        self._is_playing = True
        self._refresh_playback_widgets()

    def _toggle_playback(self) -> None:
        if self._active_audio is None:
            return

        if self._is_playing:
            if self._media_player is not None:
                self._media_player.pause()
            self._sim_timer.stop()
            self._is_playing = False
        else:
            if self._playback_position >= self._playback_duration:
                self._playback_position = 0
            if self._media_player is not None and self._active_audio.audio_path and self._active_audio.audio_path.exists():
                self._media_player.play()
            else:
                self._sim_timer.start()
            self._is_playing = True
        self._refresh_playback_widgets()

    def _seek_playback(self, seconds: int) -> None:
        if self._active_audio is None:
            return
        self._playback_position = max(0, min(seconds, self._playback_duration))
        if self._media_player is not None and self._active_audio.audio_path and self._active_audio.audio_path.exists():
            self._media_player.setPosition(self._playback_position * 1000)
        self._refresh_playback_widgets()

    def _set_volume(self, volume: int) -> None:
        if self._audio_output is not None:
            self._audio_output.setVolume(max(0.0, min(1.0, volume / 100)))

    def _advance_simulated_playback(self) -> None:
        if not self._is_playing or self._active_audio is None:
            return
        self._playback_position += 1
        if self._playback_position >= self._playback_duration:
            self._playback_position = self._playback_duration
            self._sim_timer.stop()
            self._is_playing = False
        self._refresh_playback_widgets()

    @Slot(int)
    def _media_position_changed(self, position_ms: int) -> None:
        if self._active_audio is None:
            return
        self._playback_position = max(0, position_ms // 1000)
        if self._playback_position >= self._playback_duration and self._playback_duration > 1:
            self._is_playing = False
        self._refresh_playback_widgets()

    @Slot(int)
    def _media_duration_changed(self, duration_ms: int) -> None:
        if self._active_audio is None or duration_ms <= 0:
            return
        self._playback_duration = max(1, duration_ms // 1000)
        self._active_audio.duration_seconds = self._playback_duration
        self._refresh_playback_widgets()

    def _refresh_playback_widgets(self) -> None:
        audio_id = self._active_audio.id if self._active_audio else None
        duration = max(1, self._playback_duration)
        self.gallery_page.set_playback(audio_id, self._is_playing, self._playback_position, duration)
        self.create_page.preview_player.set_playback(audio_id, self._is_playing, self._playback_position, duration)
        self.mini_player.set_playback(self._is_playing, self._playback_position, duration)

    def _find_audio(self, audio_id: str) -> AudioItem | None:
        for audio in self._audios:
            if audio.id == audio_id:
                return audio
        return None

    def _download_audio_by_id(self, audio_id: str) -> None:
        audio = self._find_audio(audio_id)
        if audio is None and self._preview_audio and self._preview_audio.id == audio_id:
            audio = self._preview_audio
        if audio is None:
            return
        if audio.audio_path and audio.audio_path.exists():
            open_path(audio.audio_path)
        else:
            QMessageBox.information(
                self,
                "Arquivo indisponivel",
                "Este item nao tem um arquivo local associado. Gere um audio para criar um WAV reproduzivel.",
            )

    def _download_active_audio(self) -> None:
        if self._active_audio:
            self._download_audio_by_id(self._active_audio.id)

    def _show_active_details(self) -> None:
        if not self._active_audio:
            return
        QMessageBox.information(
            self,
            "Detalhes do audio",
            (
                f"{self._active_audio.title}\n"
                f"Projeto: {self._active_audio.project}\n"
                f"Pasta: {self._active_audio.folder}\n"
                f"Duracao: {self._active_audio.duration_label}\n"
                f"Voz: {self._active_audio.voice}"
            ),
        )

    def _delete_audio_by_id(self, audio_id: str) -> None:
        audio = self._find_audio(audio_id)
        if audio is None:
            return
        answer = QMessageBox.question(
            self,
            "Excluir audio",
            f"Excluir '{audio.title}' da biblioteca desta sessao?",
        )
        if answer != QMessageBox.Yes:
            return
        self._audios = [item for item in self._audios if item.id != audio_id]
        if self._active_audio and self._active_audio.id == audio_id:
            self._active_audio = None
            self._is_playing = False
            self._sim_timer.stop()
            self.mini_player.set_audio(None)
        self._sync_project_ui(save=True)

    def _move_audio_by_id(self, audio_id: str) -> None:
        audio = self._find_audio(audio_id)
        if audio is None:
            return
        folders = FOLDERS[1:]
        current_index = folders.index(audio.folder) if audio.folder in folders else 0
        audio.folder = folders[(current_index + 1) % len(folders)]
        self._sync_project_ui(save=True)
        self._append_log(f"Audio '{audio.title}' movido para a pasta {audio.folder}.")

    def _test_runtime(self) -> None:
        espeak = find_espeak_command(self.settings_page.espeak_command())
        if espeak:
            self._append_log(f"Runtime local OK. espeak-ng encontrado em: {espeak}")
            QMessageBox.information(self, "Teste concluido", "Runtime local encontrado.")
            return
        self._append_log("Teste de runtime falhou: espeak-ng nao encontrado.")
        QMessageBox.warning(self, "Teste falhou", "Nao encontrei o espeak-ng no caminho configurado.")

def app_data_dir() -> Path:
    configured = os.environ.get("VOCALIS_DATA_DIR", "").strip() or os.environ.get("FALALOCAL_DATA_DIR", "").strip()
    if configured:
        return Path(configured).expanduser()
    return platform_app_data_dir(APP_NAME, APP_SLUG)


def legacy_app_data_dir() -> Path:
    return platform_app_data_dir(LEGACY_APP_NAME, LEGACY_APP_SLUG)


def platform_app_data_dir(app_name: str, app_slug: str) -> Path:
    if sys.platform.startswith("win"):
        root = os.environ.get("APPDATA") or str(Path.home() / "AppData" / "Roaming")
        return Path(root) / app_name
    if sys.platform == "darwin":
        return Path.home() / "Library" / "Application Support" / app_name
    return Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local" / "share")) / app_slug


def state_file_path() -> Path:
    state_path = app_data_dir() / "state.json"
    if data_dir_overridden():
        return state_path
    legacy_state_path = legacy_app_data_dir() / "state.json"
    if not state_path.exists() and legacy_state_path.exists():
        return legacy_state_path
    return state_path


def data_dir_overridden() -> bool:
    return bool(os.environ.get("VOCALIS_DATA_DIR", "").strip() or os.environ.get("FALALOCAL_DATA_DIR", "").strip())


def unique_id(prefix: str) -> str:
    return f"{prefix}-{uuid.uuid4().hex[:10]}"


def load_app_state() -> tuple[list[ProjectItem], list[AudioItem], bool]:
    state_path = state_file_path()
    if not state_path.exists():
        projects, audios = create_first_run_state()
        save_app_state(projects, audios)
        return projects, audios, True

    try:
        data = json.loads(state_path.read_text(encoding="utf-8"))
        projects = [
            ProjectItem.from_dict(project)
            for project in data.get("projects", [])
            if isinstance(project, dict)
        ]
        audios = functional_audios([
            AudioItem.from_dict(audio)
            for audio in data.get("audios", [])
            if isinstance(audio, dict)
        ])
    except Exception:
        projects, audios = create_first_run_state()
        save_app_state(projects, audios)
        return projects, audios, True

    if not projects:
        projects = [ProjectItem(unique_id("project"), DEFAULT_PROJECT_NAME, 0, date.today().isoformat())]
    projects = refresh_project_counts(projects, audios)
    save_app_state(projects, audios)
    return projects, audios, False


def functional_audios(audios: list[AudioItem]) -> list[AudioItem]:
    return [
        audio
        for audio in audios
        if audio.audio_path is not None
        and audio.audio_path.exists()
        and wav_duration_seconds(audio.audio_path) > 0
    ]


def create_first_run_state() -> tuple[list[ProjectItem], list[AudioItem]]:
    data_dir = app_data_dir()
    audio_dir = data_dir / "audio"
    audio_dir.mkdir(parents=True, exist_ok=True)
    test_audio_path = audio_dir / TEST_AUDIO_FILE_NAME
    ensure_test_audio_file(test_audio_path)

    project = ProjectItem(
        id=unique_id("project"),
        name=DEFAULT_PROJECT_NAME,
        total_audios=1,
        last_updated=date.today().isoformat(),
    )
    audio = AudioItem(
        id=unique_id("audio"),
        title="Audio de teste",
        project=project.name,
        folder=DEFAULT_FOLDER_NAME,
        duration_seconds=wav_duration_seconds(test_audio_path) or 4,
        created_at=date.today().isoformat(),
        voice="Arquivo WAV local",
        status="completed",
        audio_path=test_audio_path,
    )
    return [project], [audio]


def save_app_state(projects: list[ProjectItem], audios: list[AudioItem]) -> None:
    state_path = app_data_dir() / "state.json"
    state_path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "version": APP_STATE_VERSION,
        "projects": [project.to_dict() for project in projects],
        "audios": [audio.to_dict() for audio in audios],
    }
    state_path.write_text(json.dumps(payload, ensure_ascii=True, indent=2), encoding="utf-8")


def refresh_project_counts(projects: list[ProjectItem], audios: list[AudioItem]) -> list[ProjectItem]:
    existing_by_name = {project.name: project for project in projects}
    project_names = [project.name for project in projects]
    for audio in audios:
        if audio.project not in existing_by_name:
            project = ProjectItem(unique_id("project"), audio.project, 0, audio.created_at)
            existing_by_name[audio.project] = project
            project_names.append(audio.project)

    refreshed: list[ProjectItem] = []
    for name in project_names:
        project = existing_by_name[name]
        project_audios = [audio for audio in audios if audio.project == name]
        project.total_audios = len(project_audios)
        project.last_updated = max((audio.created_at for audio in project_audios), default=project.last_updated)
        refreshed.append(project)
    return refreshed


def ensure_test_audio_file(path: Path) -> None:
    if path.exists() and wav_duration_seconds(path) > 0:
        return

    path.parent.mkdir(parents=True, exist_ok=True)
    sample_rate = KOKORO_SAMPLE_RATE
    duration_seconds = 4
    total_frames = sample_rate * duration_seconds
    amplitude = 0.32
    frequencies = (392.0, 493.88, 587.33)

    with wave.open(str(path), "wb") as wav_file:
        wav_file.setnchannels(1)
        wav_file.setsampwidth(2)
        wav_file.setframerate(sample_rate)
        frames = bytearray()
        for index in range(total_frames):
            t = index / sample_rate
            freq = frequencies[min(len(frequencies) - 1, int(t))]
            envelope = min(1.0, index / (sample_rate * 0.08), (total_frames - index) / (sample_rate * 0.12))
            sample = int(32767 * amplitude * envelope * math.sin(2 * math.pi * freq * t))
            frames.extend(sample.to_bytes(2, byteorder="little", signed=True))
        wav_file.writeframes(bytes(frames))


def clear_layout(layout: QHBoxLayout | QVBoxLayout) -> None:
    while layout.count():
        item = layout.takeAt(0)
        widget = item.widget()
        child_layout = item.layout()
        if widget is not None:
            widget.deleteLater()
        elif child_layout is not None:
            clear_layout(child_layout)  # type: ignore[arg-type]


def refresh_style(widget: QWidget) -> None:
    widget.style().unpolish(widget)
    widget.style().polish(widget)
    widget.update()


def professional_icon(
    widget: QWidget,
    name: str,
    fallback: QStyle.StandardPixmap,
    color: str = "#334155",
):
    if qta is not None:
        try:
            return qta.icon(name, color=color)
        except Exception:
            pass
    return widget.style().standardIcon(fallback)


def format_seconds(seconds: int) -> str:
    seconds = max(0, seconds)
    minutes, remainder = divmod(seconds, 60)
    hours, minutes = divmod(minutes, 60)
    if hours:
        return f"{hours:02d}:{minutes:02d}:{remainder:02d}"
    return f"{minutes:02d}:{remainder:02d}"


def estimate_duration_seconds(text: str) -> int:
    words = max(1, len(text.split()))
    return max(8, int(words / 2.55))


def wav_duration_seconds(path: Path) -> int:
    try:
        with wave.open(str(path), "rb") as wav_file:
            frames = wav_file.getnframes()
            rate = wav_file.getframerate()
            if rate <= 0:
                return 0
            return max(1, round(frames / rate))
    except Exception:
        return 0


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
    color: #1e293b;
}

/* =========================
   BASE
========================= */

QMainWindow,
QFrame#MainShell,
QFrame#Workspace {
    background: #f8fafc;
}

QFrame#TitleBar {
    background: #ffffff;
    border-bottom: 1px solid #e2e8f0;
}

QLabel#WindowTitle {
    color: #334155;
    font-size: 12px;
    font-weight: 700;
}

QPushButton#WindowButton {
    background: transparent;
    border: 0;
    border-radius: 6px;
    padding: 3px;
}

QPushButton#WindowButton:hover {
    background: #f1f5f9;
}

/* =========================
   SIDEBAR LIGHT
========================= */

QFrame#Sidebar {
    background: #ffffff;
    border: 1px solid #e2e8f0;
}

QLabel#LogoMark {
    background: #2563eb;
    color: #ffffff;
    border-radius: 10px;
    min-width: 38px;
    min-height: 38px;
    font-size: 15px;
    font-weight: 800;
    qproperty-alignment: AlignCenter;
}

QLabel#SidebarTitle {
    color: #0f172a;
    font-size: 18px;
    font-weight: 800;
}

QLabel#SidebarSubtitle {
    color: #64748b;
    font-size: 11px;
}

QLabel#SidebarSectionLabel {
    color: #64748b;
    font-size: 11px;
    font-weight: 800;
}

QFrame#SidebarPanel {
    background: #f8fafc;
    border: 1px solid #e2e8f0;
    border-radius: 12px;
}

QLabel#SidebarPanelTitle {
    color: #0f172a;
    font-weight: 700;
}

/* =========================
   BOTÕES DA SIDEBAR
========================= */

QPushButton#SidebarButton {
    background: transparent;
    color: #334155;
    border: 1px solid transparent;
    border-radius: 10px;
    padding: 10px 12px;
    text-align: left;
    font-weight: 600;
}

QPushButton#SidebarButton:hover {
    background: #f1f5f9;
    color: #0f172a;
    border-color: #e2e8f0;
}

QPushButton#SidebarButton:checked {
    background: #eff6ff;
    color: #1d4ed8;
    border-color: #bfdbfe;
    font-weight: 800;
}

QPushButton#SidebarPrimaryButton {
    background: #2563eb;
    border: 1px solid #2563eb;
    border-radius: 10px;
    color: #ffffff;
    font-weight: 800;
    padding: 10px 12px;
    text-align: left;
}

QPushButton#SidebarPrimaryButton:hover,
QPushButton#SidebarPrimaryButton[active="true"] {
    background: #1d4ed8;
    border-color: #1d4ed8;
}

QPushButton#SidebarPrimaryButton:pressed {
    background: #1e40af;
    border-color: #1e40af;
}

QPushButton#SidebarIconButton {
    background: transparent;
    border: 1px solid transparent;
    border-radius: 8px;
    padding: 4px;
}

QPushButton#SidebarIconButton:hover {
    background: #f1f5f9;
    border-color: #cbd5e1;
}

QPushButton#SidebarIconButton:disabled {
    background: transparent;
    border-color: transparent;
}

/* =========================
   PROJETOS NA SIDEBAR
========================= */

QScrollArea#SidebarProjectScroll {
    border: 0;
    background: transparent;
}

QPushButton#SidebarProjectButton {
    background: #f1f5f9;
    color: #1e293b;
    border: 1px solid #dbe4ee;
    border-radius: 10px;
    padding: 9px 10px;
    text-align: left;
    font-weight: 650;
}

QPushButton#SidebarProjectButton:hover {
    background: #eef6ff;
    color: #1d4ed8;
    border-color: #bfdbfe;
}

QPushButton#SidebarProjectButton:pressed {
    background: #dbeafe;
    color: #1e40af;
    border-color: #93c5fd;
}

QPushButton#SidebarProjectButton:checked {
    background: #2563eb;
    border-color: #2563eb;
    color: #ffffff;
    font-weight: 800;
}

/* =========================
   TEXTOS
========================= */

QLabel#PageTitle {
    color: #0f172a;
    font-size: 24px;
    font-weight: 800;
}

QLabel#SectionTitle {
    color: #111827;
    font-size: 15px;
    font-weight: 700;
}

QLabel#CardTitle {
    color: #111827;
    font-size: 14px;
    font-weight: 700;
}

QLabel#MutedLabel {
    color: #64748b;
}

QLabel#TinyMutedLabel {
    color: #748094;
    font-size: 11px;
}

/* =========================
   PAINÉIS / CARDS
========================= */

QFrame#Panel,
QFrame#PreviewPlayer {
    background: #ffffff;
    border: 1px solid #e2e8f0;
    border-radius: 12px;
}

QFrame#MetricCard {
    background: #ffffff;
    border: 1px solid #e2e8f0;
    border-radius: 12px;
}

QFrame#MetricCard:hover,
QFrame#AudioCard:hover {
    border-color: #bfdbfe;
    background: #fbfdff;
}

QLabel#MetricValue {
    color: #0f172a;
    font-size: 23px;
    font-weight: 800;
}

QFrame#AudioCard {
    background: #ffffff;
    border: 1px solid #e2e8f0;
    border-radius: 12px;
}

QFrame#AudioCard[active="true"] {
    border: 1px solid #3b82f6;
    background: #eff6ff;
}

/* =========================
   BOTÕES GERAIS
========================= */

QPushButton {
    background: #ffffff;
    border: 1px solid #cbd5e1;
    border-radius: 9px;
    padding: 8px 12px;
    color: #1e293b;
}

QPushButton:hover {
    background: #f8fafc;
    border-color: #94a3b8;
}

QPushButton:pressed {
    background: #e2e8f0;
}

QPushButton:disabled {
    color: #94a3b8;
    background: #f1f5f9;
    border-color: #e2e8f0;
}

QPushButton#PrimaryButton {
    background: #2563eb;
    border-color: #2563eb;
    color: #ffffff;
    font-weight: 800;
    padding: 9px 16px;
}

QPushButton#PrimaryButton:hover {
    background: #1d4ed8;
    border-color: #1d4ed8;
}

QPushButton#PrimaryButton:pressed {
    background: #1e40af;
    border-color: #1e40af;
}

QPushButton#IconButton {
    background: #eff6ff;
    border: 1px solid #bfdbfe;
    border-radius: 9px;
    padding: 0;
}

QPushButton#IconButton:hover {
    background: #dbeafe;
    border-color: #93c5fd;
}

QPushButton#FlatIconButton {
    background: transparent;
    border: 1px solid transparent;
    border-radius: 8px;
    padding: 4px;
}

QPushButton#FlatIconButton:hover {
    background: #f1f5f9;
    border-color: #e2e8f0;
}

/* =========================
   BADGES
========================= */

QLabel#StatusBadge {
    border-radius: 10px;
    padding: 5px 10px;
    font-size: 11px;
    font-weight: 700;
}

QLabel#StatusBadge[tone="neutral"] {
    background: #f1f5f9;
    color: #475569;
}

QLabel#StatusBadge[tone="success"] {
    background: #dcfce7;
    color: #166534;
}

QLabel#StatusBadge[tone="warning"] {
    background: #fef3c7;
    color: #92400e;
}

QLabel#StatusBadge[tone="danger"] {
    background: #fee2e2;
    color: #991b1b;
}

QLabel#DurationPill {
    background: #eef2ff;
    color: #3730a3;
    border-radius: 10px;
    padding: 4px 9px;
    font-weight: 700;
}

/* =========================
   CAMPOS
========================= */

QLineEdit,
QPlainTextEdit,
QTextEdit,
QComboBox,
QSpinBox,
QDoubleSpinBox {
    background: #ffffff;
    border: 1px solid #cbd5e1;
    border-radius: 9px;
    padding: 8px;
    color: #1e293b;
    selection-background-color: #2563eb;
    selection-color: #ffffff;
}

QLineEdit:hover,
QPlainTextEdit:hover,
QTextEdit:hover,
QComboBox:hover,
QSpinBox:hover,
QDoubleSpinBox:hover {
    border-color: #94a3b8;
}

QLineEdit:focus,
QPlainTextEdit:focus,
QTextEdit:focus,
QComboBox:focus,
QSpinBox:focus,
QDoubleSpinBox:focus {
    border: 1px solid #3b82f6;
    background: #ffffff;
}

QLineEdit#SearchInput {
    padding: 10px 12px;
    border-radius: 10px;
}

QComboBox#CompactInput {
    min-width: 132px;
}

QPlainTextEdit#LargeTextEdit {
    font-size: 14px;
}

/* =========================
   CONFIGURAÇÕES
========================= */

QGroupBox#SettingsSection {
    background: #ffffff;
    border: 1px solid #e2e8f0;
    border-radius: 12px;
    margin-top: 14px;
    padding: 13px;
    font-weight: 700;
    color: #111827;
}

QGroupBox#SettingsSection::title {
    subcontrol-origin: margin;
    left: 12px;
    padding: 0 6px;
    color: #334155;
}

QScrollArea#ScrollArea {
    border: 0;
    background: transparent;
}

/* =========================
   SLIDER / PROGRESSO
========================= */

QSlider::groove:horizontal {
    height: 5px;
    background: #dbe4ee;
    border-radius: 3px;
}

QSlider::handle:horizontal {
    width: 16px;
    height: 16px;
    margin: -6px 0;
    background: #2563eb;
    border: 2px solid #ffffff;
    border-radius: 8px;
}

QSlider::handle:horizontal:hover {
    background: #1d4ed8;
}

QProgressBar {
    border: 1px solid #e2e8f0;
    border-radius: 5px;
    background: #ffffff;
    height: 9px;
    text-align: center;
}

QProgressBar::chunk {
    background: #22c55e;
    border-radius: 5px;
}

/* =========================
   EMPTY STATE
========================= */

QFrame#EmptyState {
    background: #ffffff;
    border: 1px dashed #cbd5e1;
    border-radius: 12px;
}

QLabel#EmptyTitle {
    color: #111827;
    font-size: 16px;
    font-weight: 800;
}

/* =========================
   MINI PLAYER
========================= */

QFrame#MiniPlayer {
    background: #ffffff;
    border-top: 1px solid #e2e8f0;
}

QLabel#MiniPlayerTitle {
    color: #111827;
    font-size: 14px;
    font-weight: 800;
}
"""


def main() -> int:
    app = QApplication(sys.argv)
    app.setApplicationName(APP_NAME)
    window = MainWindow()
    window.show()
    return app.exec()
