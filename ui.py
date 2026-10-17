"""
ui.py — listBuddy MainWindow
Layout: header-bar (title + controls) → two-column body
  Left  : playlist cards
  Right : output preview (groups + scrollable file list)
  Footer: player · destination · export · progress (footer.py)
"""
from __future__ import annotations

import itertools
import logging
import os
import sys
import time
from io import BytesIO
from functools import partial
from pathlib import Path
from collections.abc import Iterator
from typing import Any, Callable, Literal
from xml.etree import ElementTree as ET

from shiboken6 import isValid
from PySide6.QtCore import (
    QEvent, QEventLoop, QPoint, QSize, QThread, Qt, QTimer, QUrl, QSettings,
    QPropertyAnimation, QEasingCurve,
)
from PySide6.QtGui import (
    QAction,
    QDesktopServices,
    QImage,
    QIcon,
    QKeySequence,
    QMouseEvent,
    QPixmap,
    QShortcut,
)
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QDialog,
    QFileDialog,
    QGraphicsOpacityEffect,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMenu,
    QPlainTextEdit,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)
from PySide6.QtMultimedia import QMediaDevices

import rekordbox_xml
from app_paths import default_settings_path, make_private
from db import key_bpm_of
from about_dialog import (
    AboutDialog,
    FirstRunNoticeDialog,
    disclaimer_dialog,
    disclaimer_pending,
    mark_disclaimer_accepted,
)
import dialogs
from audio_formats import NOT_PLAYABLE_MESSAGE, is_playable_audio
import icons
from branding import APP_NAME
from preview_card import (
    CHIP_W, IDX_W, KEYBPM_W, ROW_GAP, ROW_HEIGHT, WARN_W, PreviewGroupCard,
)
from row_blocks import ALL_BROKEN, NONE, block_positions, broken_notice_text, ext_chip_text, format_key_bpm
from playlist_filter import matches
from styles import apply_title_tracking, status_style, token
from worker import DestinationCheck, ExportWorker, folder_names_by_playlist
from ui_components import (
    ClickableLabel,
    WrapLabel,
    FileRow,
    MaintenanceButton,
    PlaylistCard,
    PlaylistGroup,
    RelocateDialog,
    RestoreBackupDialog,
    TitleBar,
)
from preview_worker import ExistenceRecheckWorker, PlayResolveWorker, PreviewWorker, GroupData, TrackRow
from library_load_worker import LibraryLoadResult, LibraryLoadWorker
from audio_player import AudioPlayer
from footer import FooterBar
from waveform_worker import WaveData, WaveformWorker
from rekordbox_fixes import FixStore, fixes_path_for
from rekordbox_xml_relocate import RekordboxXmlRelocateWorker
from relocate_core import BackupInfo, RelocateScope, RestoreBackupWorker, list_backups
from traktor_relocate import RelocateWorker, is_traktor_running
from update_checker import UpdateCheckWorker, UpdateInfo, safe_release_url

_logger = logging.getLogger("listBuddy")
_KOFI_URL = "https://ko-fi.com/gabrielmaglia"
# Va en cada confirmación antes de escribir sobre una librería (DISCLAIMER.md §3-4).
_RESPONSIBILITY_LINE = (
    f"Lo hacés bajo tu responsabilidad: {APP_NAME} no se hace cargo de pérdidas "
    "o daños en tu librería (Ayuda → Aviso legal). Tené tu propia copia de "
    "seguridad."
)
_APP_VERSION = "1.0.0"

# T-016: header/frameless custom, retoma T-010 (revertido, ver D-06 en
# engram/03_backlog.md) con un mecanismo seguro. T-010 crasheaba el proceso
# entero porque nativeEvent() leía un MSG nativo de Windows a mano con
# ctypes.wintypes.MSG.from_address() (access violation en el primer show(),
# sin excepción de Python atrapable). Esta vez el resize por bordes usa
# EXCLUSIVAMENTE self.windowHandle().startSystemResize(edge) — API de alto
# nivel de Qt6 que delega el resize al SO — disparado desde grips de resize
# en Python puro (_ResizeGrip más abajo). Prohibido: ctypes, ctypes.wintypes,
# nativeEvent(), MSG.from_address() o cualquier lectura de puntero/struct
# nativo de Windows.
_IS_WINDOWS = sys.platform == "win32"
_RESIZE_MARGIN = 7  # px de margen sensible a resize en los bordes de la ventana frameless


class _ResizeGrip(QWidget):
    """
    Grip invisible (sin pintar nada propio) usado en los bordes/esquinas de
    la ventana frameless en Windows para permitir resize manual. Al hacer
    click, delega el resize entero al sistema operativo vía
    `QWindow.startSystemResize()` — no hay lectura de memoria ni structs
    nativos de ningún tipo, es la API pública de Qt6 para este caso (T-016,
    reemplaza el `nativeEvent()`+ctypes de T-010 revertido, ver D-06).
    """

    def __init__(self, edges: Qt.Edge, cursor: Qt.CursorShape, parent: QWidget) -> None:
        super().__init__(parent)
        self._edges = edges
        self.setCursor(cursor)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)

    def mousePressEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            win = self.window()
            handle = win.windowHandle() if win is not None else None
            if handle is not None and not win.isMaximized():
                handle.startSystemResize(self._edges)
                event.accept()
                return
        super().mousePressEvent(event)


# ─────────────────────────────────────────────── Donation dialog ──────────

class DonationDialog(QDialog):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("donation_dialog")
        self.setWindowTitle(f"Apoyar — {APP_NAME}")
        self.setFixedSize(310, 400)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(28, 24, 28, 24)
        layout.setSpacing(14)

        title = QLabel(f"¿Te sirvió {APP_NAME}?")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setObjectName("dialog_title")
        apply_title_tracking(title, 17)
        layout.addWidget(title)

        sub = QLabel("Podés invitarme un café en Ko-fi.\nContribución 100 % voluntaria.")
        sub.setAlignment(Qt.AlignmentFlag.AlignCenter)
        sub.setWordWrap(True)
        layout.addWidget(sub)

        qr_label = QLabel()
        qr_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        px = self._make_qr()
        if px:
            qr_label.setPixmap(px)
        else:
            qr_label.setText(_KOFI_URL)
        layout.addWidget(qr_label)

        kofi_btn = QPushButton("☕  Abrir Ko-fi")
        kofi_btn.setObjectName("kofi_btn")
        kofi_btn.clicked.connect(lambda: QDesktopServices.openUrl(QUrl(_KOFI_URL)))
        layout.addWidget(kofi_btn)

        close_btn = QPushButton("Cerrar")
        close_btn.setObjectName("close_dialog_btn")
        close_btn.clicked.connect(self.accept)
        layout.addWidget(close_btn)

    @staticmethod
    def _make_qr() -> QPixmap | None:
        # qrcode solo aporta la matriz de módulos (sin Pillow): se pinta con Qt.
        try:
            import qrcode  # type: ignore

            qr = qrcode.QRCode(border=2)
            qr.add_data(_KOFI_URL)
            qr.make(fit=True)
            matrix = qr.get_matrix()
            n = len(matrix)
            img = QImage(n, n, QImage.Format.Format_RGB32)
            for y, row in enumerate(matrix):
                for x, dark in enumerate(row):
                    img.setPixel(x, y, 0xFF000000 if dark else 0xFFFFFFFF)
            return QPixmap.fromImage(img).scaled(
                180, 180,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.FastTransformation,
            )
        except Exception:
            return None


# ─────────────────────────────────────────────────── MainWindow ──────────

class MainWindow(QMainWindow):
    def __init__(self, settings_path: Path | None = None) -> None:
        super().__init__()
        self.setWindowTitle(APP_NAME)
        # T-016: frameless + chrome propio, solo Windows. macOS conserva el
        # frame nativo (sin tocar) — ver nota de compatibilidad en
        # TitleBar/_build_header. Resize por bordes vía _ResizeGrip
        # (startSystemResize(), sin ctypes — ver comentario de módulo y D-06).
        if _IS_WINDOWS:
            self.setWindowFlags(self.windowFlags() | Qt.WindowType.FramelessWindowHint)
        self.resize(980, 700)
        self.setMinimumSize(820, 560)
        self.setObjectName("rb_main")

        self._grips: list[_ResizeGrip] = []

        self._db = None
        self._load_worker: LibraryLoadWorker | None = None   # T-094: lectura de la librería en curso
        self._load_generation = 0                            # descarta resultados de cargas reemplazadas
        self._keep_after_load: set[Any] = set()              # playlists a re-marcar al terminar
        self._worker: ExportWorker | None = None
        self._all_cards: list[PlaylistCard] = []
        self._groups: list[PlaylistGroup] = []
        self._source: str = "rekordbox"  # "rekordbox" | "traktor"
        self._preview_worker: PreviewWorker | None = None   # el último lanzado
        self._preview_workers: list[PreviewWorker] = []      # T-106: uno por lote de extracción
        # T-106 (TEC-23): trabajo por lotes con presupuesto de tiempo por tick del event loop.
        self._mark_queue: list[PlaylistCard] = []            # «Marcar todas» pendiente
        self._status_sub: QLabel | None = None               # detalle de la tarjeta de estado (progreso)
        self._loading_detail = ""
        self._scroll_to_restore: int | None = None           # scroll a devolver tras un recheck
        self._populate_job: Iterator[None] | None = None     # poblado del árbol en curso
        self._populate_on_done: Callable[[], None] | None = None
        self._mark_value = True
        self._feed_queue: list[PlaylistCard] = []            # tarjetas por extraer para la previa
        self._feed_order: dict[PlaylistCard, int] = {}
        self._feed_folders: dict[PlaylistCard, str] = {}
        self._relocate_worker: RelocateWorker | None = None
        self._relocate_source: str = "rekordbox"  # fuente activa al arrancar el relocate en curso
        # I-1: progreso conocido del relocate en curso (último valor de la
        # signal `progress`) — usado para decidir si hace falta confirmar
        # antes de cancelar/cerrar (¿hay trabajo ya hecho que se perdería?).
        self._relocate_progress_done: int = 0
        self._relocate_progress_total: int = 0

        # B-4 (T-019): worker de restauración de backup — un solo campo,
        # igual patrón que _relocate_worker (nunca dos restores a la vez).
        self._restore_worker: RestoreBackupWorker | None = None

        # T-021 (I-8): chequeo de actualización, aviso discreto (nunca modal).
        self._update_worker: UpdateCheckWorker | None = None
        self._update_url: str = ""

        # ── Audio playback ───────────────────────────────────────────────
        self._audio = AudioPlayer(self)
        self._audio.playing_changed.connect(self._on_playing_changed)
        self._audio.error.connect(self._on_audio_error)
        self._audio.position_changed.connect(self._on_position_changed)
        self._audio.track_finished.connect(self._on_track_finished)
        self._playing_path: str = ""        # raw_path del track sonando
        self._is_playing: bool = False
        # (widget, ícono, token de color, tamaño): se re-tiñen al cambiar de tema
        self._themed_icons: list[tuple[QWidget, str, str, int]] = []
        self._playing_row: FileRow | None = None

        # ── Forma de onda del footer ─────────────────────────────────────
        self._wave_worker: WaveformWorker | None = None
        self._wave_gen: int = 0
        self._wave_cache: dict[str, WaveData] = {}
        # Cancelados pero con el hilo aún vivo: se sueltan en su `finished`.
        self._live_wave_workers: set[WaveformWorker] = set()
        self._live_threads: set[QThread] = set()  # T-088: hilos retenidos hasta su finished

        self._export_state: Literal["idle", "running", "cancelling"] = "idle"
        self._last_export_dest: str = ""
        self._dest_check: DestinationCheck | None = None
        self._status_before_check = ""
        self._closing = False   # cerrar invalida lo que llegue en cola (chequeo de destino, resolución de ruta)
        self._play_gen = 0

        # Cache de metadata de tracks: evita re-queries SQLAlchemy (N+1 problem)
        # key: "<source>:<playlist_name>"  value: list[TrackRow] sin exists flags
        self._track_meta_cache: dict[str, list[TrackRow]] = {}

        # Cache de existencia de archivos: evita stat() repetido (lento en USB/red)
        # key: raw_path  value: bool
        self._exists_cache: dict[str, bool] = {}
        self._last_exists_check = time.monotonic()   # TEC-18
        self._recheck_worker: ExistenceRecheckWorker | None = None

        # Debounce: 80ms sin cambios antes de disparar el preview
        self._preview_debounce = QTimer()
        self._preview_debounce.setSingleShot(True)
        self._preview_debounce.setInterval(80)
        self._preview_debounce.timeout.connect(self._start_preview_worker)

        # Cola de grupos pendientes de render + generation counter
        self._render_queue: list[GroupData] = []
        # Grupos ya dibujados: el cambio de tema los re-encola (T-070).
        self._rendered_groups: list[GroupData] = []
        self._broken_total: int = 0
        # Tarjetas vivas de la vista previa por playlist del árbol (T-089): tildar/destildar
        # agrega o quita solo la afectada en vez de reconstruir todo.
        self._preview_cards: dict[object, PreviewGroupCard] = {}

        settings_path = settings_path or default_settings_path()
        make_private(Path(settings_path), create=True)  # SEC-11: lleva rutas de la librería
        self.settings = QSettings(str(settings_path), QSettings.Format.IniFormat)
        self._fixes_store = FixStore(fixes_path_for(Path(self.settings.fileName())))
        self._theme = str(self.settings.value("theme", "dark"))
        from ui_components import PlaylistCard as _PC
        _PC.set_theme(self._theme)

        # ── Configuración persistida ─────────────────────────────────────
        self._rb_xml_path = str(self.settings.value("rb_xml_path", "") or "")
        self._tk_collection_path = str(self.settings.value("tk_collection_path", "") or "")
        self._auto_advance = self.settings.value("auto_advance", True, type=bool)
        self._check_updates = self.settings.value("check_updates_on_start", True, type=bool)
        self._saved_device_id = str(self.settings.value("audio_device_id", "") or "")
        self._media_devices = QMediaDevices(self)
        self._media_devices.audioOutputsChanged.connect(self._refresh_audio_devices)

        central = QWidget()
        central.setObjectName("central_widget")
        central.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        root_layout = QVBoxLayout(central)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)

        root_layout.addWidget(self._build_header())
        root_layout.addWidget(self._build_update_strip())

        self._stack = QStackedWidget()
        self._stack.addWidget(self._build_body())             # 0 = principal
        self._stack.addWidget(self._build_settings_page())    # 1 = configuración
        root_layout.addWidget(self._stack, 1)
        root_layout.addWidget(self._build_footer())

        self.setCentralWidget(central)
        if _IS_WINDOWS:
            self._create_resize_grips()

        # Minimal menu
        view_menu = self.menuBar().addMenu("Ver")
        self.theme_action = QAction("Tema claro", self)
        self.theme_action.setCheckable(True)
        self.theme_action.setChecked(self._theme == "light")
        self.theme_action.triggered.connect(
            lambda checked: self._apply_theme("light" if checked else "dark")
        )
        view_menu.addAction(self.theme_action)
        self._reload_action = QAction("Recargar librería", self)
        self._reload_action.setShortcut(QKeySequence("Ctrl+R"))
        self._reload_action.triggered.connect(self._reload_library)
        view_menu.addAction(self._reload_action)
        help_menu = self.menuBar().addMenu("Ayuda")
        help_menu.addAction("☕  Donar en Ko-fi…").triggered.connect(self._show_donation)
        # AboutRole: en macOS Qt lo muda al menú de la app, donde se lo espera.
        help_menu.addAction("Aviso legal…").triggered.connect(
            lambda: disclaimer_dialog(self).exec()
        )
        about_action = help_menu.addAction(f"Acerca de {APP_NAME}…")
        about_action.setMenuRole(QAction.MenuRole.AboutRole)
        about_action.triggered.connect(self._show_about)

        from styles import load_qss
        app = QApplication.instance()
        if app:
            app.setStyleSheet(load_qss(self._theme))
        self._sync_theme_toggle(self._theme)
        self._sync_source_buttons()
        QTimer.singleShot(0, self._fit_header)  # el ancho final llega tras el show
        self._footer.apply_theme(self._theme)

        self._apply_saved_audio_device()
        last_dest = str(self.settings.value("last_dest_folder", "") or "")
        if last_dest:
            self._footer.set_dest(last_dest)

        self._load_playlists()

        self._space_shortcut = QShortcut(QKeySequence(Qt.Key.Key_Space), self)
        self._space_shortcut.activated.connect(self._on_space)

        self._start_update_check()
        # Después del show: el aviso legal sale sobre la ventana, no antes.
        QTimer.singleShot(0, self._maybe_show_disclaimer)

    def _maybe_show_disclaimer(self) -> None:
        """Aviso legal resumido al primer arranque y cuando cambia su versión."""
        if not disclaimer_pending(self.settings):
            return
        dlg = FirstRunNoticeDialog(self._theme, self)
        dlg.accepted.connect(lambda: mark_disclaimer_accepted(self.settings))
        dlg.open()

    # Seam de test: BOOT reemplaza `_maybe_show_disclaimer` por un no-op para
    # que ningún diálogo aparezca en los tests; los que lo prueban usan este alias.
    _maybe_show_disclaimer_real = _maybe_show_disclaimer

    # ──────────────────────────────────────── Widget builders ────────────

    def _build_update_strip(self) -> QWidget:
        """T-021 (I-8): aviso de actualización en franja propia bajo el header (D2)."""
        strip = QWidget()
        strip.setObjectName("update_strip")
        strip.setFixedHeight(28)
        strip.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        lo = QHBoxLayout(strip)
        lo.setContentsMargins(20, 0, 20, 0)
        self._update_banner = ClickableLabel("")
        self._update_banner.setObjectName("update_banner")
        self._update_banner.setToolTip("Ver la nueva versión en GitHub")
        self._update_banner.clicked.connect(self._open_update_link)
        lo.addWidget(self._update_banner)
        lo.addStretch(1)
        strip.setVisible(False)
        self._update_strip = strip
        return strip

    def _build_header(self) -> QWidget:
        """
        Title bar: listBuddy + EXPORT ENGINE eyebrow · now-playing center ·
        controls right. T-016: en Windows, además de la UI de la app, esta
        barra ES el chrome de ventana (frameless) — TitleBar agrega
        drag-to-move + doble click maximiza/restaura, y se le suman los
        botones propios de minimizar/maximizar/cerrar al final de la fila.
        En macOS la ventana conserva el frame nativo (no se agregan los
        botones winctl_*) — ver `_IS_WINDOWS`.
        """
        bar = TitleBar()
        bar.setObjectName("header_bar")
        bar.setFixedHeight(56)
        bar.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self._header_bar = bar
        lo = QHBoxLayout(bar)
        lo.setContentsMargins(20, 0, 20, 0)
        lo.setSpacing(12)  # T2: con 20 px el header no entra a 820 px

        # ── Izquierda: marca única + selector de fuente ──────────────────
        brand = QWidget()
        brand.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        bl = QHBoxLayout(brand)
        bl.setContentsMargins(0, 0, 0, 0)
        bl.setSpacing(10)
        logo = QLabel()
        self._tint_icon(logo, "logo", "accent", 22)
        title_lbl = QLabel(APP_NAME)
        title_lbl.setObjectName("header_title")
        apply_title_tracking(title_lbl, 20)
        bl.addWidget(logo)
        bl.addWidget(title_lbl)
        lo.addWidget(brand)
        lo.addWidget(self._build_source_switcher())

        lo.addStretch(1)

        # ── Derecha: controles ───────────────────────────────────────────
        self._maint_btn = MaintenanceButton()
        self._tint_icon(self._maint_btn.icon_label(), "wrench", "text", 16)
        lo.addWidget(self._maint_btn)
        self._build_maintenance_menu()

        self._settings_btn = QPushButton()
        self._tint_icon(self._settings_btn, "gear", "muted", 16)
        self._settings_btn.setObjectName("settings_btn")
        self._settings_btn.setToolTip("Configuración")
        self._settings_btn.setAccessibleName("Configuración")
        self._settings_btn.setCheckable(True)
        self._settings_btn.clicked.connect(self._toggle_settings)

        self._theme_btn = QPushButton()
        self._theme_btn.setObjectName("theme_btn")
        self._theme_btn.setToolTip("Cambiar tema")
        self._theme_btn.setAccessibleName("Cambiar tema")
        self._theme_btn.clicked.connect(
            lambda: self._apply_theme("light" if self._theme == "dark" else "dark")
        )

        self._donate_btn = QPushButton(" Apoyar")
        self._tint_icon(self._donate_btn, "heart", "muted", 15)
        self._donate_btn.setObjectName("donate_btn")
        self._donate_btn.clicked.connect(self._show_donation)
        lo.addWidget(self._settings_btn)
        lo.addWidget(self._theme_btn)
        lo.addWidget(self._donate_btn)

        # T-016: botones propios de minimizar/maximizar/cerrar — solo en
        # Windows, donde la ventana es frameless y el frame nativo (que
        # traía estos controles) fue reemplazado. QSS ya define
        # winctl_group/winctl_min/winctl_max/winctl_close (qss/dark.qss,
        # qss/light.qss) desde T-010, quedaron sin usar tras el revert.
        if _IS_WINDOWS:
            winctl = QWidget()
            winctl.setObjectName("winctl_group")
            w_lo = QHBoxLayout(winctl)
            w_lo.setContentsMargins(0, 0, 0, 0)
            w_lo.setSpacing(0)
            self._min_btn = QPushButton("─")
            self._min_btn.setObjectName("winctl_min")
            self._min_btn.setToolTip("Minimizar")
            self._min_btn.setCursor(Qt.CursorShape.ArrowCursor)
            self._min_btn.clicked.connect(self.showMinimized)
            self._max_btn = QPushButton("□")
            self._max_btn.setObjectName("winctl_max")
            self._max_btn.setToolTip("Maximizar/restaurar")
            self._max_btn.setCursor(Qt.CursorShape.ArrowCursor)
            self._max_btn.clicked.connect(self._toggle_maximize_restore)
            self._close_btn = QPushButton()
            self._tint_icon(self._close_btn, "close", "muted", 14)
            self._close_btn.setObjectName("winctl_close")
            self._close_btn.setToolTip("Cerrar")
            self._close_btn.setCursor(Qt.CursorShape.ArrowCursor)
            self._close_btn.clicked.connect(self.close)
            w_lo.addWidget(self._min_btn)
            w_lo.addWidget(self._max_btn)
            w_lo.addWidget(self._close_btn)
            lo.addWidget(winctl)

        return bar

    def _toggle_maximize_restore(self) -> None:
        """Conectado a winctl_max (T-016) y reusado por TitleBar.mouseDoubleClickEvent."""
        if self.isMaximized():
            self.showNormal()
        else:
            self.showMaximized()

    # ── Resize por bordes (T-016, sin ctypes — ver D-06) ───────────────────
    # `_ResizeGrip` (definido a nivel de módulo) es la única pieza nueva:
    # widgets finitos superpuestos en los bordes/esquinas que, al click,
    # llaman self.windowHandle().startSystemResize(edge). Nada de esto lee
    # memoria ni structs nativos — es la API pública de QWindow.

    def _create_resize_grips(self) -> None:
        specs = [
            (Qt.Edge.TopEdge | Qt.Edge.LeftEdge, Qt.CursorShape.SizeFDiagCursor),
            (Qt.Edge.TopEdge | Qt.Edge.RightEdge, Qt.CursorShape.SizeBDiagCursor),
            (Qt.Edge.BottomEdge | Qt.Edge.LeftEdge, Qt.CursorShape.SizeBDiagCursor),
            (Qt.Edge.BottomEdge | Qt.Edge.RightEdge, Qt.CursorShape.SizeFDiagCursor),
            (Qt.Edge.TopEdge, Qt.CursorShape.SizeVerCursor),
            (Qt.Edge.BottomEdge, Qt.CursorShape.SizeVerCursor),
            (Qt.Edge.LeftEdge, Qt.CursorShape.SizeHorCursor),
            (Qt.Edge.RightEdge, Qt.CursorShape.SizeHorCursor),
        ]
        central = self.centralWidget()
        self._grips = [_ResizeGrip(edges, cursor, central) for edges, cursor in specs]
        self._reposition_grips()
        for grip in self._grips:
            grip.show()
            grip.raise_()

    def _reposition_grips(self) -> None:
        if not self._grips:
            return
        central = self.centralWidget()
        m = _RESIZE_MARGIN
        w, h = central.width(), central.height()
        tl, tr, bl, br, top, bottom, left, right = self._grips
        tl.setGeometry(0, 0, m, m)
        tr.setGeometry(max(0, w - m), 0, m, m)
        bl.setGeometry(0, max(0, h - m), m, m)
        br.setGeometry(max(0, w - m), max(0, h - m), m, m)
        top.setGeometry(m, 0, max(0, w - 2 * m), m)
        bottom.setGeometry(m, max(0, h - m), max(0, w - 2 * m), m)
        left.setGeometry(0, m, m, max(0, h - 2 * m))
        right.setGeometry(max(0, w - m), m, m, max(0, h - 2 * m))

    def _fit_header(self) -> None:
        """Si el header no entra a lo ancho, Mantenimiento y Apoyar quedan en solo ícono (D3)."""
        bar = self._header_bar
        self._set_header_compact(False)  # medir siempre contra el ancho completo
        bar.layout().invalidate()
        self._set_header_compact(bar.layout().sizeHint().width() > bar.width())
        self._maint_btn.layout().activate()  # su sizeHint sale de este layout interno
        bar.layout().invalidate()
        bar.layout().activate()  # aplicar ya la geometría nueva (sin esperar al próximo evento)

    def _set_header_compact(self, compact: bool) -> None:
        self._maint_btn.set_compact(compact)
        self._donate_btn.setText("" if compact else " Apoyar")
        self._donate_btn.setToolTip("Apoyar" if compact else "")
        self._donate_btn.setAccessibleName("Apoyar")

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        if hasattr(self, "_donate_btn"):  # puede llegar antes de armar el header
            self._fit_header()
        if self._grips:
            self._reposition_grips()
            for grip in self._grips:
                grip.raise_()

    def _build_body(self) -> QWidget:
        body = QWidget()
        body.setObjectName("body_widget")
        body.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        lo = QHBoxLayout(body)
        lo.setContentsMargins(0, 0, 0, 0)
        lo.setSpacing(0)
        lo.addWidget(self._build_left_col())
        lo.addWidget(self._build_right_col(), 1)
        return body

    # ── Left column ──────────────────────────────────────────────────────

    def _build_left_col(self) -> QWidget:
        col = QWidget()
        col.setObjectName("left_col")
        col.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        col.setFixedWidth(320)
        lo = QVBoxLayout(col)
        lo.setContentsMargins(0, 0, 0, 0)
        lo.setSpacing(0)

        lo.addWidget(self._build_playlists_header())
        help_lbl = QLabel("Marcá las que querés exportar")
        help_lbl.setObjectName("playlists_help")
        lo.addWidget(help_lbl)
        lo.addWidget(self._build_playlist_search())
        self._no_results = QLabel("")
        self._no_results.setObjectName("playlist_no_results")
        self._no_results.setVisible(False)
        lo.addWidget(self._no_results)
        lo.addWidget(self._build_playlist_scroll(), 1)
        return col

    def _build_footer(self) -> QWidget:
        f = FooterBar()
        f.play_clicked.connect(self._audio.toggle)
        f.seek_requested.connect(self._audio.seek)
        f.change_dest_clicked.connect(self._choose_folder)
        f.dest_changed.connect(self._on_path_changed)
        f.export_clicked.connect(self._on_export_clicked)
        f.finder_clicked.connect(self._open_dest_in_finder)
        f.apply_theme(self._theme)
        self._footer = f
        return f

    def _build_source_switcher(self) -> QWidget:
        """Segmented control: Rekordbox | Traktor."""
        wrap = QWidget()
        wrap.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        wrap.setObjectName("source_switcher")
        wrap.setFixedHeight(36)  # 30 del botón + 2 de margen + 1 de borde por lado
        lo = QHBoxLayout(wrap)
        lo.setContentsMargins(2, 2, 2, 2)
        lo.setSpacing(0)

        self._src_rb_btn = QPushButton("Rekordbox")
        self._src_rb_btn.setObjectName("source_btn_rb")
        self._src_rb_btn.setProperty("src_active", "true")
        self._src_rb_btn.clicked.connect(lambda: self._switch_source("rekordbox"))

        self._src_tk_btn = QPushButton("Traktor")
        self._src_tk_btn.setObjectName("source_btn_tk")
        self._src_tk_btn.setProperty("src_active", "false")
        self._src_tk_btn.clicked.connect(lambda: self._switch_source("traktor"))

        lo.addWidget(self._src_rb_btn, 1)
        lo.addWidget(self._src_tk_btn, 1)
        return wrap

    def _sync_source_buttons(self) -> None:
        """Marca el botón activo (propiedad + punto ámbar); el inactivo lleva un
        ícono transparente del mismo tamaño para que el ancho no salte."""
        accent = token(self._theme, "accent")
        for btn, src in ((self._src_rb_btn, "rekordbox"), (self._src_tk_btn, "traktor")):
            active = self._source == src
            btn.setProperty("src_active", "true" if active else "false")
            if active:
                btn.setIcon(icons.icon("dot", accent, 10))
            else:
                blank = QPixmap(10, 10)
                blank.fill(Qt.GlobalColor.transparent)
                btn.setIcon(QIcon(blank))
            btn.setIconSize(QSize(10, 10))
            btn.style().unpolish(btn)
            btn.style().polish(btn)

    def _build_maintenance_menu(self) -> None:
        """Menú del botón Mantenimiento (D-08: sale de la columna de 344 px)."""
        menu = QMenu(self)
        menu.setToolTipsVisible(True)
        self._act_relocate = menu.addAction("Reparar enlaces rotos…")
        self._act_relocate.triggered.connect(self._on_relocate_action)
        self._act_restore = menu.addAction("Restaurar copia de seguridad…")
        self._act_restore.triggered.connect(self._open_restore_backup_dialog)
        self._act_forget_fixes = menu.addAction("Olvidar reparaciones de Rekordbox…")
        self._act_forget_fixes.triggered.connect(self._forget_rb_fixes)
        self._act_export_xml = menu.addAction("Exportar XML para Rekordbox…")
        self._act_export_xml.triggered.connect(self._export_rb_xml)
        menu.addSeparator()
        self._act_auto = menu.addAction(
            "Resolver automáticamente con la mejor coincidencia"
        )
        self._act_auto.setCheckable(True)
        self._act_auto.setChecked(False)  # D4: siempre apagado al arrancar, no se persiste
        self._act_auto.setToolTip(self._AUTO_TIP_TRAKTOR)
        self._maint_menu = menu
        self._relocate_state: Literal["idle", "running", "cancelling"] = "idle"
        self._maintenance_locked = False  # restauración en curso
        # Popup propio y no setMenu: setMenu agrega un indicador que el diseño no tiene.
        self._maint_btn.clicked.connect(self._show_maintenance_menu)
        self._sync_maintenance_for_source()

    def _show_maintenance_menu(self) -> None:
        self._sync_rb_actions()
        self._maint_menu.popup(
            self._maint_btn.mapToGlobal(QPoint(0, self._maint_btn.height() + 4))
        )

    def _on_relocate_action(self) -> None:
        if self._relocate_state == "idle":
            self._start_relocate()
        elif self._relocate_state == "running":
            self._cancel_relocate()

    def _set_relocate_state(self, state: Literal["idle", "running", "cancelling"]) -> None:
        self._relocate_state = state
        self._sync_busy_locks()
        text, enabled = {
            "idle": ("Reparar enlaces rotos…", True),
            "running": ("Cancelar", True),
            "cancelling": ("Cancelando…", False),
        }[state]
        self._act_relocate.setText(text)
        self._act_relocate.setEnabled(enabled and self._repair_supported())

    def _is_maintenance_busy(self) -> bool:
        """Hay una reparación o una restauración en curso."""
        return (
            getattr(self, "_relocate_state", "idle") != "idle"
            or getattr(self, "_maintenance_locked", False)
        )

    def _sync_busy_locks(self) -> None:
        """Mientras se repara/restaura no se cambia de fuente ni se recarga la librería."""
        free = not self._is_maintenance_busy()
        self._src_rb_btn.setEnabled(free)
        self._src_tk_btn.setEnabled(free)
        self._reload_action.setEnabled(free)
        self._sync_rb_actions()

    def _sync_rb_actions(self) -> None:
        """«Olvidar reparaciones» y «Exportar XML»: solo con Rekordbox, sin tareas en curso."""
        if not hasattr(self, "_act_export_xml"):
            return
        base = (
            self._source == "rekordbox"
            and isinstance(self._db, rekordbox_xml.RekordboxXmlLibrary)
            and not self._is_maintenance_busy()
        )
        self._act_forget_fixes.setEnabled(base and self._fixes_store.count() > 0)
        self._act_export_xml.setEnabled(
            base and any(c.isChecked() for c in self._all_cards)
        )

    def _set_maintenance_enabled(self, enabled: bool) -> None:
        self._maintenance_locked = not enabled
        self._sync_busy_locks()
        ok = enabled and self._repair_supported()
        self._act_relocate.setEnabled(ok)
        self._act_restore.setEnabled(enabled and self._source == "traktor")
        self._sync_rb_actions()

    _AUTO_TIP_BASE = (
        "Con >1 candidato, aplica directo el de mejor score sin mostrar\n"
        "el modal de desambiguación. El log marca cada uno como '(auto)'.\n"
        "Riesgo: un nombre de archivo idéntico para canciones distintas\n"
        "podría auto-resolver al candidato equivocado"
    )
    _AUTO_TIP_TRAKTOR = _AUTO_TIP_BASE + " (backup reversible)."
    _AUTO_TIP_REKORDBOX = (
        _AUTO_TIP_BASE + ".\nCon Rekordbox, las reparaciones se pueden deshacer "
        "con «Olvidar reparaciones de Rekordbox…»."
    )
    _REKORDBOX_RESTORE_HINT = (
        "Con Rekordbox no hay copias: List Buddy no modifica tu XML ni tu librería."
    )

    def _repair_supported(self) -> bool:
        if self._load_worker is not None:
            return False   # sin librería cargada todavía no hay qué reparar
        if self._source == "traktor":
            return True
        return self._source == "rekordbox" and isinstance(
            self._db, rekordbox_xml.RekordboxXmlLibrary
        )

    def _sync_maintenance_for_source(self) -> None:
        ok = self._repair_supported()
        self._act_relocate.setEnabled(ok and self._relocate_state != "cancelling")
        self._act_restore.setEnabled(self._source == "traktor")
        self._act_auto.setEnabled(ok)
        self._update_relocate_tooltip()
        self._sync_rb_actions()

    def _auto_resolve_enabled(self) -> bool:
        return self._act_auto.isChecked()

    def _update_relocate_tooltip(self) -> None:
        """Tooltip del botón de relocate según la fuente activa (Traktor/Rekordbox)."""
        if self._source == "traktor":
            self._act_relocate.setToolTip(
                "Busca los archivos con link roto en una carpeta/disco y repara\n"
                "la colección de Traktor (collection.nml)."
            )
        else:
            self._act_relocate.setToolTip(
                "Busca los archivos que faltan en una carpeta o disco. Las rutas nuevas "
                "se guardan en List Buddy para exportar; tu XML y Rekordbox no se modifican."
            )
        self._act_auto.setToolTip(
            self._AUTO_TIP_TRAKTOR if self._source == "traktor" else self._AUTO_TIP_REKORDBOX
        )
        self._act_restore.setToolTip(
            self._REKORDBOX_RESTORE_HINT if self._source != "traktor" else ""
        )

    def _switch_source(self, source: str) -> None:
        if source == self._source or self._is_maintenance_busy():
            return
        self._source = source
        self._keep_after_load = set()
        self._track_meta_cache.clear()
        self._exists_cache.clear()
        # Update button states
        self._sync_source_buttons()
        self._sync_maintenance_for_source()
        self._load_playlists()

    def _build_playlists_header(self) -> QWidget:
        row = QWidget()
        row.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        rl = QHBoxLayout(row)
        rl.setContentsMargins(16, 16, 12, 4)
        rl.setSpacing(10)

        title = QLabel("Playlists")
        title.setObjectName("playlists_title")
        apply_title_tracking(title, 17)
        rl.addWidget(title)

        self.count_pill = QLabel("0/0")
        self.count_pill.setObjectName("count_pill")
        rl.addWidget(self.count_pill)
        rl.addStretch(1)

        self.all_btn = QPushButton("Todas")
        self.all_btn.setObjectName("all_btn")
        self.all_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.all_btn.clicked.connect(lambda: self._set_all(True, only_visible=True))
        rl.addWidget(self.all_btn)

        self.none_btn = QPushButton("Ninguna")
        self.none_btn.setObjectName("none_btn")
        self.none_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.none_btn.clicked.connect(lambda: self._set_all(False, only_visible=True))
        rl.addWidget(self.none_btn)
        return row

    def _build_playlist_search(self) -> QWidget:
        wrap = QWidget()
        wrap.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        wl = QHBoxLayout(wrap)
        wl.setContentsMargins(12, 0, 12, 8)
        self.playlist_search = QLineEdit()
        self.playlist_search.setObjectName("playlist_search")
        self.playlist_search.setPlaceholderText("Buscar playlist")
        self.playlist_search.setAccessibleName("Buscar playlist")
        self.playlist_search.textChanged.connect(lambda _t: self._apply_filter())
        wl.addWidget(self.playlist_search)
        return wrap

    def _build_playlist_scroll(self) -> QScrollArea:
        scroll = QScrollArea()
        scroll.setObjectName("playlist_scroll")
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        scroll.viewport().setObjectName("playlist_scroll_vp")

        self.playlist_container = QWidget()
        self.playlist_container.setObjectName("scroll_content")
        self.playlist_container_layout = QVBoxLayout(self.playlist_container)
        self.playlist_container_layout.setContentsMargins(8, 0, 8, 8)
        self.playlist_container_layout.setSpacing(2)
        self.playlist_container_layout.addStretch(1)

        scroll.setWidget(self.playlist_container)
        return scroll

    # ── Right column ─────────────────────────────────────────────────────

    def _build_right_col(self) -> QWidget:
        col = QWidget()
        col.setObjectName("right_col")
        col.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        lo = QVBoxLayout(col)
        lo.setContentsMargins(20, 16, 20, 0)
        lo.setSpacing(12)

        # Título + subtítulo + aviso de rotos + estado
        head_row = QWidget()
        head_row.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        hl = QHBoxLayout(head_row)
        hl.setContentsMargins(0, 0, 0, 0)
        hl.setSpacing(8)
        title = QLabel("Vista previa de la salida")
        title.setObjectName("preview_title")
        apply_title_tracking(title, 17)
        sub = QLabel("Así van a quedar las carpetas en el destino")
        sub.setObjectName("preview_subtitle")
        # Subtítulo bajo el título (no en línea como el diseño): en la columna angosta
        # chocaba con el aviso y el estado y se recortaba.
        tb = QVBoxLayout()
        tb.setContentsMargins(0, 0, 0, 0)
        tb.setSpacing(2)
        tb.addWidget(title)
        tb.addWidget(sub)
        hl.addLayout(tb)
        hl.addStretch(1)

        # Aviso «N enlaces rotos»: sigue al total de la vista previa (_set_broken_total).
        self._broken_notice = QWidget()
        self._broken_notice.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        bn = QHBoxLayout(self._broken_notice)
        bn.setContentsMargins(0, 0, 0, 0)
        bn.setSpacing(6)
        bn_icon = QLabel()
        bn_icon.setObjectName("broken_notice_icon")
        self._tint_icon(bn_icon, "warning", "danger", 14)
        self._broken_notice_label = QLabel("")
        self._broken_notice_label.setObjectName("broken_notice_label")
        bn.addWidget(bn_icon)
        bn.addWidget(self._broken_notice_label)
        self._broken_notice.setVisible(False)
        hl.addWidget(self._broken_notice)

        self.output_status = QLabel("en espera")
        self.output_status.setObjectName("output_status_tag")
        hl.addWidget(self.output_status)

        # T-015: "cerrar todas" — reusa _set_all(False), el mismo handler que
        # ya usa el botón "Ninguna" del árbol izquierdo (ui.py _build_playlists_header).
        self.close_all_btn = QPushButton("Cerrar todas")
        self.close_all_btn.setObjectName("close_all_btn")
        self.close_all_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.close_all_btn.setToolTip("Destildar todas las playlists de la cola")
        self.close_all_btn.clicked.connect(lambda: self._set_all(False))
        self.close_all_btn.setVisible(False)
        hl.addWidget(self.close_all_btn)

        lo.addWidget(head_row)

        # Output panel
        panel = QWidget()
        panel.setObjectName("output_panel")
        panel.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        panel_lo = QVBoxLayout(panel)
        panel_lo.setContentsMargins(0, 0, 0, 0)
        panel_lo.setSpacing(0)

        # Preview scroll (idle/selecting)
        self.preview_scroll = QScrollArea()
        self.preview_scroll.setObjectName("preview_scroll")
        self.preview_scroll.setWidgetResizable(True)
        self.preview_scroll.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        )
        self.preview_scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        self.preview_scroll.viewport().setObjectName("preview_scroll_vp")

        self.preview_container = QWidget()
        self.preview_container.setObjectName("preview_container")
        self.preview_layout = QVBoxLayout(self.preview_container)
        self.preview_layout.setContentsMargins(0, 0, 0, 20)
        self.preview_layout.setSpacing(14)
        self.preview_scroll.setWidget(self.preview_container)
        panel_lo.addWidget(self.preview_scroll, 1)

        # Log view (during/after export)
        self.log_view = QPlainTextEdit()
        self.log_view.setObjectName("log_view")
        self.log_view.setReadOnly(True)
        self.log_view.setMaximumBlockCount(5000)   # TEC-09: 40k pistas no dejan un log sin tope
        self.log_view.setVisible(False)
        panel_lo.addWidget(self.log_view, 1)

        lo.addWidget(panel, 1)
        return col

    # ──────────────────────────────────────── Settings page ──────────────

    def _build_settings_page(self) -> QWidget:
        page = QWidget()
        page.setObjectName("settings_page")
        page.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        outer = QVBoxLayout(page)
        outer.setContentsMargins(18, 18, 18, 18)
        outer.setSpacing(14)

        # ── Top bar: volver + título ─────────────────────────────────────
        top = QWidget()
        top.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        tl = QHBoxLayout(top)
        tl.setContentsMargins(0, 0, 0, 0)
        tl.setSpacing(10)
        back = QPushButton("←  Volver")
        back.setObjectName("settings_back")
        back.clicked.connect(lambda: self._toggle_settings(False))
        title = QLabel("Configuración")
        title.setObjectName("settings_title")
        apply_title_tracking(title, 17)
        tl.addWidget(back)
        tl.addWidget(title)
        tl.addStretch(1)
        outer.addWidget(top)

        # ── Scroll con secciones ─────────────────────────────────────────
        scroll = QScrollArea()
        scroll.setObjectName("settings_scroll")
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        scroll.viewport().setObjectName("settings_scroll_vp")

        content = QWidget()
        content.setObjectName("settings_content")
        content.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        cl = QVBoxLayout(content)
        cl.setContentsMargins(0, 0, 0, 0)
        cl.setSpacing(18)

        def section(name: str) -> QVBoxLayout:
            card = QWidget()
            card.setObjectName("settings_card")
            card.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
            box = QVBoxLayout(card)
            box.setContentsMargins(16, 14, 16, 16)
            box.setSpacing(10)
            head = QLabel(name)
            head.setObjectName("settings_section")
            box.addWidget(head)
            cl.addWidget(card)
            return box

        # ── AUDIO ─────────────────────────────────────────────────────────
        audio_box = section("AUDIO")
        dev_label = QLabel("Dispositivo de salida")
        dev_label.setObjectName("settings_label")
        audio_box.addWidget(dev_label)
        self._device_combo = QComboBox()
        self._device_combo.setObjectName("settings_combo")
        self._refresh_audio_devices()
        self._device_combo.currentIndexChanged.connect(self._on_device_changed)
        audio_box.addWidget(self._device_combo)

        # ── REPRODUCCIÓN ───────────────────────────────────────────────────
        play_box = section("REPRODUCCIÓN")
        self._auto_advance_chk = QCheckBox("Auto-avance al siguiente track al terminar")
        self._auto_advance_chk.setObjectName("settings_check")
        self._auto_advance_chk.setChecked(self._auto_advance)
        self._auto_advance_chk.toggled.connect(self._on_auto_advance_toggled)
        play_box.addWidget(self._auto_advance_chk)

        # ── PRIVACIDAD ─────────────────────────────────────────────────────
        privacy_box = section("PRIVACIDAD")
        self._update_check_chk = QCheckBox("Buscar actualizaciones al iniciar")
        self._update_check_chk.setObjectName("settings_check")
        self._update_check_chk.setToolTip(
            "Al abrir la app consulta en GitHub si hay una versión nueva. No envía datos tuyos."
        )
        self._update_check_chk.setChecked(self._check_updates)
        self._update_check_chk.toggled.connect(self._on_check_updates_toggled)
        privacy_box.addWidget(self._update_check_chk)

        # ── LIBRERÍAS ──────────────────────────────────────────────────────
        lib_box = section("LIBRERÍAS")
        helper = QLabel(
            "Traktor se detecta solo. Para Rekordbox elegí el rekordbox.xml que "
            "exportaste desde Rekordbox (Archivo → Exportar colección en formato xml)."
        )
        helper.setObjectName("settings_helper")
        helper.setWordWrap(True)
        lib_box.addWidget(helper)

        self._rb_path_edit = self._add_path_row(
            lib_box, "Rekordbox · rekordbox.xml", self._rb_xml_path,
            self._browse_rb_path, self._clear_rb_path,
            empty_text="(sin elegir)", clear_text="Quitar",
        )
        self._tk_path_edit = self._add_path_row(
            lib_box, "Traktor · collection.nml", self._tk_collection_path,
            self._browse_tk_path, self._clear_tk_path,
        )

        cl.addStretch(1)
        scroll.setWidget(content)
        outer.addWidget(scroll, 1)
        return page

    def _add_path_row(
        self, box, label_text, value, on_browse, on_clear,
        empty_text: str = "(automático)", clear_text: str = "Auto",
    ) -> QLineEdit:
        lbl = QLabel(label_text)
        lbl.setObjectName("settings_label")
        box.addWidget(lbl)
        row = QWidget()
        row.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        rl = QHBoxLayout(row)
        rl.setContentsMargins(0, 0, 0, 0)
        rl.setSpacing(8)
        edit = QLineEdit(value or empty_text)
        edit.setObjectName("settings_path")
        edit.setReadOnly(True)
        rl.addWidget(edit, 1)
        browse = QPushButton("Elegir…")
        browse.setObjectName("settings_path_btn")
        browse.clicked.connect(on_browse)
        rl.addWidget(browse)
        auto = QPushButton(clear_text)
        auto.setObjectName("settings_path_btn")
        auto.clicked.connect(on_clear)
        rl.addWidget(auto)
        box.addWidget(row)
        return edit

    def _toggle_settings(self, show: bool | None = None) -> None:
        if show is None:
            show = self._stack.currentIndex() == 0
        self._stack.setCurrentIndex(1 if show else 0)
        self._settings_btn.setChecked(show)

    # ── Audio device ──────────────────────────────────────────────────────

    def _refresh_audio_devices(self) -> None:
        if not hasattr(self, "_device_combo"):
            return
        self._devices = QMediaDevices.audioOutputs()
        combo = self._device_combo
        combo.blockSignals(True)
        combo.clear()
        for d in self._devices:
            label = d.description()
            if d.isDefault():
                label += "  ·  predeterminado"
            combo.addItem(label)
        sel = 0
        for i, d in enumerate(self._devices):
            if self._saved_device_id and bytes(d.id()).hex() == self._saved_device_id:
                sel = i
                break
        if self._devices:
            combo.setCurrentIndex(sel)
        combo.blockSignals(False)

    def _apply_saved_audio_device(self) -> None:
        if not self._saved_device_id:
            return
        for d in QMediaDevices.audioOutputs():
            if bytes(d.id()).hex() == self._saved_device_id:
                self._audio.set_output_device(d)
                return

    def _on_device_changed(self, idx: int) -> None:
        if idx < 0 or idx >= len(self._devices):
            return
        d = self._devices[idx]
        self._audio.set_output_device(d)
        self._saved_device_id = bytes(d.id()).hex()
        self.settings.setValue("audio_device_id", self._saved_device_id)

    # ── Toggles ─────────────────────────────────────────────────────────────

    def _on_auto_advance_toggled(self, checked: bool) -> None:
        self._auto_advance = checked
        self.settings.setValue("auto_advance", checked)

    def _on_check_updates_toggled(self, checked: bool) -> None:
        self._check_updates = checked
        self.settings.setValue("check_updates_on_start", checked)

    # ── Library paths ───────────────────────────────────────────────────────

    def _browse_rb_path(self) -> None:
        f, _ = QFileDialog.getOpenFileName(
            self, "Elegí el rekordbox.xml exportado", "",
            "Rekordbox XML (*.xml);;Todos los archivos (*)",
        )
        if f:
            self._rb_xml_path = f
            self.settings.setValue("rb_xml_path", f)
            self._rb_path_edit.setText(f)
            if self._source == "rekordbox":
                self._reload_after_path_change()

    def _clear_rb_path(self) -> None:
        self._rb_xml_path = ""
        self.settings.setValue("rb_xml_path", "")
        self._rb_path_edit.setText("(sin elegir)")
        if self._source == "rekordbox":
            self._reload_after_path_change()

    def _browse_tk_path(self) -> None:
        f, _ = QFileDialog.getOpenFileName(
            self, "Elegí el collection.nml de Traktor", "",
            "Traktor collection (collection.nml *.nml);;Todos los archivos (*)",
        )
        if f:
            self._tk_collection_path = f
            self.settings.setValue("tk_collection_path", f)
            self._tk_path_edit.setText(f)
            if self._source == "traktor":
                self._reload_after_path_change()

    def _clear_tk_path(self) -> None:
        self._tk_collection_path = ""
        self.settings.setValue("tk_collection_path", "")
        self._tk_path_edit.setText("(automático)")
        if self._source == "traktor":
            self._reload_after_path_change()

    def _reload_library(self) -> None:
        """Ver → Recargar librería: vuelve a leer la fuente activa desde disco."""
        if self._is_maintenance_busy():
            return
        self._reload_after_path_change()

    def _reload_after_path_change(self) -> None:
        """Vuelve a leer la fuente activa; las playlists marcadas se re-marcan al terminar la carga."""
        keep = {self._playlist_cache_key(c.playlist) for c in self._all_cards if c.isChecked()}
        if (self._load_worker is not None or self._populate_job is not None
                or self._populate_on_done is not None):
            # Carga o poblado en curso: las marcas aún no se aplicaron, la pendiente es la última conocida.
            keep |= self._keep_after_load
        if self._mark_value:
            # Re-marcado por lotes a medias: las que faltan marcar también cuentan.
            keep |= {self._playlist_cache_key(c.playlist) for c in self._mark_queue}
        self._clear_preview_layout()   # los datos reparados cambian con las mismas claves
        self._track_meta_cache.clear()
        self._exists_cache.clear()
        self._keep_after_load = keep
        self._load_playlists()

    # ──────────────────────────────────────── Load playlists ─────────────

    def _load_playlists(self) -> None:
        """Lee la fuente activa (Rekordbox o Traktor) en un hilo (T-094).

        Vuelve enseguida con la tarjeta «Cargando librería…»; el resultado llega por
        `_on_library_loaded` / `_on_library_failed`. Una carga nueva cancela la anterior.
        """
        self._cancel_library_load()
        self._clear_playlist_area()
        self._src_rb_btn.setToolTip("")
        self._db = None  # una carga fallida no puede dejar la librería de la otra fuente

        if self._source == "traktor":
            path = Path(self._tk_collection_path) if self._tk_collection_path else None
        else:
            path = Path(self._rb_xml_path) if self._rb_xml_path else None
        worker = LibraryLoadWorker(self._load_generation, self._source, path, self._fixes_store)
        worker.loaded.connect(self._on_library_loaded)
        worker.failed.connect(self._on_library_failed)
        worker.progress.connect(self._on_library_progress)
        self._load_worker = worker
        self._retain_thread(worker)
        self._show_loading()
        self._sync_maintenance_for_source()
        worker.start()

    def _cancel_library_load(self) -> None:
        """Suelta la carga en curso: su resultado ya no se muestra y el hilo termina solo."""
        self._load_generation += 1   # Qt igual entrega lo ya encolado: se descarta por generación
        worker, self._load_worker = self._load_worker, None
        if worker is None:
            return
        worker.loaded.disconnect()
        worker.failed.disconnect()
        worker.progress.disconnect()
        worker.requestInterruption()

    def _on_library_progress(self, token: int, pct: int) -> None:
        sub = self._status_sub
        if token != self._load_generation or sub is None or not isValid(sub):
            return
        sub.setText(f"{self._loading_detail} {pct} %")

    def _on_cancel_load_clicked(self) -> None:
        """Botón «Cancelar» de la tarjeta «Cargando librería…»: suelta la carga y deja la lista vacía."""
        self._cancel_library_load()
        self._keep_after_load = set()
        self._show_status_card(
            "Carga cancelada",
            "Volvé a cargar la librería con Ver → Recargar librería.",
        )
        self._sync_maintenance_for_source()

    def _on_library_loaded(self, result: LibraryLoadResult) -> None:
        if self._closing:
            return
        if result.token != self._load_generation:
            return
        self._load_worker = None
        self._clear_playlist_area()
        self._db = result.db
        if result.source == "traktor":
            from traktor_db import playlist_song_count
            src_label = "Traktor"
        else:
            playlist_song_count = rekordbox_xml.playlist_song_count
            src_label = "Rekordbox"
        self._populate_playlists(
            result.tree, playlist_song_count,
            on_done=partial(self._finish_library_load, result, src_label),
        )

    def _finish_library_load(self, result: LibraryLoadResult, src_label: str) -> None:
        if self._closing:
            return
        if result.token != self._load_generation:
            return
        self._log(f"{len(self._all_cards)} playlist(s) cargada(s) desde {src_label}.")
        if result.source == "rekordbox":
            stamp = f"{self._db.exported_at:%d/%m/%Y %H:%M}"
            self._log(f"XML exportado el {stamp}.")
            self._src_rb_btn.setToolTip(f"XML exportado el {stamp}")
        keep, self._keep_after_load = self._keep_after_load, set()
        if keep:
            # Re-marcar en lotes: cientos de setChecked juntos congelan la ventana (T-106).
            self._mark_queue = [c for c in self._all_cards
                                if self._playlist_cache_key(c.playlist) in keep]
            self._mark_value = True
            self._pump_mark()
        self._sync_maintenance_for_source()

    def _on_library_failed(self, token: int, message: str) -> None:
        if self._closing:
            return
        if token != self._load_generation:
            return
        self._load_worker = None
        self._keep_after_load = set()
        action = None
        if self._source == "rekordbox":
            action = ("Elegir rekordbox.xml…", self._browse_rb_path)
        self._show_not_installed(message, action)
        self._sync_maintenance_for_source()

    # Seam de test: los tests con BOOT reemplazan `_load_playlists` por un no-op
    # y llaman a esta referencia para ejercitar la carga real.
    _load_playlists_real = _load_playlists

    def _populate_playlists(
        self, tree: list[dict], song_count: Callable[[Any], int],
        on_done: Callable[[], None] | None = None,
    ) -> None:
        """Arma carpetas y filas desde el árbol; separado de la carga para testearlo sin DB.

        T-106: en lotes de ≈25 ms con el árbol parcial a la vista (800 playlists de una vez
        congelaban la ventana). El primer lote corre acá mismo, así que un árbol chico queda
        completo al volver; `on_done` corre cuando termina el último lote."""
        self._populate_job = self._populate_steps(tree, song_count)
        self._populate_on_done = on_done
        self._pump_populate()

    def _populate_steps(
        self, tree: list[dict], song_count: Callable[[Any], int],
    ) -> Iterator[None]:
        card_index = 0
        layout = self.playlist_container_layout

        def add_node(node: dict, group: PlaylistGroup | None = None) -> Iterator[None]:
            nonlocal card_index
            pl = node["playlist"]
            if pl.is_folder:
                grp = PlaylistGroup(pl.Name)
                self._groups.append(grp)
                layout.insertWidget(layout.count() - 1, grp)
                yield
                for child in node["children"]:
                    yield from add_node(child, grp)
            else:
                card = PlaylistCard(pl, song_count(pl), index=card_index)
                card.toggled.connect(self._on_card_toggled)
                card_index += 1
                self._all_cards.append(card)
                if group is not None:
                    group.add_card(card)
                else:
                    layout.insertWidget(layout.count() - 1, card)
                card.ensurePolished()   # el pulido de estilos se paga por lote, no de golpe al mostrar
                yield

        for node in tree:
            yield from add_node(node)
        yield from self._filter_steps(100)   # con el contenedor oculto: barato, pero por tandas

    def _pump_populate(self) -> None:
        job = self._populate_job
        if job is None:
            return
        if not isValid(self.playlist_container_layout):
            self._populate_job = None
            return
        deadline = time.perf_counter() + self._BATCH_BUDGET_S
        for _ in job:
            if time.perf_counter() >= deadline:
                # Cada lote hace que Qt re-acomode TODAS las tarjetas ya puestas (O(n) por tick:
                # con 800 ≈ 200 ms). Mientras falte poblar, el contenedor queda oculto.
                self.playlist_container.hide()
                QTimer.singleShot(0, self._pump_populate)
                return
        self._populate_job = None
        if self.playlist_container.isHidden():
            self.playlist_container.show()   # el costo grande del final, solo en su tick
            QTimer.singleShot(0, self._finish_populate)
        else:
            self._finish_populate()

    def _finish_populate(self) -> None:
        if self._populate_job is not None or not isValid(self.playlist_container_layout):
            return   # arrancó otro poblado (o la ventana murió) mientras tanto
        on_done, self._populate_on_done = self._populate_on_done, None
        self._update_order_numbers()
        self._preview_debounce.start()
        if on_done is not None:
            on_done()

    def _apply_filter(self) -> None:
        """Muestra/oculta filas por nombre; solo de vista: no toca marcas, orden ni contador."""
        # Layout y repintado una sola vez al final: mostrar cientos de filas de
        # golpe (al borrar la consulta) costaba ~0,8 s con 300 playlists.
        layout = self.playlist_container_layout
        layout.setEnabled(False)
        self.playlist_container.setUpdatesEnabled(False)
        try:
            for _ in self._filter_steps(0):
                pass
        finally:
            self.playlist_container.setUpdatesEnabled(True)
            layout.setEnabled(True)

    def _filter_steps(self, every: int) -> Iterator[None]:
        """El filtro como generador: cede cada `every` tarjetas (0 = nunca) para repartirlo en ticks."""
        query = self.playlist_search.text()
        active = bool(query.strip())
        for i, card in enumerate(self._all_cards, start=1):
            card.setVisible(matches(card.name, query))
            if every and i % every == 0:
                yield
        for grp in self._groups:
            grp.setVisible(not active or any(not c.isHidden() for c in grp.cards()))
        none_visible = bool(self._all_cards) and all(c.isHidden() for c in self._all_cards)
        self._no_results.setText(f"Sin resultados para «{query.strip()}»")
        self._no_results.setVisible(active and none_visible)

    def _clear_playlist_area(self) -> None:
        self._populate_job = None
        self.playlist_container.show()
        self._mark_queue.clear()
        self._all_cards.clear()
        self._groups.clear()
        layout = self.playlist_container_layout
        # takeAt y no itemAt+setParent(None): sacar el widget por debajo del layout
        # corrompía el heap de PySide6 y reventaba (SIGSEGV) el widget siguiente (T-076).
        # El stretch final (sin widget) se conserva.
        stretch = layout.takeAt(layout.count() - 1) if layout.count() else None
        while layout.count():
            w = layout.takeAt(0).widget()
            if w:
                w.setParent(None)  # type: ignore[arg-type]
        if stretch is not None:
            layout.addItem(stretch)

    def _show_not_installed(
        self, detail: str, action: tuple[str, Callable[[], None]] | None = None,
    ) -> None:
        """Show a friendly 'not installed' placeholder in the playlist area."""
        app_name = "Traktor Pro 3 / 4" if self._source == "traktor" else "Rekordbox"
        self._show_status_card(f"{app_name} no disponible", detail, action)

    def _show_loading(self) -> None:
        """Placeholder mientras el hilo lee la librería (T-094)."""
        if self._source == "traktor":
            detail = "Leyendo la colección de Traktor…"
        else:
            detail = "Leyendo el XML de Rekordbox. Con colecciones grandes puede tardar unos segundos."
        self._loading_detail = detail
        self._show_status_card("Cargando librería…", detail, ("Cancelar", self._on_cancel_load_clicked))

    def _show_status_card(
        self, title_text: str, detail: str,
        action: tuple[str, Callable[[], None]] | None = None,
    ) -> None:
        self._clear_playlist_area()

        card = QWidget()
        card.setObjectName("not_installed_card")
        card.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        cl = QVBoxLayout(card)
        cl.setContentsMargins(18, 20, 18, 20)
        cl.setSpacing(8)
        cl.setAlignment(Qt.AlignmentFlag.AlignCenter)

        icon = QLabel("◇")
        icon.setObjectName("not_installed_icon")
        icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        cl.addWidget(icon)

        title = QLabel(title_text)
        title.setObjectName("not_installed_title")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        cl.addWidget(title)

        sub = WrapLabel(detail)
        self._status_sub = sub
        sub.setObjectName("not_installed_sub")
        sub.setAlignment(Qt.AlignmentFlag.AlignCenter)
        cl.addWidget(sub)

        if action is not None:
            text, slot = action
            btn = QPushButton(text)
            btn.setObjectName("not_installed_btn")
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.clicked.connect(slot)
            cl.addWidget(btn, 0, Qt.AlignmentFlag.AlignCenter)

        self.playlist_container_layout.insertWidget(
            self.playlist_container_layout.count() - 1, card
        )
        self._update_order_numbers()

    # ──────────────────────────────────────── Order tracking ─────────────

    def _on_card_toggled(self, card: PlaylistCard) -> None:
        if card in self._mark_queue:
            self._mark_queue.remove(card)   # el usuario decidió esta: el lote no la pisa
        self._update_order_numbers()

    def _update_order_numbers(self) -> None:
        selectable = sum(1 for c in self._all_cards if not c._empty)
        order = 0
        for position, card in enumerate(self._all_cards, start=1):
            if card.isChecked():
                order += 1
                card.set_numbers(position, order)
            else:
                card.set_numbers(position, None)

        n = order
        self.count_pill.setText(f"{n}/{selectable}")
        self._footer.set_export_count(n)

        if n == 0:
            self.output_status.setText("en espera")
        else:
            self.output_status.setText(
                f"{n} carpeta{'s' if n != 1 else ''} · numeración independiente"
            )
        self.close_all_btn.setVisible(n > 0)

        if hasattr(self, "preview_scroll") and self.preview_scroll.isVisible():
            self._preview_debounce.start()

    # ──────────────────────────────── Output preview (async) ────────────

    # ── Animaciones ──────────────────────────────────────────────────────

    def _animate_fade_in(self, widget: QWidget, duration: int = 180) -> None:
        """Fade-in suave para un widget recién añadido al layout."""
        effect = QGraphicsOpacityEffect(widget)
        effect.setOpacity(0.0)
        widget.setGraphicsEffect(effect)
        anim = QPropertyAnimation(effect, b"opacity", widget)
        anim.setDuration(duration)
        anim.setStartValue(0.0)
        anim.setEndValue(1.0)
        anim.setEasingCurve(QEasingCurve.Type.OutQuart)
        # T-029: guardamos la anim en el propio widget para poder pararla y
        # desconectarla ANTES de deleteLater() si el preview se re-renderiza
        # mientras el fade sigue en vuelo. Sin esto, `finished` dispara
        # 120-180ms después de start() sobre un widget cuyo objeto C++ ya
        # fue destruido -> EXC_BAD_ACCESS nativo (no es un RuntimeError de
        # Python atrapable — reproducido en local: PID crashea con
        # SIGSEGV/139 en <5s de toggles rápidos de playlist, ver
        # scratchpad/repro_t029_real_app.py). Mismo patrón de "soltar la ref
        # antes de que Qt borre el objeto" que ya se usa para _playing_row
        # más abajo.
        widget._fade_anim = anim  # type: ignore[attr-defined]
        # Remover el efecto al terminar para no penalizar el paint
        anim.finished.connect(lambda: self._on_fade_finished(widget))
        anim.start()

    def _on_fade_finished(self, widget: QWidget) -> None:
        widget.setGraphicsEffect(None)
        widget._fade_anim = None  # type: ignore[attr-defined]

    def _stop_fade_anim(self, widget: QWidget) -> None:
        """T-029: para y desconecta el fade-in en vuelo de `widget` (si lo
        tiene) antes de deleteLater(). Debe llamarse en TODO call site que
        pueda borrar un widget devuelto por `_animate_fade_in` mientras su
        animación sigue corriendo — hoy: `loading` (línea ~1465, duration
        120) y `grp` (línea ~1584, duration 180)."""
        anim = getattr(widget, "_fade_anim", None)
        if anim is not None:
            anim.stop()
            try:
                anim.finished.disconnect()
            except TypeError:
                pass  # ya desconectada (p.ej. terminó justo antes de pararla)
            widget._fade_anim = None  # type: ignore[attr-defined]

    # ─────────────────────────────────────────────────────────────────────

    def _set_broken_total(self, n: int) -> None:
        self._broken_total = n
        self._maint_btn.set_broken(n)
        notice = getattr(self, "_broken_notice", None)
        if notice is not None:
            self._broken_notice_label.setText(broken_notice_text(n))
            notice.setVisible(n > 0)
        # El badge cambia el ancho del header: sin re-medir, Sora (más ancha) lo recortaba.
        self._fit_header()

    def _clear_preview_layout(self, immediate: bool = False) -> None:
        """`immediate` destruye ya los widgets (no deleteLater): el cambio de tema
        necesita que no existan cuando Qt re-pulea (T-070)."""
        self._preview_cards.clear()
        self._rendered_groups.clear()
        self._set_broken_total(0)
        self._render_queue.clear()
        # Las filas se destruyen acá (deleteLater); soltar la ref al row sonando
        # para no tocar un objeto C++ borrado en el próximo click (→ abort de Qt).
        self._playing_row = None
        lo = self.preview_layout
        while lo.count():
            item = lo.takeAt(0)
            w = item.widget()
            if w:
                self._stop_fade_anim(w)   # T-029: parar el fade ANTES de borrar
                if immediate:
                    from shiboken6 import delete
                    delete(w)
                else:
                    w.deleteLater()

    def _cancel_preview_worker(self) -> None:
        self._feed_queue = []   # lo que no se alcanzó a extraer se vuelve a pedir
        workers, self._preview_workers = self._preview_workers, []
        if self._preview_worker is not None and self._preview_worker not in workers:
            workers.append(self._preview_worker)
        for worker in workers:
            if worker.isRunning():
                worker.group_ready.disconnect()
                worker.done.disconnect()
                worker.cancel()
                worker.requestInterruption()
                # No se espera: el hilo viejo termina solo (puede estar en un stat
                # lento) y mientras tanto queda retenido, nunca destruido en vuelo.
                self._retain_thread(worker)

    def _retain_thread(self, thread: QThread) -> None:
        """Mantiene vivo el wrapper de un hilo hasta su `finished` real.

        Qt aborta el proceso si se destruye un QThread que sigue corriendo.
        """
        if not isinstance(thread, QThread):
            return
        self._live_threads.add(thread)
        thread.finished.connect(lambda t=thread: self._live_threads.discard(t))

    def _start_preview_worker(self) -> None:
        """Llamado por el debounce timer. Cancela worker anterior, muestra loading, inicia nuevo."""
        self._cancel_preview_worker()

        selected = [c for c in self._all_cards if c.isChecked()]
        if selected and self._preview_cards:
            self._sync_preview_cards(selected)
            return
        self._clear_preview_layout()
        if not selected:
            self._show_preview_empty()
            return

        # Loading placeholder con fade-in suave
        loading = QLabel(f"Cargando {len(selected)} playlist{'s' if len(selected) != 1 else ''}…")
        loading.setObjectName("preview_loading")
        loading.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.preview_layout.addWidget(loading)
        self.preview_layout.addStretch(1)
        self._animate_fade_in(loading, duration=120)

        self._feed_preview(selected, {c: i for i, c in enumerate(selected, start=1)},
                           self._folder_names_of(selected))

    def _feed_preview(
        self, cards: list[PlaylistCard], order: dict[PlaylistCard, int],
        folders: dict[PlaylistCard, str],
    ) -> None:
        """T-106: extrae la metadata en el hilo de UI pero por lotes (≈25 ms por tick) y lanza un
        `PreviewWorker` por lote, así las tarjetas empiezan a aparecer y la ventana responde."""
        self._render_queue.clear()
        self._feed_queue = list(cards)
        self._feed_order = order
        self._feed_folders = folders
        self._pump_feed()

    def _pump_feed(self) -> None:
        queue = self._feed_queue
        if not queue:
            return
        if not isValid(self.preview_layout):
            queue.clear()
            return
        deadline = time.perf_counter() + self._BATCH_BUDGET_S
        groups: list[GroupData] = []
        while queue and (not groups or time.perf_counter() < deadline):
            chunk = queue[:4]
            del queue[:4]
            groups.extend(self._extract_preview_data(chunk))
        for g in groups:
            g.order = self._feed_order.get(g.card, g.order)
            g.name = self._feed_folders.get(g.card, g.name)
        self._start_group_worker(groups)
        if queue:
            QTimer.singleShot(0, self._pump_feed)

    def _launch_preview_worker(self, groups: list[GroupData]) -> None:
        self._render_queue.clear()
        self._start_group_worker(groups)

    def _start_group_worker(self, groups: list[GroupData]) -> None:
        # ── Worker: existence checks en background con cache compartido ──
        worker = PreviewWorker(groups, self._source == "traktor", self._exists_cache)
        worker.group_ready.connect(self._queue_group)
        worker.done.connect(self._on_preview_done)
        self._preview_workers = [w for w in self._preview_workers if w.isRunning()]
        self._preview_workers.append(worker)
        self._preview_worker = worker
        worker.start()

    def _sync_preview_cards(self, selected: list[PlaylistCard]) -> None:
        """Tildar/destildar con la vista previa ya armada (T-089): quita las tarjetas de las
        playlists desmarcadas, renumera las que siguen y manda al worker solo las nuevas."""
        self._render_queue.clear()   # lo encolado sin dibujar se vuelve a pedir abajo
        keep = set(selected)
        for key in [k for k in self._preview_cards if k not in keep]:
            self._remove_preview_card(key)
        folders = self._folder_names_of(selected)
        for order, card in enumerate(selected, start=1):
            shown = self._preview_cards.get(card)
            if shown is not None:
                shown.data.name = folders.get(card, shown.data.name)   # un « (2)» puede aparecer o desaparecer
                shown.set_order(order)
        self._set_broken_total(sum(g.missing_count for g in self._rendered_groups))
        new = [c for c in selected if c not in self._preview_cards]
        if not new:
            return
        self._feed_preview(new, {c: i for i, c in enumerate(selected, start=1)}, folders)

    def _remove_preview_card(self, key: object) -> None:
        card = self._preview_cards.pop(key)
        self._rendered_groups = [g for g in self._rendered_groups if g is not card.data]
        row = self._playing_row
        if row is not None and card.isAncestorOf(row):
            self._playing_row = None   # la fila se destruye con la tarjeta
        self.preview_layout.removeWidget(card)
        self._stop_fade_anim(card)   # T-029: parar el fade ANTES de borrar
        card.deleteLater()

    def _group_rank(self, data: GroupData, ranks: dict[int, int]) -> int:
        """Posición de la playlist en el árbol = orden de la cola; sin playlist, al final."""
        return ranks.get(id(data.card), len(ranks))

    def _groups_in_order(self, groups: list[GroupData]) -> list[GroupData]:
        ranks = {id(c): i for i, c in enumerate(self._all_cards)}
        return sorted(groups, key=lambda g: self._group_rank(g, ranks))

    def _playlist_cache_key(self, playlist) -> str:
        uid = (
            getattr(playlist, "uuid", None)
            or getattr(playlist, "ID",   None)
            or playlist.Name
        )
        return f"{self._source}:{uid}"

    def _name_groups_like_folders(self, groups: list[GroupData]) -> None:
        """D-17: las colisiones se resuelven contra TODAS las marcadas, no solo las del lote."""
        folders = self._folder_names_of([c for c in self._all_cards if c.isChecked()])
        for g in groups:
            g.name = folders.get(g.card, g.name)

    @staticmethod
    def _folder_names_of(cards: list[PlaylistCard]) -> dict[PlaylistCard, str]:
        """Nombre de carpeta que el export creará por playlist (D-17), con la misma función de
        nombres únicos del worker. `cards` debe venir en el orden del árbol, como en el export."""
        names = folder_names_by_playlist([c.playlist for c in cards])
        return {c: names[id(c.playlist)] for c in cards if id(c.playlist) in names}

    def _extract_preview_data(self, selected: list[PlaylistCard]) -> list[GroupData]:
        """
        Extrae metadata de la DB en el main thread.
        Usa _track_meta_cache para evitar re-queries SQLAlchemy en cada toggle.
        El campo 'exists' se deja en True — el worker lo actualiza en background.
        """
        is_traktor = self._source == "traktor"

        if is_traktor:
            from traktor_db import get_songs as _get_songs
        else:
            from rekordbox_export import get_songs as _rb_get_songs
            from db import order_playlist_songs

            # mismo orden que el export.
            def _get_songs(pl):  # type: ignore[misc]
                return order_playlist_songs(_rb_get_songs(pl))

        from rekordbox_export import get_content, get_artist, sanitize

        groups: list[GroupData] = []
        for idx, card in enumerate(selected):
            cache_key = self._playlist_cache_key(card.playlist)

            if cache_key in self._track_meta_cache:
                # Cache hit: copia las filas (worker sobreescribirá exists)
                cached = self._track_meta_cache[cache_key]
                tracks = [
                    TrackRow(
                        num=t.num, title=t.title, artist=t.artist,
                        ext=t.ext, raw_path=t.raw_path, exists=True,
                        key=t.key, bpm=t.bpm, relocated=t.relocated,
                        streaming=t.streaming,
                    )
                    for t in cached
                ]
            else:
                # Cache miss: query a la DB (solo ocurre la primera vez)
                tracks: list[TrackRow] = []
                read_ok = True
                try:
                    for i, song in enumerate(_get_songs(card.playlist)):
                        content = get_content(song)
                        if not content:
                            continue
                        title    = sanitize(str(getattr(content, "Title",  "") or "") or "?")
                        artist   = get_artist(content)
                        artist_s = sanitize(str(artist)) if artist else ""
                        streaming = bool(getattr(content, "streaming", False))
                        # Streaming: no hay archivo; sin raw_path no se reproduce ni se repara.
                        raw      = "" if streaming else (getattr(content, "FolderPath", "") or "")
                        ext      = "stream" if streaming else (Path(raw).suffix.lower() if raw else "")
                        key, bpm = key_bpm_of(content)
                        tracks.append(TrackRow(
                            num      = str(i + 1).zfill(3),
                            title    = title    if len(title)    <= 46 else title[:44]    + "…",
                            artist   = artist_s if len(artist_s) <= 22 else artist_s[:20] + "…",
                            ext      = ext,
                            raw_path = raw,
                            exists   = True,
                            key      = key,
                            bpm      = bpm,
                            relocated = bool(getattr(content, "relocated", False)),
                            streaming = streaming,
                        ))
                except Exception as e:
                    # TEC-10: no cachear el vacío; el próximo toggle reintenta.
                    read_ok = False
                    _logger.exception("Preview: no se pudo leer la playlist %s", card.playlist.Name)
                    self._report_unreadable_playlist(card.playlist.Name, e)
                if read_ok:
                    self._track_meta_cache[cache_key] = tracks

            groups.append(GroupData(
                name        = card.playlist.Name,
                order       = idx + 1,
                total_count = card._track_count,
                tracks      = tracks,
                card        = card,
            ))
        return groups

    # ── Render queue: un grupo por event-loop tick, filas en lotes de 15 ──────

    def _queue_group(self, data: GroupData) -> None:
        """Recibe el grupo del worker y lo encola para render diferido."""
        # Cuenta al llegar el grupo, no al renderizar las filas en lotes.
        self._set_broken_total(self._broken_total + data.missing_count)
        self._render_queue.append(data)
        if len(self._render_queue) == 1:               # primer grupo: arrancar el pump
            QTimer.singleShot(0, self._pump_render_queue)

    def _pump_render_queue(self) -> None:
        """Procesa un grupo por tick del event loop — nunca bloquea la UI."""
        if not self._render_queue:
            return
        if not isValid(self.preview_layout):
            # El timer sobrevivió a la ventana (cierre, tests): nada que dibujar.
            self._render_queue.clear()
            return
        data = self._render_queue.pop(0)
        if data.card in self._preview_cards:
            # Cancelación a medias: ese grupo ya tiene tarjeta.
            if self._render_queue:
                QTimer.singleShot(0, self._pump_render_queue)
            return
        self._rendered_groups.append(data)
        self._rendered_groups = self._groups_in_order(self._rendered_groups)
        slot = next(i for i, g in enumerate(self._rendered_groups) if g is data)
        lo   = self.preview_layout

        # Quitar loading label al llegar el primer grupo real
        if lo.count() >= 1:
            first = lo.itemAt(0)
            if first and first.widget() and first.widget().objectName() == "preview_loading":
                w = first.widget()
                lo.removeWidget(w)
                self._stop_fade_anim(w)   # T-029: idem _clear_preview_layout
                w.deleteLater()
        # Quitar stretch final para insertar antes
        last = lo.itemAt(lo.count() - 1) if lo.count() else None
        if last and last.spacerItem():
            lo.removeItem(last)

        # T-015: ✕ destilda el mismo checkbox del árbol (`data.card`, que setChecked()
        # no avisa por señal: _close_group_card actualiza los números a mano).
        card = PreviewGroupCard(data, self._theme, can_repair=self._repair_supported())
        if data.card is not None:
            card.close_requested.connect(partial(self._close_group_card, data.card))
        card.repair_requested.connect(partial(self._on_card_repair, False, data))
        card.auto_resolve_requested.connect(partial(self._on_card_repair, True, data))
        self._preview_cards[data.card if data.card is not None else card] = card
        lo.insertWidget(slot, card)
        lo.addStretch(1)
        self._animate_fade_in(card, duration=180)

        # T-106: armazón en este tick y filas en el siguiente, así ningún tick junta ambos costos.
        QTimer.singleShot(0, partial(self._finish_group_rows, data, card))

    def _finish_group_rows(self, data: GroupData, card: PreviewGroupCard) -> None:
        # Filas perezosas (T-089): la tarjeta construye ~12 y el resto al scrollear. Una carpeta
        # 100 % rota nace colapsada y no crea sus filas hasta que se expande (D4).
        key = data.card if data.card is not None else card
        if isValid(card) and self._preview_cards.get(key) is card:
            positions = block_positions([t.exists for t in data.tracks])
            card.set_lazy_rows(list(zip(data.tracks, positions)), self._make_row_widget,
                               data.missing_count > 0)
        # Continuar con el siguiente grupo en el próximo tick
        if self._render_queue:
            QTimer.singleShot(0, self._pump_render_queue)
        elif self._scroll_to_restore is not None and not self._feed_queue:
            QTimer.singleShot(0, self._restore_preview_scroll)

    def _on_card_repair(self, auto: bool, data: GroupData) -> None:
        """Botonera de la tarjeta (D1 del PO): actúa SOLO sobre los rotos de esa carpeta."""
        if not self._repair_supported():
            return
        if self._relocate_state != "idle":
            return
        paths = frozenset(t.raw_path for t in data.tracks if not t.exists and t.raw_path)
        if not paths:
            return                       # alcance vacío: nunca degradar a «toda la librería»
        self._start_relocate(scope=RelocateScope(data.name, paths), auto_resolve=auto)

    def _on_preview_done(self) -> None:
        """Worker terminó. Limpia loading label si no llegó ningún grupo."""
        if self._closing:
            return
        self._last_exists_check = time.monotonic()
        lo = self.preview_layout
        for i in range(lo.count()):
            item = lo.itemAt(i)
            if item and item.widget() and item.widget().objectName() == "preview_loading":
                w = item.widget()
                lo.removeWidget(w)
                self._stop_fade_anim(w)   # T-029: idem _clear_preview_layout
                w.deleteLater()
                break

    def _show_preview_empty(self) -> None:
        lo = self.preview_layout
        empty = QWidget()
        empty.setObjectName("preview_empty")
        empty.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        el = QVBoxLayout(empty)
        el.setAlignment(Qt.AlignmentFlag.AlignCenter)
        el.setSpacing(10)
        icon = QLabel("◇")
        icon.setObjectName("output_empty_icon")
        icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title = QLabel("Sin playlists en cola")
        title.setObjectName("output_empty_title")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        sub = QLabel("Elegí una o más playlists\npara ver la salida numerada.")
        sub.setObjectName("output_empty_sub")
        sub.setAlignment(Qt.AlignmentFlag.AlignCenter)
        el.addStretch(1)
        el.addWidget(icon)
        el.addWidget(title)
        el.addWidget(sub)
        el.addStretch(1)
        lo.addWidget(empty)

    def _make_row_widget(
        self, track: TrackRow, block_pos: str = NONE, reserve_note: bool = False,
    ) -> QWidget:
        """Una fila de archivo. Llamado desde _batch_rows. `reserve_note`: en una carpeta con
        rotas, las sanas reservan el hueco del ícono de aviso para que el artista y el chip alineen."""
        missing = not track.exists
        flag = "true" if missing else "false"
        row = FileRow(track.raw_path, track.exists, block_pos=block_pos)
        row.track = track
        if track.relocated:
            row.setToolTip("Reubicada por List Buddy")
        row.setMinimumHeight(ROW_HEIGHT)   # rotas y sanas miden lo mismo: el alto del scroll depende de eso (T-074)
        if track.exists:
            row.clicked.connect(self._play_track)
        # Re-aplicar highlight si esta fila corresponde al track sonando
        if track.raw_path and track.raw_path == self._playing_path:
            row.set_playing(True)
            self._playing_row = row
        rl = QHBoxLayout(row)
        rl.setContentsMargins(14, 0, 14, 0)
        rl.setSpacing(ROW_GAP)

        def label(name: str, text: str) -> QLabel:
            lbl = QLabel(text)
            lbl.setObjectName(name)
            lbl.setProperty("file_missing", flag)
            return lbl

        idx_lbl = label("output_file_idx", track.num)
        idx_lbl.setFixedWidth(IDX_W)
        rl.addWidget(idx_lbl)
        # Ignored: un título largo se recorta en vez de ensanchar la columna (T8).
        name_lbl = label("output_file_name", track.title)
        name_lbl.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        rl.addWidget(name_lbl, 3)
        if track.artist:
            ar_lbl = label("output_file_artist", f"— {track.artist}")
            ar_lbl.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
            rl.addWidget(ar_lbl, 2)
        if missing:
            warn = label("output_file_warn", "")
            warn.setFixedWidth(WARN_W)
            warn.setPixmap(icons.pixmap("warning", token(PlaylistCard._theme, "danger"), 16))
            warn.setAccessibleName("Enlace roto")
            warn.setToolTip("Enlace roto")
            rl.addWidget(warn)
        elif reserve_note:
            rl.addSpacing(WARN_W + ROW_GAP)
        kb = label("output_file_keybpm", format_key_bpm(track.key, track.bpm))
        kb.setFixedWidth(KEYBPM_W)
        row.keybpm_label = kb
        rl.addWidget(kb)
        if track.ext:
            chip = label("output_file_ext", ext_chip_text(track.ext))
            chip.setFixedWidth(CHIP_W)
            chip.setAlignment(Qt.AlignmentFlag.AlignCenter)
            rl.addWidget(chip, 0, Qt.AlignmentFlag.AlignVCenter)
        return row

    # ──────────────────────────────────── Audio playback ─────────────────

    def _set_row_playing(self, row: FileRow | None, playing: bool) -> None:
        """
        set_playing() defensivo: el row puede ser un objeto C++ ya borrado
        (preview re-renderizado). Una excepción acá abortaría toda la app porque
        corre dentro de un slot de Qt, así que la tragamos en silencio.
        """
        if row is None:
            return
        try:
            row.set_playing(playing)
        except RuntimeError:
            pass

    def _play_track(self, raw_path: str) -> None:
        """Slot de FileRow.clicked. La fila emisora es self.sender()."""
        row = self.sender()
        self._play_file_row(row if isinstance(row, FileRow) else None, raw_path)

    def _play_file_row(
        self,
        row: FileRow | None,
        raw_path: str,
        allow_toggle: bool = True,
        track: TrackRow | None = None,
    ) -> None:
        # Click en la fila que ya suena → pausa/reanuda en vez de reiniciar
        if allow_toggle and raw_path and raw_path == self._playing_path \
                and self._audio.current_path():
            self._play_gen += 1   # el último gesto fue este: una resolución tardía ya no vale
            self._audio.toggle()
            return

        # exists()/resolve_path() pueden tardar en USB o red: se resuelven en un hilo corto y el
        # último click gana (TEC-15).
        self._play_gen += 1
        resolver = PlayResolveWorker(raw_path, self._source == "traktor", self._play_gen)
        self._retain_thread(resolver)
        resolver.resolved.connect(
            lambda gen, path, r=row, raw=raw_path, t=track: self._on_play_resolved(gen, path, r, raw, t)
        )
        resolver.start()

    def _on_play_resolved(
        self, gen: int, resolved: str | None, row: FileRow | None, raw_path: str,
        track: TrackRow | None,
    ) -> None:
        if self._closing or gen != self._play_gen or not resolved:
            return
        if not is_playable_audio(resolved):
            self._on_audio_error(NOT_PLAYABLE_MESSAGE)   # SEC-18: ni se abre
            return
        from shiboken6 import isValid
        if row is None or not isValid(row):
            row = self._row_for(raw_path)   # pudo dibujarse mientras se resolvía la ruta
        self._audio.play(resolved)
        self._playing_path = raw_path

        self._set_row_playing(self._playing_row, False)
        self._playing_row = None
        if isinstance(row, FileRow):
            self._set_row_playing(row, True)
            self._playing_row = row

        self._update_now_playing(track or getattr(row, "track", None))
        self._start_waveform(resolved)

    def _update_now_playing(self, track: TrackRow | None = None) -> None:
        """Título y artista del footer salen del dato de la pista, no de las filas."""
        self._footer.set_now_playing(
            track.title if track else "", track.artist if track else "",
        )

    def _on_playing_changed(self, playing: bool) -> None:
        self._is_playing = playing
        self._refresh_play_glyph()

    def _refresh_play_glyph(self) -> None:
        """Ícono del play: nota en reposo, play con un track cargado, pausa sonando."""
        name = "pause" if self._is_playing else ("play" if self._playing_path else "note")
        self._footer.set_play_glyph(name)

    def _tint_icon(self, widget: QWidget, name: str, color_token: str, size: int) -> None:
        """Pone un ícono SVG y lo registra para re-teñirlo con el tema."""
        self._themed_icons.append((widget, name, color_token, size))
        self._apply_icon(widget, name, color_token, size)

    def _apply_icon(self, widget: QWidget, name: str, color_token: str, size: int) -> None:
        color = token(self._theme, color_token)
        if isinstance(widget, QPushButton):
            widget.setIcon(icons.icon(name, color, size))
            widget.setIconSize(QSize(size, size))
        elif isinstance(widget, QLabel):
            widget.setPixmap(icons.pixmap(name, color, size))

    def _retint_icons(self) -> None:
        from shiboken6 import isValid
        # El preview recrea widgets: descartar los que Qt ya destruyó.
        self._themed_icons = [t for t in self._themed_icons if isValid(t[0])]
        for widget, name, color_token, size in self._themed_icons:
            self._apply_icon(widget, name, color_token, size)
        self._refresh_play_glyph()

    def _on_space(self) -> None:
        # No robar la barra espaciadora cuando se está escribiendo o sobre un botón
        from PySide6.QtWidgets import QAbstractButton
        fw = QApplication.focusWidget()
        if isinstance(fw, (QLineEdit, QPlainTextEdit, QAbstractButton)):
            return
        self._audio.toggle()

    def _playable_tracks(self) -> list[TrackRow]:
        """Pistas reproducibles en orden de cola, leídas de los DATOS y no de las filas:
        el cambio de tema destruye las filas y las reconstruye por lotes (T-070), pero
        `_apply_theme` repone estos grupos de forma síncrona, así que nunca quedan
        vacíos (T-072)."""
        return [
            t for g in self._groups_in_order([*self._rendered_groups, *self._render_queue])
            for t in g.tracks if t.exists and t.raw_path
        ]

    def _row_for(self, raw_path: str) -> FileRow | None:
        for row in self.preview_container.findChildren(FileRow):
            try:
                if row._raw_path == raw_path:
                    return row
            except RuntimeError:
                continue
        return None   # aún no dibujada: _make_row_widget la resalta cuando aparezca

    def _on_track_finished(self) -> None:
        """Reproduce el siguiente track existente de la cola, si lo hay."""
        if self._closing:
            return
        if not self._auto_advance:
            return
        queue = self._playable_tracks()
        idx = next((i for i, t in enumerate(queue) if t.raw_path == self._playing_path), -1)
        if idx == -1 or idx + 1 >= len(queue):
            return
        nxt = queue[idx + 1]
        self._play_file_row(self._row_for(nxt.raw_path), nxt.raw_path,
                            allow_toggle=False, track=nxt)

    def _on_position_changed(self, pos: int, dur: int) -> None:
        self._footer.set_position(pos, dur)

    def _on_audio_error(self, msg: str) -> None:
        self._playing_path = ""
        self._is_playing = False
        self._refresh_play_glyph()
        self._set_row_playing(self._playing_row, False)
        self._playing_row = None
        self._update_now_playing(None)
        self._cancel_waveform()
        self._footer.set_wave(None)
        dialogs.warning(self, "Reproducción de audio", msg)

    # ── Forma de onda del footer ───────────────────────────────────────────

    def _start_waveform(self, resolved: str) -> None:
        self._cancel_waveform()
        cached = self._wave_cache.get(resolved)
        if cached is not None:
            self._footer.set_wave(cached)
            return
        self._footer.set_wave(None)          # onda plana mientras decodifica
        self._wave_gen += 1
        worker = WaveformWorker(resolved, self._wave_gen)
        worker.ready.connect(lambda data, gen, p=resolved: self._on_wave_ready(p, data, gen))
        worker.finished.connect(lambda w=worker: self._live_wave_workers.discard(w))
        self._live_wave_workers.add(worker)   # vivo hasta que el hilo termine
        self._wave_worker = worker
        worker.start()

    def _cancel_waveform(self) -> None:
        worker = self._wave_worker
        if worker is not None:
            try:
                worker.ready.disconnect()
            except (RuntimeError, TypeError):
                pass
            worker.cancel()

    def _on_wave_ready(self, path: str, data: WaveData, generation: int) -> None:
        if self._closing:
            return
        if generation != self._wave_gen:
            return                            # resultado stale → descartar
        self._wave_cache[path] = data
        while len(self._wave_cache) > 32:
            self._wave_cache.pop(next(iter(self._wave_cache)))
        self._footer.set_wave(self._wave_cache[path])

    def closeEvent(self, event) -> None:
        # I-1: cerrar la ventana con un relocate corriendo cancelaba sin
        # avisar nada — mismo aviso que "Cancelar" si ya hay trabajo hecho
        # que se perdería (nada se escribe hasta el final, ADR-001 punto 2).
        if self._relocate_worker and self._relocate_worker.isRunning():
            if self._relocate_progress_done > 0 and not self._confirm_relocate_interrupt(
                "Cerrar la app"
            ):
                event.ignore()
                return

        self._closing = True
        self._play_gen += 1
        self._audio.stop()
        self._cancel_waveform()
        for w in list(self._live_wave_workers):
            w.wait(1500)
        self._cancel_preview_worker()
        self._cancel_library_load()
        if self._worker and self._worker.isRunning():
            self._wait_export_block(self._worker)
        if self._relocate_worker and self._relocate_worker.isRunning():
            self._relocate_worker.requestInterruption()
            # Si está bloqueado esperando el modal de desambiguación, nadie
            # va a llamar provide_answer(): liberarlo como SKIP para que la
            # app pueda cerrar sin quedar colgada.
            self._relocate_worker.provide_answer(None)
            self._relocate_worker.wait(4000)
        if self._update_worker is not None:
            # Hilo daemon: no frena la salida aunque el urlopen/DNS siga colgado.
            self._update_worker.cancel()
        # Cualquier hilo que siga corriendo (p. ej. un PreviewWorker cancelado
        # en un stat lento) se espera con tope: destruirlo en vuelo aborta.
        for thread in list(self._live_threads):
            if thread.isRunning():
                thread.requestInterruption()
                thread.wait(2000)
        super().closeEvent(event)
        self._exit_if_threads_hung()

    # Hilos que solo leen o solo crean la carpeta vacía de destino (stat, decoder, carga de la
    # librería, resolución de ruta): si uno queda colgado en el kernel
    # se puede abandonar. Cualquier otro (relocate, restore, carga, destino) escribe o crea
    # archivos y se espera entero.
    _READ_ONLY_THREADS = (
        DestinationCheck, ExistenceRecheckWorker, LibraryLoadWorker, PlayResolveWorker,
        PreviewWorker, WaveformWorker,
    )

    def _exit_if_threads_hung(self) -> None:
        """TEC-24: un `stat`/decoder colgado en el kernel (USB dormido, SMB caído) no se puede
        esperar sin tope ni destruir en vuelo (Qt aborta con SIGABRT). Si SOLO quedan hilos de
        lectura, se guarda lo propio y el proceso sale limpio (el SO libera el hilo). Si queda
        vivo un hilo que escribe, se espera sin tope con cursor de espera, como el export (D-16):
        cortarlo a mitad dejaría un NML/JSON a medias."""
        alive = [t for t in (*self._live_threads, *self._live_wave_workers) if t.isRunning()]
        writers = [t for t in alive if not isinstance(t, self._READ_ONLY_THREADS)]
        if writers:
            self.output_status.setText("Esperando que termine la operación en curso…")
            QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
            try:
                for t in writers:
                    while not t.wait(50):
                        QApplication.processEvents(QEventLoop.ProcessEventsFlag.ExcludeUserInputEvents)
            finally:
                QApplication.restoreOverrideCursor()
            alive = [t for t in alive if t.isRunning()]
        if not alive:
            return
        _logger.warning("Cierre con %d hilo(s) de lectura colgado(s): salida directa", len(alive))
        self.settings.sync()
        logging.shutdown()
        os._exit(0)

    _RECHECK_EVERY_S = 5.0

    def event(self, e) -> bool:
        if e.type() == QEvent.Type.WindowActivate:
            self._recheck_existence_on_focus()
        return super().event(e)

    def _recheck_existence_on_focus(self) -> None:
        """TEC-18: al volver a la ventana (típico: se conectó el disco) se re-mira en disco lo
        que la vista previa muestra, con throttling de 5 s y sin tocar la UI hasta saber si
        algo cambió."""
        if time.monotonic() - self._last_exists_check < self._RECHECK_EVERY_S:
            return
        busy = self._recheck_worker is not None and self._recheck_worker.isRunning()
        if busy or self._export_state != "idle" or self._is_maintenance_busy():
            return
        known = {t.raw_path: t.exists for g in self._rendered_groups for t in g.tracks
                 if t.raw_path and not t.streaming}
        if not known:
            return
        self._last_exists_check = time.monotonic()
        worker = ExistenceRecheckWorker(known, self._source == "traktor")
        worker.changed.connect(self._on_recheck_done)
        self._retain_thread(worker)
        self._recheck_worker = worker
        worker.start()

    def _on_recheck_done(self, changed: frozenset[str]) -> None:
        """T-106: rehace solo las tarjetas con alguna pista cuyo estado cambió y conserva el
        resto y el scroll de la vista previa (antes se reconstruía todo y volvía arriba)."""
        if self._closing:
            return
        if not changed or self._export_state != "idle":
            return
        for raw in changed:
            self._exists_cache.pop(raw, None)
        affected = [card for card, pc in self._preview_cards.items()
                    if any(t.raw_path in changed for t in pc.data.tracks)]
        if not affected:
            return
        # A mitad del dibujo hay tarjetas marcadas aún sin dibujar: se cancela lo en vuelo (traería
        # datos viejos) y se vuelve a pedir TODO lo que falta, no solo las afectadas.
        self._cancel_preview_worker()
        self._render_queue.clear()
        for card in affected:
            self._remove_preview_card(card)
        self._set_broken_total(sum(g.missing_count for g in self._rendered_groups))
        self._scroll_to_restore = self.preview_scroll.verticalScrollBar().value()
        selected = [c for c in self._all_cards if c.isChecked()]
        missing = [c for c in selected if c not in self._preview_cards]
        self._feed_preview(missing, {c: i for i, c in enumerate(selected, start=1)},
                           self._folder_names_of(selected))

    def _restore_preview_scroll(self) -> None:
        value, self._scroll_to_restore = self._scroll_to_restore, None
        if value is not None and isValid(self.preview_scroll):
            self.preview_scroll.verticalScrollBar().setValue(value)

    def _wait_export_block(self, worker: QThread) -> None:
        """Cierra sin abortar: la copia corta entre bloques de 1 MiB, pero un disco lento puede
        tardar en devolver el bloque actual. Se espera sin tope (con cursor de espera); si el
        disco está colgado de verdad, el usuario lo resuelve desconectándolo, no con un SIGABRT."""
        worker.requestInterruption()
        self.output_status.setText("Esperando que termine la copia…")
        QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
        try:
            while not worker.wait(50):
                QApplication.processEvents(QEventLoop.ProcessEventsFlag.ExcludeUserInputEvents)
        finally:
            QApplication.restoreOverrideCursor()

    # ──────────────────────────────────────── Actions ────────────────────

    def _choose_folder(self) -> None:
        folder = QFileDialog.getExistingDirectory(self, "Elegí la carpeta de destino")
        if folder:
            self._footer.set_dest(folder)

    def _on_path_changed(self, text: str) -> None:
        if text.strip():
            self.settings.setValue("last_dest_folder", text.strip())

    # Presupuesto de trabajo por tick: deja pasar el input y el repintado (TEC-23, ≤ 100 ms).
    _BATCH_BUDGET_S = 0.010

    def _set_all(self, checked: bool, only_visible: bool = False) -> None:
        """Marca/desmarca en lotes: con cientos de playlists un solo bucle congelaba la ventana.
        El primer lote corre acá mismo, así que las listas chicas quedan listas al volver."""
        self._mark_queue = [c for c in self._all_cards if not (only_visible and c.isHidden())]
        self._mark_value = checked
        self._pump_mark()

    def _pump_mark(self) -> None:
        queue = self._mark_queue
        if not queue or not isValid(self.playlist_container_layout):
            return
        deadline = time.perf_counter() + self._BATCH_BUDGET_S
        done = 0
        for card in queue:
            card.setChecked(self._mark_value)
            done += 1
            if time.perf_counter() >= deadline:
                break
        del queue[:done]
        self._update_order_numbers()
        if queue:
            QTimer.singleShot(0, self._pump_mark)

    def _close_group_card(self, card: PlaylistCard) -> None:
        """T-015: botón de cerrar del header de un grupo en el preview — destilda
        el checkbox real de esa playlist en el árbol izquierdo (mismo efecto
        que destildarla ahí a mano)."""
        if card in self._mark_queue:
            self._mark_queue.remove(card)
        card.setChecked(False)
        self._update_order_numbers()

    def _selected_playlists(self) -> list:
        return [c.playlist for c in self._all_cards if c.isChecked()]

    # ──────────────────────────────────────── Export ─────────────────────

    def _start_export(self) -> None:
        if self._relocate_worker and self._relocate_worker.isRunning():
            dialogs.warning(
                self, "Relocate en curso",
                "Esperá a que termine la reparación de enlaces antes de exportar.",
            )
            return
        output = self._footer.dest_text().strip()
        if not output:
            dialogs.warning(self, "Falta carpeta", "Elegí primero una carpeta de destino.")
            return
        selected = self._selected_playlists()
        if not selected:
            dialogs.warning(self, "Sin selección", "Marcá al menos una playlist.")
            return
        if self._dest_check is not None:
            return   # ya se está comprobando el destino de un click anterior
        self._status_before_check = self.output_status.text()
        self.output_status.setText("Verificando destino…")
        check = DestinationCheck(Path(output))
        self._dest_check = check
        self._retain_thread(check)
        check.checked.connect(lambda ok, o=output, s=selected: self._on_dest_checked(o, s, ok))
        check.start()

    def _restore_status_after_check(self) -> None:
        self.output_status.setText(self._status_before_check)

    def _on_dest_checked(self, output: str, selected: list, ok: bool) -> None:
        self._dest_check = None
        if self._closing:
            return   # la ventana ya se cerró: nunca arrancar un export después de closeEvent
        if self._relocate_worker and self._relocate_worker.isRunning():
            self._restore_status_after_check()
            dialogs.warning(
                self, "Relocate en curso",
                "Esperá a que termine la reparación de enlaces antes de exportar.",
            )
            return
        if not ok:
            self._restore_status_after_check()
            # Típico: el destino guardado está en un disco que hoy no está montado.
            dialogs.warning(
                self, "No se puede usar la carpeta de destino",
                f"No se puede escribir en:\n{output}\n\n"
                "¿Está conectado el disco? Conectalo o elegí otra carpeta con «Cambiar».",
            )
            return

        self._last_export_dest = output
        self._set_export_state("running")
        self._footer.begin_progress("Copiando y numerando…")
        self.output_status.setText("exportando…")
        self._set_status_style("active")
        self.preview_scroll.setVisible(False)
        self.log_view.setVisible(True)
        self.log_view.clear()
        self._log(f"→ Destino: {output}")

        self._worker = ExportWorker(selected, Path(output))
        self._retain_thread(self._worker)
        self._worker.log.connect(self._log)
        self._worker.progress.connect(self._on_progress)
        self._worker.finished_ok.connect(self._on_finished)
        self._worker.start()

    def _set_export_state(self, state: Literal["idle", "running", "cancelling"]) -> None:
        self._export_state = state
        self._footer.set_export_mode(state)

    def _on_export_clicked(self) -> None:
        if self._export_state == "idle":
            self._start_export()
        elif self._export_state == "running":
            self._cancel_export()

    def _cancel_export(self) -> None:
        if self._worker and self._worker.isRunning():
            self._set_export_state("cancelling")
            self._worker.requestInterruption()

    def _open_dest_in_finder(self) -> None:
        QDesktopServices.openUrl(QUrl.fromLocalFile(self._last_export_dest))

    def _on_progress(self, done: int, total: int) -> None:
        self._footer.set_progress(done, total)

    def _on_finished(self, copied: int, missing: int, skipped: int, status: str) -> None:
        self._set_export_state("idle")

        # ── Resumen ───────────────────────────────────────────────────────
        parts: list[str] = []
        if copied:
            parts.append(f"{copied} copiada{'s' if copied != 1 else ''}")
        if skipped:
            parts.append(f"{skipped} saltada{'s' if skipped != 1 else ''}")
        if missing:
            parts.append(f"{missing} no encontrada{'s' if missing != 1 else ''}")
        summary = " · ".join(parts) if parts else "Nada que copiar"

        if status == "cancelled":
            self._footer.end_progress(f"Cancelado — {summary}", "⏹")
            self.output_status.setText("cancelado")
            self._set_status_style("warn")
        elif status == "error":
            self._footer.end_progress(summary or "Error durante la exportación", "✗")
            self.output_status.setText("error ✗")
            self._set_status_style("error")
        elif missing > 0 and copied == 0:
            self._footer.end_progress(summary, "⚠")
            self.output_status.setText("sin copias ⚠")
            self._set_status_style("warn")
        elif missing > 0:
            self._footer.end_progress(summary, "⚠")
            self.output_status.setText("parcial ⚠")
            self._set_status_style("warn")
        else:
            self._footer.end_progress(summary, "✓")
            self.output_status.setText("exportado ✓")
            self._set_status_style("ok")

        self._log(f"\n{'⏹' if status == 'cancelled' else '✓'}  {summary}")

        # ── Botón "Abrir en Finder" ───────────────────────────────────────
        # El worker ya miró el disco (TEC-31): acá no hay E/S.
        if copied > 0 and getattr(self._worker, "dest_exists", False):
            self._footer.set_finder_visible(True)

        self.log_view.setVisible(False)
        self.preview_scroll.setVisible(True)
        self._exists_cache.clear()
        QTimer.singleShot(8000, self._hide_progress_section)

    def _set_status_style(self, variant: str) -> None:
        """Colorea el tag output_status según el resultado (ok/warn/error/active)."""
        self.output_status.setStyleSheet(status_style(self._theme, variant))

    def _hide_progress_section(self) -> None:
        # Un timer de 8 s de una corrida anterior no debe ocultar la actual.
        if self._footer.progress_active():
            return
        self._footer.hide_progress()
        self.output_status.setStyleSheet("")

    def _log(self, text: str) -> None:
        self.log_view.appendPlainText(text)

    def _report_unreadable_playlist(self, name: str, exc: Exception) -> None:
        line = f"⚠ No se pudo leer la playlist {name}: {exc}"
        self._log(line)
        self.output_status.setText(line)
        self._set_status_style("warn")

    # ──────────────────────────────── Relocate (F-07 ADR-001 / F-08 ADR-002) ───

    def _forget_rb_fixes(self) -> None:
        n = self._fixes_store.count()
        if n <= 0 or self._is_maintenance_busy():
            return
        if not dialogs.question(
            self, "Olvidar reparaciones de Rekordbox",
            ("Vas a olvidar la reparación guardada para Rekordbox. " if n == 1
             else f"Vas a olvidar las {n} reparaciones guardadas para Rekordbox. ")
            + "Las pistas vuelven a figurar con su ruta original del XML. "
            "Tu XML y Rekordbox no cambian. ¿Seguir?",
        ):
            return
        self._fixes_store.clear()
        self._reload_after_path_change()
        self._sync_rb_actions()

    def _export_rb_xml(self) -> None:
        if not isinstance(self._db, rekordbox_xml.RekordboxXmlLibrary):
            return
        if self._is_maintenance_busy():
            return
        playlists = self._selected_playlists()
        if not playlists:
            dialogs.warning(self, "Sin selección", "Marcá al menos una playlist.")
            return
        from rekordbox_export import sanitize
        first = sanitize(str(getattr(playlists[0], "Name", "") or "")) or "playlist"
        dest_str, _ = QFileDialog.getSaveFileName(
            self, "Guardar XML para Rekordbox",
            str(Path.home() / "Desktop" / f"List Buddy - {first}.xml"),
            "Rekordbox XML (*.xml)",
        )
        if not dest_str:
            return
        dest = Path(dest_str)
        try:
            res = rekordbox_xml.write_playlists_xml(
                playlists, dest, source=self._db.path, app_version=_APP_VERSION,
            )
        except ValueError as e:
            dialogs.warning(self, "No se puede guardar ahí", str(e))
            return
        except ET.ParseError as e:
            # Texto crudo de una pista que no se puede rearmar (p. ej. entidades del DTD).
            dialogs.critical(
                self, "No se pudo armar el XML",
                "Una de las pistas del XML cargado no se pudo reconstruir, así que no se guardó nada.\n\n"
                f"Volvé a exportar el XML desde Rekordbox y cargalo de nuevo.\n\nDetalle: {e}",
            )
            return
        except OSError as e:
            dialogs.critical(self, "Error al guardar", f"No se pudo guardar el XML: {e}")
            return
        lines = [
            f"Se guardó: {dest}",
            f"{res.playlists} lista(s) · {res.tracks} pista(s) · "
            f"{res.relocated} con ruta reparada · {res.missing} todavía sin archivo.",
            "",
        ]
        if res.missing > 0:
            lines += [
                "Las pistas sin archivo se incluyen igual, para respetar el orden; "
                "Rekordbox las va a mostrar como faltantes.",
                "",
            ]
        lines += [
            "Para importarla en Rekordbox:",
            "1. Preferencias → Vista → Diseño: activá «rekordbox xml».",
            "2. Preferencias → Avanzado → Base de datos → rekordbox xml: en "
            "«Biblioteca importada» elegí este archivo.",
            "3. En el panel izquierdo abrí «rekordbox xml» → Listas de reproducción, "
            "hacé clic derecho en la lista y elegí «Importar lista de reproducción».",
            "",
            "Si el panel «rekordbox xml» ya estaba abierto, actualizalo (clic derecho → "
            "Actualizar / volvé a elegir el archivo) para ver la lista nueva.",
        ]
        dialogs.information(self, "XML para Rekordbox", "\n".join(lines))

    def _relocate_target_info(self) -> tuple[str, Path | None]:
        """
        B-2: qué archivo se va a modificar, para mostrarlo completo en el
        diálogo de confirmación previo. Solo Traktor: `self._db` ya está
        cargado (se valida arriba en `_start_relocate`).
        Devuelve (nombre_de_archivo, ruta_o_None).
        """
        return "collection.nml", Path(self._db.path) if self._db is not None else None

    def _confirm_relocate_start(
        self, search_root: str, auto_resolve: bool,
        scope: RelocateScope | None = None,
    ) -> bool:
        """
        B-2: diálogo de confirmación previo a arrancar el relocate — hoy el
        flujo iba directo de "elegir carpeta" a "arrancar y escribe" (cero
        confirmaciones en toda la app, incumple ADR-001 punto 3). Informa
        (a) qué archivo se va a modificar, (b) que hay backup automático y
        dónde queda, (c) que hay que tener la app de origen cerrada.
        I-5: si "Resolver automáticamente" está tildado, suma una línea de
        advertencia específica — un click de distancia de miles de
        reescrituras silenciosas merece su propia confirmación explícita.
        """
        if self._source == "rekordbox":
            return self._confirm_rb_relocate_start(auto_resolve, scope)
        app_name = "Traktor"
        target_name, target_path = self._relocate_target_info()
        target_display = str(target_path) if target_path else (
            f"{target_name} (ubicación autodetectada de {app_name})"
        )
        backups_display = (
            str(target_path.parent / "listBuddy_backups") if target_path
            else f"la carpeta 'listBuddy_backups' junto a tu {target_name}"
        )

        if scope is not None:
            n = len(scope.paths)
            head = [
                f"Esto va a reparar los enlaces rotos de la carpeta «{scope.name}» "
                f"({n} pista{'s' if n != 1 else ''}) en tu librería de {app_name}:",
                target_display,
                "",
                "Si alguna de estas pistas también está en otras playlists, queda "
                "reparada en todas: es la misma entrada de tu librería.",
            ]
        else:
            head = [
                f"Esto va a modificar el archivo de tu librería de {app_name}:",
                target_display,
            ]
        lines = head + [
            "",
            "Se crea un backup automático antes de escribir, en:",
            backups_display,
            "",
            f"Cerrá {app_name} antes de continuar — si sigue abierto, la "
            "reparación se cancela sin escribir nada.",
        ]
        if auto_resolve and scope is not None:
            lines += [
                "",
                "⚠ Vas a aplicar la mejor coincidencia en las pistas con más de un "
                "candidato, sin preguntar una por una. Solo en esta carpeta.",
            ]
        elif auto_resolve:
            lines += [
                "",
                "⚠ Tenés activado \"Resolver automáticamente…\": vas a aplicar "
                "la mejor coincidencia en todas las pistas con más de un "
                "candidato, sin preguntar una por una.",
            ]
        lines += ["", _RESPONSIBILITY_LINE, "", "¿Continuar?"]

        yes = dialogs.question(
            self, f"Reparar enlaces rotos — {app_name}",
            "\n".join(lines),
        )
        return yes

    def _confirm_rb_relocate_start(
        self, auto_resolve: bool, scope: RelocateScope | None,
    ) -> bool:
        lines: list[str] = []
        if scope is not None:
            n = len(scope.paths)
            lines += [
                f"Carpeta «{scope.name}» ({n} pista{'s' if n != 1 else ''}).",
                "",
            ]
        lines += [
            "List Buddy va a buscar los archivos que faltan y a guardar las rutas "
            "nuevas para usarlas al exportar.",
            "",
            "No se modifica tu XML ni tu librería de Rekordbox. Para que Rekordbox "
            "también las tenga, usá «Exportar XML para Rekordbox…» e importá la lista.",
        ]
        if auto_resolve and scope is not None:
            lines += [
                "",
                "⚠ Vas a aplicar la mejor coincidencia en las pistas con más de un "
                "candidato, sin preguntar una por una. Solo en esta carpeta.",
            ]
        elif auto_resolve:
            lines += [
                "",
                "⚠ Tenés activado \"Resolver automáticamente…\": vas a aplicar "
                "la mejor coincidencia en todas las pistas con más de un "
                "candidato, sin preguntar una por una.",
            ]
        lines += ["", _RESPONSIBILITY_LINE, "", "¿Continuar?"]
        return dialogs.question(
            self, "Reparar enlaces rotos — Rekordbox", "\n".join(lines)
        )

    def _confirm_relocate_interrupt(self, action_label: str) -> bool:
        """
        I-1: confirma antes de perder trabajo ya hecho en un relocate en
        curso. Diseño actual (ADR-001 punto 2): nada se escribe hasta el
        final — correcto para atomicidad, pero con auto-resolución OFF (el
        default) y muchos links rotos el usuario puede pasar mucho tiempo
        respondiendo modales de desambiguación antes de tocar "Cancelar" o
        cerrar la ventana, y hoy eso tiraba todo sin avisar. Se llama solo
        cuando ya hay progreso (`_relocate_progress_done > 0`) — cancelar
        antes de que arranque nada no necesita confirmación.
        """
        done = self._relocate_progress_done
        total = self._relocate_progress_total
        yes = dialogs.question(
            self, "¿Perder el trabajo hecho?",
            f"Ya se revisaron {done} de {total or done} enlace(s) roto(s) "
            "en esta sesión. Nada se guarda hasta el final: si continuás, "
            "se pierden todas las decisiones ya tomadas y vas a tener que "
            f"volver a repasarlas.\n\n¿{action_label} de todos modos?",
        )
        return yes

    def _start_relocate(
        self, scope: RelocateScope | None = None, auto_resolve: bool | None = None,
    ) -> None:
        """Relocate global (menú, sin argumentos) o, con `scope` (T-073), solo
        de las pistas de una playlist. Con alcance el tilde del menú no se
        lee: `auto_resolve` viene explícito y la confirmación siempre se pide."""
        if not self._repair_supported():
            return
        if self._db is None:
            dialogs.warning(
                self, "Sin librería", "Cargá la librería de Traktor primero."
            )
            return
        if self._worker and self._worker.isRunning():
            dialogs.warning(
                self, "Exportación en curso",
                "Esperá a que termine la exportación actual antes de reparar enlaces.",
            )
            return
        if self._relocate_worker and self._relocate_worker.isRunning():
            return
        if self._dest_check is not None:
            dialogs.warning(
                self, "Verificando destino",
                "Esperá un momento: se está verificando la carpeta de destino de la exportación.",
            )
            return

        # R-03 (Traktor) / R-01 (Rekordbox) — "cerrá la app antes de reparar
        # enlaces" — se chequea DENTRO del worker (run()), no acá: ambos
        # chequeos (subprocess.run / get_rekordbox_pid) no son garantizadamente
        # livianos y nunca deben correr en el hilo de UI. Ver
        # _on_relocate_finished para el status "blocked".

        search_root = QFileDialog.getExistingDirectory(
            self, "Elegí la carpeta o disco donde buscar los archivos"
        )
        if not search_root:
            return

        if scope is None:
            if auto_resolve is None:
                auto_resolve = self._auto_resolve_enabled()
        else:
            auto_resolve = bool(auto_resolve)
        if not self._confirm_relocate_start(search_root, auto_resolve, scope):
            return

        # T-007: cambiar botón a modo Cancelar (mismo patrón que export_btn).
        self._set_relocate_state("running")

        self._footer.begin_progress("Buscando enlaces rotos…")
        self.output_status.setText("reparando…")
        self._set_status_style("active")
        self.preview_scroll.setVisible(False)
        self.log_view.setVisible(True)
        self.log_view.clear()
        self._log(f"→ Buscando en: {search_root}")

        # Se fija la fuente activa al arrancar (no self._source en vivo):
        # el selector de fuente queda bloqueado mientras hay un relocate
        # (`_sync_busy_locks`); igual el mensaje de "blocked" al terminar debe
        # referirse a la app que efectivamente se chequeó, no a la que esté
        # seleccionada en ese momento.
        self._relocate_source = self._source
        self._relocate_progress_done = 0
        self._relocate_progress_total = 0

        if scope is not None:
            self._log(f"→ Alcance: carpeta «{scope.name}» ({len(scope.paths)} pista(s))")
        if self._source == "rekordbox":
            self._log(f"→ XML: {self._db.path}")
            self._relocate_worker = RekordboxXmlRelocateWorker(
                self._db.path, self._fixes_store.path, Path(search_root),
                auto_resolve=auto_resolve, scope=scope,
            )
        else:
            self._log(f"→ NML: {self._db.path}")
            self._relocate_worker = RelocateWorker(
                self._db.path, Path(search_root), auto_resolve=auto_resolve,
                scope=scope,
            )
        self._retain_thread(self._relocate_worker)
        self._relocate_worker.log.connect(self._log)
        self._relocate_worker.progress.connect(self._on_progress)
        self._relocate_worker.progress.connect(self._on_relocate_progress_track)
        self._relocate_worker.ask_user.connect(self._on_relocate_ask)
        self._relocate_worker.finished_ok.connect(self._on_relocate_finished)
        self._relocate_worker.start()

    def _on_relocate_progress_track(self, done: int, total: int) -> None:
        """I-1: registra el último progreso conocido del relocate en curso
        (independiente de `_on_progress`, que solo actualiza la barra) para
        poder avisar antes de tirarlo si el usuario cancela o cierra."""
        self._relocate_progress_done = done
        self._relocate_progress_total = total

    def _on_relocate_ask(self, request) -> None:
        """
        Slot conectado a RelocateWorker.ask_user (auto-queued: el worker
        emite desde su propio hilo, este slot corre en el hilo de UI). El
        worker queda bloqueado en threading.Event.wait() hasta que
        provide_answer() le llegue — nunca toca widgets desde su hilo.
        """
        if self._closing:
            # closeEvent ya liberó al worker; un modal nuevo bloquearía el cierre
            if self._relocate_worker:
                self._relocate_worker.provide_answer(None)
            return
        dlg = RelocateDialog(request, self)
        dlg.exec()
        if self._relocate_worker:
            self._relocate_worker.provide_answer(dlg.chosen_path)

    def _cancel_relocate(self) -> None:
        if not (self._relocate_worker and self._relocate_worker.isRunning()):
            return
        # I-1: avisar antes de tirar el trabajo ya hecho — solo si ya hay
        # progreso (cancelar apenas arrancó, sin nada que perder, no necesita
        # confirmación).
        if self._relocate_progress_done > 0 and not self._confirm_relocate_interrupt(
            "Cancelar la reparación"
        ):
            return
        self._set_relocate_state("cancelling")
        self._relocate_worker.requestInterruption()

    def _on_relocate_finished(
        self, repaired: int, skipped: int, unresolved: int, status: str
    ) -> None:
        if self._closing:
            return
        # I-1: ya terminó (ok/cancelled/error/blocked) — no queda nada que
        # perder, resetear el tracker de progreso para la próxima corrida.
        self._relocate_progress_done = 0
        self._relocate_progress_total = 0

        # ── Resetear botón (mismo patrón que _on_finished/export_btn) ──────
        self._set_relocate_state("idle")

        parts: list[str] = []
        if repaired:
            parts.append(f"{repaired} reparada{'s' if repaired != 1 else ''}")
        if skipped:
            parts.append(f"{skipped} salteada{'s' if skipped != 1 else ''}")
        if unresolved:
            parts.append(f"{unresolved} sin coincidencias")
        summary = " · ".join(parts) if parts else "Sin enlaces rotos"

        if status == "blocked":
            self._footer.end_progress("Bloqueado — Traktor está abierto", "⚠")
            self.output_status.setText("bloqueado ⚠")
            self._set_status_style("warn")
            self.log_view.setVisible(False)
            self.preview_scroll.setVisible(True)
            dialogs.warning(
                self, "Traktor está abierto",
                "Cerrá Traktor antes de reparar enlaces.\n\n"
                "Traktor reescribe collection.nml entero al salir o guardar "
                "(no bloquea el archivo a nivel de OS), así "
                "que si queda abierto pisaría las reparaciones.",
            )
            QTimer.singleShot(8000, self._hide_progress_section)
            return
        elif status == "cancelled":
            self._footer.end_progress(f"Cancelado — {summary}", "⏹")
            self.output_status.setText("cancelado")
            self._set_status_style("warn")
        elif status == "error":
            self._footer.end_progress(summary or "Error durante el relocate", "✗")
            self.output_status.setText("error ✗")
            self._set_status_style("error")
            # El relocate ESCRIBE sobre la librería del usuario: un fallo de
            # backup/escritura/DB no puede quedar solo en un label chico que
            # se oculta al terminar (el log_view se esconde abajo). Modal claro
            # + puntero al log rotativo, donde el worker dejó el detalle.
            try:
                from app_logging import log_dir
                log_path = log_dir() / "listBuddy.log"
            except Exception:
                log_path = None
            app_name = "Rekordbox" if self._relocate_source == "rekordbox" else "Traktor"
            if app_name == "Rekordbox":
                detail = (
                    "No se pudieron guardar las reparaciones. "
                    "Tu XML y Rekordbox no se tocaron."
                )
            else:
                detail = (
                    "La reparación de enlaces falló y no se escribió nada sobre tu "
                    f"librería de {app_name} (el backup y la escritura son atómicos: "
                    "o se aplica todo, o queda intacto)."
                )
            if log_path is not None:
                detail += f"\n\nRevisá el detalle del error en el log:\n{log_path}"
            dialogs.critical(self, f"Error al reparar enlaces — {app_name}", detail)
        elif unresolved > 0:
            self._footer.end_progress(summary, "⚠")
            self.output_status.setText("parcial ⚠")
            self._set_status_style("warn")
        else:
            self._footer.end_progress(summary, "✓")
            self.output_status.setText("reparado ✓")
            self._set_status_style("ok")

        self._log(f"\n{'⏹' if status == 'cancelled' else '✓'}  {summary}")

        self.log_view.setVisible(False)
        self.preview_scroll.setVisible(True)

        if status == "ok" and repaired > 0:
            # El NML cambió: invalidar caches y recargar el árbol para que
            # el preview refleje los paths reparados (las pistas que ya no
            # están rotas dejan de figurar "en rojo").
            self._log("↻  Recargando playlists con los enlaces reparados…")
            self._reload_after_path_change()

        QTimer.singleShot(8000, self._hide_progress_section)

    # ──────────────────────────────────────── Restore backup (B-4, T-019) ─
    #
    # Flujo NUEVO y separado del relocate normal (T-002/T-003/T-009/T-018):
    # esto es para cuando el USUARIO quiere volver atrás, no para cuando la
    # app escribe. Reusa `_relocate_target_info()` (B-2) para saber dónde
    # vive el archivo real de la fuente activa, y las mismas protecciones de
    # seguridad que el resto del write path: app de origen cerrada, confirmación
    # explícita, escritura atómica (relocate_core.restore_backup).

    def _open_restore_backup_dialog(self) -> None:
        """Entrypoint del botón "↩ Restaurar copia de seguridad…"."""
        if not self._repair_supported():
            return
        if self._worker and self._worker.isRunning():
            dialogs.warning(
                self, "Exportación en curso",
                "Esperá a que termine la exportación actual antes de "
                "restaurar un backup.",
            )
            return
        if self._relocate_worker and self._relocate_worker.isRunning():
            dialogs.warning(
                self, "Reparación en curso",
                "Esperá a que termine la reparación de enlaces antes de "
                "restaurar un backup.",
            )
            return
        if self._restore_worker and self._restore_worker.isRunning():
            return

        target_name, target_path = self._relocate_target_info()
        if target_path is None:
            app_name = "Traktor"
            dialogs.warning(
                self, "Sin ubicación conocida",
                f"No se pudo determinar dónde vive tu {target_name} de "
                f"{app_name} — no hay carpeta de backups para mostrar.",
            )
            return

        backups = list_backups(target_path, "collection.*.nml")

        dlg = RestoreBackupDialog(backups, target_name, self)
        dlg.exec()
        if dlg.chosen_backup is None:
            return

        self._start_restore_backup(dlg.chosen_backup, target_name, target_path)

    def _start_restore_backup(
        self, backup: BackupInfo, target_name: str, target_path: Path,
    ) -> None:
        """
        `backup` es un `relocate_core.BackupInfo`. Mismas protecciones que
        el resto del write path: (a) app de origen cerrada — reusa
        `is_traktor_running`, ya existente, no se
        duplica el chequeo; (b) confirmación explícita con la fecha del
        backup elegido; (c) escritura atómica en un QThread (no congelar la
        UI copiando un collection.nml grande).
        """
        app_name = "Traktor"
        if is_traktor_running():
            dialogs.warning(
                self, f"{app_name} está abierto",
                f"Cerrá {app_name} antes de restaurar un backup — la "
                "restauración reemplaza el archivo real y una app abierta "
                "podría estar leyéndolo, o pisarlo de nuevo al cerrar.",
            )
            return

        when = (
            backup.timestamp.strftime("%d/%m/%Y %H:%M:%S")
            if backup.timestamp is not None else backup.path.name
        )
        yes = dialogs.question(
            self, f"Restaurar copia de seguridad — {app_name}",
            f"Esto va a reemplazar tu {target_name} actual con la copia "
            f"del {when} — ¿seguro?\n\n"
            f"Archivo que se sobrescribe:\n{target_path}\n\n"
            "Tus otros backups no se tocan y siguen disponibles si te "
            f"equivocás de copia.\n\n{_RESPONSIBILITY_LINE}",
        )
        if not yes:
            return

        self._set_maintenance_enabled(False)
        self.output_status.setText("restaurando…")
        self._set_status_style("active")

        self._restore_worker = RestoreBackupWorker(backup.path, target_path)
        self._retain_thread(self._restore_worker)
        self._restore_worker.finished_ok.connect(
            lambda ok, err: self._on_restore_backup_finished(ok, err, target_name)
        )
        self._restore_worker.start()

    def _on_restore_backup_finished(self, ok: bool, error_msg: str, target_name: str) -> None:
        if self._closing:
            return
        app_name = "Traktor"
        self._set_maintenance_enabled(True)

        if ok:
            self.output_status.setText("restaurado ✓")
            self._set_status_style("ok")
            dialogs.information(
                self, "Backup restaurado",
                f"Tu {target_name} de {app_name} fue reemplazado por la "
                f"copia elegida.\n\nAbrí {app_name} para confirmar que todo "
                "esté como esperás.",
            )
        else:
            self.output_status.setText("error ✗")
            self._set_status_style("error")
            dialogs.critical(
                self, "No se pudo restaurar el backup",
                f"Algo falló al restaurar sobre tu {target_name}:\n\n"
                f"{error_msg}\n\n"
                "El archivo original no se tocó (la restauración escribe a "
                "un archivo temporal primero; si falla, no reemplaza nada).",
            )

    # ──────────────────────────────────────── Theme ───────────────────────

    def _apply_theme(self, theme: str) -> None:
        self._theme = theme
        self.settings.setValue("theme", theme)
        from styles import load_qss
        from ui_components import PlaylistCard as _PC
        _PC.set_theme(theme)
        # app.setStyleSheet re-pulea cada widget recorriendo sus hijos (≈1,7 ms por
        # widget de fila a profundidad 15): con la vista previa llena eran ~4 s.
        # Se destruyen las filas antes y se re-encolan después (T-070).
        pending = self._rendered_groups + self._render_queue
        if pending:
            self._clear_preview_layout(immediate=True)
        app = QApplication.instance()
        if app:
            app.setStyleSheet(load_qss(theme))
        for grp in self.findChildren(PlaylistGroup):
            grp.set_theme(theme)
        # Refresh cards so their inline stylesheets use new theme colors
        for card in self._all_cards:
            if card.isChecked():
                card._refresh()
        self._sync_theme_toggle(theme)
        self._sync_source_buttons()
        self._footer.apply_theme(theme)
        self._retint_icons()
        # Re-tint del highlight de la fila sonando con el accent del nuevo tema
        self._set_row_playing(self._playing_row, True)
        for data in pending:
            self._queue_group(data)
        try:
            self.theme_action.setChecked(theme == "light")
        except Exception:
            pass

    def _sync_theme_toggle(self, theme: str) -> None:
        # D5b: el ícono muestra el tema ACTUAL (luna en dark, sol en light).
        self._apply_icon(self._theme_btn, "moon" if theme == "dark" else "sun", "muted", 16)

    def _show_donation(self) -> None:
        DonationDialog(self).exec()

    def _show_about(self) -> None:
        AboutDialog(_APP_VERSION, self._theme, self).exec()

    # ── T-021 (I-8): chequeo de actualización ───────────────────────────────

    def _start_update_check(self) -> None:
        """
        Lanza el chequeo en background. Se llama una sola vez al final de
        __init__, después de que la ventana ya está armada — el resultado
        (si llega) solo agrega un label discreto, nunca bloquea el arranque.
        """
        if not self._check_updates:
            return
        self._update_worker = UpdateCheckWorker(_APP_VERSION)
        self._update_worker.update_available.connect(self._on_update_available)
        self._update_worker.start()

    def _on_update_available(self, info: UpdateInfo) -> None:
        if self._closing:
            return
        self._update_url = info.url
        self._update_banner.setText(f"🔔  Nueva versión {info.version} disponible")
        self._update_strip.setVisible(True)

    def _open_update_link(self) -> None:
        # Segunda barrera: aunque _update_url cambie de dueño, solo se abre una URL válida.
        url = safe_release_url(self._update_url)
        if url:
            QDesktopServices.openUrl(QUrl(url))
