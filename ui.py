"""
ui.py — List Buddy MainWindow
Layout: header-bar (title + controls) → two-column body
  Left  : rack-head · destination · playlist cards · progress · export
  Right : output preview (groups + scrollable file list)
"""
from __future__ import annotations

import itertools
import math
from io import BytesIO
from pathlib import Path

from PyQt6.QtCore import Qt, QTimer, QUrl, QSettings, pyqtSignal
from PyQt6.QtGui import (
    QColor,
    QDesktopServices,
    QMouseEvent,
    QPainter,
    QPixmap,
)
from PyQt6.QtWidgets import (
    QApplication,
    QDialog,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPlainTextEdit,
    QProgressBar,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)
from PyQt6.QtGui import QAction

from db import get_playlist_tree as rb_get_playlist_tree
from db import open_database as rb_open_database
from db import playlist_song_count as rb_song_count
from worker import ExportWorker
from ui_components import PlaylistCard, PlaylistGroup

_KOFI_URL = "https://ko-fi.com/gabrielmaglia"
_APP_VERSION = "1.0"


# ─────────────────────────────────────────── VU bars (decorative) ────────

class VuBars(QWidget):
    _BASE = [10, 16, 22, 26, 19, 12, 24, 17, 9, 14]

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._phase = 0.0
        self._live = False
        self._accent = QColor(206, 125, 230)
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._tick)
        self.setFixedSize(54, 26)

    def set_accent(self, hex_color: str) -> None:
        self._accent = QColor(hex_color)
        self.update()

    def set_live(self, live: bool) -> None:
        self._live = live
        if live:
            self._timer.start(55)
        else:
            self._timer.stop()
            self._phase = 0.0
            self.update()

    def _tick(self) -> None:
        self._phase += 0.20
        self.update()

    def paintEvent(self, _event) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        n = len(self._BASE)
        h = self.height()
        bar_w = max(2, self.width() // n - 2)

        c = QColor(self._accent)
        c.setAlphaF(0.70)

        for i, base_h in enumerate(self._BASE):
            if self._live:
                scale = 0.35 + 0.65 * abs(math.sin(self._phase + i * 0.72))
            else:
                scale = 0.25 + 0.12 * abs(math.sin(i * 0.9))
            bh = max(2, int(base_h * scale))
            x = i * (bar_w + 2)
            y = h - bh
            p.fillRect(x, y, bar_w, bh, c)


# ────────────────────────────────────── Export button with badge ──────────

class ExportWidget(QWidget):
    clicked = pyqtSignal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("export_widget")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setMinimumHeight(50)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self._enabled = True

        lo = QHBoxLayout(self)
        lo.setContentsMargins(14, 0, 18, 0)
        lo.setSpacing(10)
        lo.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self._badge = QLabel("00")
        self._badge.setObjectName("export_badge")
        self._badge.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        lo.addWidget(self._badge)

        self._text = QLabel("Exportar en orden")
        self._text.setObjectName("export_text")
        self._text.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        lo.addWidget(self._text)

    def mousePressEvent(self, event: QMouseEvent) -> None:
        if self._enabled and event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit()
        super().mousePressEvent(event)

    def set_count(self, n: int) -> None:
        self._badge.setText(str(n).zfill(2))

    def set_label(self, text: str) -> None:
        self._text.setText(text)

    def setEnabled(self, val: bool) -> None:  # type: ignore[override]
        self._enabled = val
        self.setCursor(
            Qt.CursorShape.ArrowCursor if not val else Qt.CursorShape.PointingHandCursor
        )
        prop = "true" if not val else "false"
        self.setProperty("export_disabled", prop)
        self._badge.setProperty("export_disabled", prop)
        self._text.setProperty("export_disabled", prop)
        for w in (self, self._badge, self._text):
            w.style().unpolish(w)
            w.style().polish(w)

    def isEnabled(self) -> bool:  # type: ignore[override]
        return self._enabled


# ─────────────────────────────────────────────── Donation dialog ──────────

class DonationDialog(QDialog):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("donation_dialog")
        self.setWindowTitle("Apoyar — List Buddy")
        self.setFixedSize(310, 400)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(28, 24, 28, 24)
        layout.setSpacing(14)

        title = QLabel("¿Te sirvió List Buddy?")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setStyleSheet("font-size:15px; font-weight:700;")
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
        try:
            import qrcode  # type: ignore
            qr = qrcode.QRCode(box_size=5, border=2)
            qr.add_data(_KOFI_URL)
            qr.make(fit=True)
            img = qr.make_image(fill_color="black", back_color="white")
            buf = BytesIO()
            img.save(buf, format="PNG")
            px = QPixmap()
            px.loadFromData(buf.getvalue())
            return px.scaled(
                180, 180,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
        except Exception:
            return None


# ─────────────────────────────────────────────────── MainWindow ──────────

class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("List Buddy")
        self.resize(980, 700)
        self.setMinimumSize(820, 560)
        self.setObjectName("rb_main")

        self._db = None
        self._worker: ExportWorker | None = None
        self._all_cards: list[PlaylistCard] = []
        self._source: str = "rekordbox"  # "rekordbox" | "traktor"

        settings_path = Path(__file__).parent / ".rbe_settings.ini"
        self.settings = QSettings(str(settings_path), QSettings.Format.IniFormat)
        self._theme = str(self.settings.value("theme", "dark"))

        central = QWidget()
        central.setObjectName("central_widget")
        central.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        root_layout = QVBoxLayout(central)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)

        root_layout.addWidget(self._build_header())
        root_layout.addWidget(self._build_body(), 1)

        self.setCentralWidget(central)

        # Minimal menu
        view_menu = self.menuBar().addMenu("Ver")
        self.theme_action = QAction("Tema claro", self)
        self.theme_action.setCheckable(True)
        self.theme_action.setChecked(self._theme == "light")
        self.theme_action.triggered.connect(
            lambda checked: self._apply_theme("light" if checked else "dark")
        )
        view_menu.addAction(self.theme_action)
        help_menu = self.menuBar().addMenu("Ayuda")
        help_menu.addAction("☕  Donar en Ko-fi…").triggered.connect(self._show_donation)

        from styles import load_qss
        app = QApplication.instance()
        if app:
            app.setStyleSheet(load_qss(self._theme))
        self._sync_theme_toggle(self._theme)
        self._vu_bars.set_accent(
            "#ce7de6" if self._theme == "dark" else "#8c38bf"
        )

        self._load_playlists()

    # ──────────────────────────────────────── Widget builders ────────────

    def _build_header(self) -> QWidget:
        """Thin title bar: title+version center, donate+toggle right."""
        bar = QWidget()
        bar.setObjectName("header_bar")
        bar.setFixedHeight(42)
        bar.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        lo = QHBoxLayout(bar)
        lo.setContentsMargins(14, 0, 12, 0)
        lo.setSpacing(8)

        lo.addStretch(1)

        title_lbl = QLabel("List Buddy")
        title_lbl.setObjectName("header_title")
        lo.addWidget(title_lbl)

        ver_lbl = QLabel(_APP_VERSION)
        ver_lbl.setObjectName("version_pill")
        lo.addWidget(ver_lbl)

        lo.addStretch(1)

        donate_btn = QPushButton("♥  Apoyar")
        donate_btn.setObjectName("donate_btn")
        donate_btn.clicked.connect(self._show_donation)
        lo.addWidget(donate_btn)

        toggle = QWidget()
        toggle.setObjectName("theme_toggle")
        t_lo = QHBoxLayout(toggle)
        t_lo.setContentsMargins(2, 2, 2, 2)
        t_lo.setSpacing(0)

        self._sun_btn = QPushButton("☀")
        self._sun_btn.setObjectName("theme_sun")
        self._moon_btn = QPushButton("🌙")
        self._moon_btn.setObjectName("theme_moon")
        self._sun_btn.clicked.connect(lambda: self._apply_theme("light"))
        self._moon_btn.clicked.connect(lambda: self._apply_theme("dark"))
        t_lo.addWidget(self._sun_btn)
        t_lo.addWidget(self._moon_btn)

        lo.addWidget(toggle)
        return bar

    def _build_body(self) -> QWidget:
        body = QWidget()
        body.setObjectName("body_widget")
        body.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        lo = QHBoxLayout(body)
        lo.setContentsMargins(18, 18, 18, 18)
        lo.setSpacing(16)
        lo.addWidget(self._build_left_col())
        lo.addWidget(self._build_right_col(), 1)
        return body

    # ── Left column ──────────────────────────────────────────────────────

    def _build_left_col(self) -> QWidget:
        col = QWidget()
        col.setObjectName("left_col")
        col.setFixedWidth(344)
        lo = QVBoxLayout(col)
        lo.setContentsMargins(0, 0, 0, 0)
        lo.setSpacing(14)

        lo.addWidget(self._build_rack_head())
        lo.addWidget(self._build_source_switcher())
        lo.addWidget(self._build_dest_section())
        lo.addWidget(self._build_playlists_header())
        lo.addWidget(self._build_playlist_scroll(), 1)
        lo.addWidget(self._build_progress_section())
        lo.addWidget(self._build_export_widget())
        return col

    def _build_rack_head(self) -> QWidget:
        """lb-rackhead: logo + brand + VU bars."""
        rack = QWidget()
        rack.setObjectName("rack_head")
        rack.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        lo = QHBoxLayout(rack)
        lo.setContentsMargins(14, 12, 14, 12)
        lo.setSpacing(11)

        logo = QLabel("♪")
        logo.setObjectName("brand_logo_text")
        logo.setAlignment(Qt.AlignmentFlag.AlignCenter)
        logo.setFixedSize(34, 34)
        lo.addWidget(logo)

        brand_block = QWidget()
        brand_block.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        bl = QVBoxLayout(brand_block)
        bl.setContentsMargins(0, 0, 0, 0)
        bl.setSpacing(1)
        name_lbl = QLabel("List Buddy")
        name_lbl.setObjectName("brand_name")
        sub_lbl = QLabel("EXPORT ENGINE")
        sub_lbl.setObjectName("brand_sub")
        bl.addWidget(name_lbl)
        bl.addWidget(sub_lbl)
        lo.addWidget(brand_block, 1)

        self._vu_bars = VuBars()
        lo.addWidget(self._vu_bars)
        return rack

    def _build_source_switcher(self) -> QWidget:
        """Segmented control: Rekordbox | Traktor."""
        wrap = QWidget()
        wrap.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        wrap.setObjectName("source_switcher")
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

    def _switch_source(self, source: str) -> None:
        if source == self._source:
            return
        self._source = source
        # Update button states
        self._src_rb_btn.setProperty("src_active", "true" if source == "rekordbox" else "false")
        self._src_tk_btn.setProperty("src_active", "true" if source == "traktor" else "false")
        for btn in (self._src_rb_btn, self._src_tk_btn):
            btn.style().unpolish(btn)
            btn.style().polish(btn)
        self._load_playlists()

    def _build_dest_section(self) -> QWidget:
        wrap = QWidget()
        wrap.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        wl = QVBoxLayout(wrap)
        wl.setContentsMargins(0, 0, 0, 0)
        wl.setSpacing(7)

        ey = QLabel("CARPETA DE DESTINO")
        ey.setObjectName("eyebrow")
        wl.addWidget(ey)

        dest_row = QWidget()
        dest_row.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        dr = QHBoxLayout(dest_row)
        dr.setContentsMargins(0, 0, 0, 0)
        dr.setSpacing(8)

        path_row = QWidget()
        path_row.setObjectName("path_row_widget")
        path_row.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        pr = QHBoxLayout(path_row)
        pr.setContentsMargins(12, 0, 8, 0)
        pr.setSpacing(8)

        fi = QLabel("▭")
        fi.setObjectName("path_folder_icon")
        pr.addWidget(fi)

        self.folder_edit = QLineEdit()
        self.folder_edit.setObjectName("folder_edit")
        self.folder_edit.setPlaceholderText("Elegí dónde exportar…")
        self.folder_edit.textChanged.connect(self._on_path_changed)
        pr.addWidget(self.folder_edit, 1)

        dr.addWidget(path_row, 1)

        browse_btn = QPushButton("Elegir…")
        browse_btn.setObjectName("browse_btn")
        browse_btn.clicked.connect(self._choose_folder)
        dr.addWidget(browse_btn)

        wl.addWidget(dest_row)
        return wrap

    def _build_playlists_header(self) -> QWidget:
        row = QWidget()
        row.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        rl = QHBoxLayout(row)
        rl.setContentsMargins(0, 0, 0, 0)
        rl.setSpacing(8)

        ey = QLabel("PLAYLISTS")
        ey.setObjectName("eyebrow")
        rl.addWidget(ey)

        self.count_pill = QLabel("0 / 0")
        self.count_pill.setObjectName("count_pill")
        rl.addWidget(self.count_pill)
        rl.addStretch(1)

        self.all_btn = QPushButton("Todas")
        self.all_btn.setObjectName("all_btn")
        self.all_btn.clicked.connect(lambda: self._set_all(True))
        rl.addWidget(self.all_btn)

        self.none_btn = QPushButton("Ninguna")
        self.none_btn.setObjectName("none_btn")
        self.none_btn.clicked.connect(lambda: self._set_all(False))
        rl.addWidget(self.none_btn)

        return row

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
        self.playlist_container_layout.setContentsMargins(0, 0, 0, 0)
        self.playlist_container_layout.setSpacing(0)
        self.playlist_container_layout.addStretch(1)

        scroll.setWidget(self.playlist_container)
        return scroll

    def _build_progress_section(self) -> QWidget:
        self.progress_section = QWidget()
        self.progress_section.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.progress_section.setVisible(False)
        pl = QVBoxLayout(self.progress_section)
        pl.setContentsMargins(0, 0, 0, 0)
        pl.setSpacing(5)

        label_row = QWidget()
        label_row.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        lr = QHBoxLayout(label_row)
        lr.setContentsMargins(0, 0, 0, 0)
        lr.setSpacing(0)
        self.prog_label = QLabel("Copiando y numerando…")
        self.prog_label.setObjectName("prog_label")
        self.prog_pct = QLabel("0%")
        self.prog_pct.setObjectName("prog_pct")
        lr.addWidget(self.prog_label)
        lr.addStretch(1)
        lr.addWidget(self.prog_pct)
        pl.addWidget(label_row)

        self.progress = QProgressBar()
        self.progress.setObjectName("progress")
        self.progress.setTextVisible(False)
        self.progress.setValue(0)
        pl.addWidget(self.progress)

        return self.progress_section

    def _build_export_widget(self) -> ExportWidget:
        self.export_btn = ExportWidget()
        self.export_btn.set_count(0)
        self.export_btn.setEnabled(False)
        self.export_btn.clicked.connect(self._start_export)
        return self.export_btn

    # ── Right column ─────────────────────────────────────────────────────

    def _build_right_col(self) -> QWidget:
        col = QWidget()
        col.setObjectName("right_col")
        col.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        lo = QVBoxLayout(col)
        lo.setContentsMargins(0, 0, 0, 0)
        lo.setSpacing(10)

        # Eyebrow + status
        head_row = QWidget()
        head_row.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        hl = QHBoxLayout(head_row)
        hl.setContentsMargins(0, 0, 0, 0)
        hl.setSpacing(8)
        ey = QLabel("SALIDA · VISTA PREVIA")
        ey.setObjectName("output_eyebrow")
        hl.addWidget(ey)
        self.output_status = QLabel("en espera")
        self.output_status.setObjectName("output_status_tag")
        hl.addWidget(self.output_status)
        hl.addStretch(1)
        lo.addWidget(head_row)

        # Output panel
        panel = QWidget()
        panel.setObjectName("output_panel")
        panel.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        panel_lo = QVBoxLayout(panel)
        panel_lo.setContentsMargins(0, 0, 0, 0)
        panel_lo.setSpacing(0)

        # Panel header — destination path
        self.output_head = QWidget()
        self.output_head.setObjectName("output_head")
        self.output_head.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        oh = QHBoxLayout(self.output_head)
        oh.setContentsMargins(14, 10, 14, 10)
        oh.setSpacing(8)
        fi = QLabel("▭")
        fi.setObjectName("output_folder_icon")
        self.output_path_label = QLabel("Sin carpeta seleccionada")
        self.output_path_label.setObjectName("output_path_label")
        self.output_path_label.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred
        )
        oh.addWidget(fi)
        oh.addWidget(self.output_path_label, 1)
        panel_lo.addWidget(self.output_head)

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
        self.preview_layout.setContentsMargins(12, 10, 12, 10)
        self.preview_layout.setSpacing(10)
        self.preview_scroll.setWidget(self.preview_container)
        panel_lo.addWidget(self.preview_scroll, 1)

        # Log view (during/after export)
        self.log_view = QPlainTextEdit()
        self.log_view.setObjectName("log_view")
        self.log_view.setReadOnly(True)
        self.log_view.setVisible(False)
        panel_lo.addWidget(self.log_view, 1)

        lo.addWidget(panel, 1)
        return col

    # ──────────────────────────────────────── Load playlists ─────────────

    def _load_playlists(self) -> None:
        """Load playlists from the active source (Rekordbox or Traktor)."""
        self._clear_playlist_area()

        try:
            if self._source == "traktor":
                from traktor_db import (
                    open_collection,
                    get_playlist_tree,
                    playlist_song_count,
                )
                col = open_collection()
                tree = get_playlist_tree(col)
                self._db = col
            else:
                tree = rb_get_playlist_tree(rb_open_database())
                playlist_song_count = rb_song_count
        except RuntimeError as e:
            self._show_not_installed(str(e))
            return

        card_index = 0
        layout = self.playlist_container_layout

        def add_node(node: dict, group: PlaylistGroup | None = None) -> None:
            nonlocal card_index
            pl = node["playlist"]
            if pl.is_folder:
                grp = PlaylistGroup(pl.Name)
                layout.insertWidget(layout.count() - 1, grp)
                for child in node["children"]:
                    add_node(child, grp)
            else:
                count = playlist_song_count(pl)
                card = PlaylistCard(pl, count, index=card_index)
                card.toggled.connect(self._on_card_toggled)
                card_index += 1
                self._all_cards.append(card)
                if group is not None:
                    group.add_card(card)
                else:
                    layout.insertWidget(layout.count() - 1, card)

        for node in tree:
            add_node(node)

        self._update_order_numbers()
        src_label = "Traktor" if self._source == "traktor" else "Rekordbox"
        self._log(f"♪ {len(self._all_cards)} playlist(s) cargada(s) desde {src_label}.")

    def _clear_playlist_area(self) -> None:
        self._all_cards.clear()
        layout = self.playlist_container_layout
        for i in reversed(range(layout.count())):
            item = layout.itemAt(i)
            w = item.widget() if item else None
            if w:
                w.setParent(None)  # type: ignore[arg-type]

    def _show_not_installed(self, detail: str) -> None:
        """Show a friendly 'not installed' placeholder in the playlist area."""
        self._clear_playlist_area()

        app_name = "Traktor Pro 3 / 4" if self._source == "traktor" else "Rekordbox 6"
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

        title = QLabel(f"{app_name} no encontrado")
        title.setObjectName("not_installed_title")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        cl.addWidget(title)

        sub = QLabel(detail)
        sub.setObjectName("not_installed_sub")
        sub.setAlignment(Qt.AlignmentFlag.AlignCenter)
        sub.setWordWrap(True)
        cl.addWidget(sub)

        self.playlist_container_layout.insertWidget(
            self.playlist_container_layout.count() - 1, card
        )
        self._update_order_numbers()

    # ──────────────────────────────────────── Order tracking ─────────────

    def _on_card_toggled(self, _card: PlaylistCard) -> None:
        self._update_order_numbers()

    def _update_order_numbers(self) -> None:
        selected: list[PlaylistCard] = []
        selectable = 0
        for card in self._all_cards:
            if not card._empty:
                selectable += 1
            if card.isChecked():
                selected.append(card)

        sel_pos = 0
        for i, card in enumerate(self._all_cards):
            if card.isChecked():
                card.set_order_num(str(sel_pos + 1).zfill(2))
                sel_pos += 1
            else:
                card.set_order_num(str(i + 1).zfill(2))

        n = len(selected)
        self.count_pill.setText(f"{n} / {selectable}")
        self.export_btn.set_count(n)
        self.export_btn.setEnabled(n > 0)

        if n == 0:
            self.output_status.setText("en espera")
        else:
            self.output_status.setText(
                f"{n} carpeta{'s' if n != 1 else ''} · numeración independiente"
            )

        if hasattr(self, "preview_scroll") and self.preview_scroll.isVisible():
            self._update_output_preview()

    # ──────────────────────────────────────── Output preview ─────────────

    def _update_output_preview(self) -> None:
        lo = self.preview_layout
        while lo.count():
            item = lo.takeAt(0)
            w = item.widget()
            if w:
                w.deleteLater()

        selected = [c for c in self._all_cards if c.isChecked()]

        if not selected:
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
            return

        for idx, card in enumerate(selected):
            lo.addWidget(self._build_output_group(card, idx + 1))

        lo.addStretch(1)

    def _build_output_group(self, card: PlaylistCard, order: int) -> QWidget:
        from rekordbox_export import get_songs, get_content, get_artist, sanitize

        grp = QWidget()
        grp.setObjectName("output_grp")
        grp.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        gl = QVBoxLayout(grp)
        gl.setContentsMargins(0, 0, 0, 0)
        gl.setSpacing(0)

        # Group header
        head = QWidget()
        head.setObjectName("output_grp_head")
        head.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        hl = QHBoxLayout(head)
        hl.setContentsMargins(13, 9, 13, 9)
        hl.setSpacing(8)
        badge = QLabel(str(order).zfill(2))
        badge.setObjectName("output_grp_badge")
        badge.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        hl.addWidget(badge)
        fname_lbl = QLabel(f"▭  {card.playlist.Name} /")
        fname_lbl.setObjectName("output_grp_fname")
        hl.addWidget(fname_lbl, 1)
        cnt_lbl = QLabel(f"{card._track_count} archivos")
        cnt_lbl.setObjectName("output_grp_cnt")
        hl.addWidget(cnt_lbl)
        gl.addWidget(head)

        # Scrollable file list — all tracks
        inner_scroll = QScrollArea()
        inner_scroll.setObjectName("grp_inner_scroll")
        inner_scroll.setWidgetResizable(True)
        inner_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        inner_scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        inner_scroll.setFixedHeight(160)
        inner_scroll.viewport().setObjectName("grp_inner_scroll_vp")

        files_widget = QWidget()
        files_widget.setObjectName("grp_files_container")
        files_layout = QVBoxLayout(files_widget)
        files_layout.setContentsMargins(0, 2, 0, 4)
        files_layout.setSpacing(0)

        try:
            songs = list(get_songs(card.playlist))
            for i, song in enumerate(songs):
                content = get_content(song)
                if content is None:
                    continue
                title = sanitize(str(getattr(content, "Title", "") or "") or "?")
                artist = get_artist(content)
                artist_s = sanitize(str(artist)) if artist else ""
                raw_path = getattr(content, "FolderPath", "") or ""
                ext = Path(raw_path).suffix.lower() if raw_path else ""

                row = QWidget()
                row.setObjectName("output_file_row")
                row.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
                rl = QHBoxLayout(row)
                rl.setContentsMargins(13, 4, 13, 4)
                rl.setSpacing(7)

                idx_lbl = QLabel(str(i + 1).zfill(2))
                idx_lbl.setObjectName("output_file_idx")
                rl.addWidget(idx_lbl)

                display_title = title if len(title) <= 46 else title[:44] + "…"
                name_lbl = QLabel(f"{i + 1:03d} - {display_title}")
                name_lbl.setObjectName("output_file_name")
                rl.addWidget(name_lbl, 1)

                if artist_s:
                    ar_display = artist_s if len(artist_s) <= 22 else artist_s[:20] + "…"
                    ar_lbl = QLabel(f"— {ar_display}")
                    ar_lbl.setObjectName("output_file_artist")
                    rl.addWidget(ar_lbl)

                if ext:
                    ext_lbl = QLabel(ext)
                    ext_lbl.setObjectName("output_file_ext")
                    rl.addWidget(ext_lbl)

                files_layout.addWidget(row)

            files_layout.addStretch(1)
        except Exception as e:
            err = QLabel(f"  (no disponible: {e})")
            err.setObjectName("output_file_more")
            files_layout.addWidget(err)

        inner_scroll.setWidget(files_widget)
        gl.addWidget(inner_scroll)

        return grp

    # ──────────────────────────────────────── Actions ────────────────────

    def _choose_folder(self) -> None:
        folder = QFileDialog.getExistingDirectory(self, "Elegí la carpeta de destino")
        if folder:
            self.folder_edit.setText(folder)

    def _on_path_changed(self, text: str) -> None:
        if text.strip():
            display = text if len(text) <= 52 else "…" + text[-50:]
            self.output_path_label.setText(display)
        else:
            self.output_path_label.setText("Sin carpeta seleccionada")

    def _set_all(self, checked: bool) -> None:
        for card in self._all_cards:
            card.setChecked(checked)
        self._update_order_numbers()

    def _selected_playlists(self) -> list:
        return [c.playlist for c in self._all_cards if c.isChecked()]

    # ──────────────────────────────────────── Export ─────────────────────

    def _start_export(self) -> None:
        output = self.folder_edit.text().strip()
        if not output:
            QMessageBox.warning(self, "Falta carpeta", "Elegí primero una carpeta de destino.")
            return
        selected = self._selected_playlists()
        if not selected:
            QMessageBox.warning(self, "Sin selección", "Marcá al menos una playlist.")
            return

        self.export_btn.setEnabled(False)
        self.export_btn.set_label("Exportando…")
        self.progress_section.setVisible(True)
        self.progress.setValue(0)
        self.prog_label.setText("Copiando y numerando…")
        self.output_status.setText("exportando…")
        self._vu_bars.set_live(True)
        self.preview_scroll.setVisible(False)
        self.log_view.setVisible(True)
        self.log_view.clear()
        self._log(f"▭ Destino: {output}")

        self._worker = ExportWorker(selected, Path(output))
        self._worker.log.connect(self._log)
        self._worker.progress.connect(self._on_progress)
        self._worker.finished_ok.connect(self._on_finished)
        self._worker.start()

    def _on_progress(self, done: int, total: int) -> None:
        self.progress.setMaximum(total)
        self.progress.setValue(done)
        pct = int(done / total * 100) if total > 0 else 0
        self.prog_pct.setText(f"{pct}%")

    def _on_finished(self, copied: int, missing: int) -> None:
        self.export_btn.setEnabled(True)
        self.export_btn.set_label("Exportar en orden")
        self.prog_label.setText("Exportación completa")
        self.prog_pct.setText("100%")
        self.output_status.setText("exportado ✓")
        self._vu_bars.set_live(False)
        self._log(f"\n✓ Listo. {copied} copiadas, {missing} no encontradas.")
        QMessageBox.information(
            self, "Exportación terminada",
            f"Copiadas: {copied}\nNo encontradas: {missing}",
        )
        self.log_view.setVisible(False)
        self.preview_scroll.setVisible(True)

    def _log(self, text: str) -> None:
        self.log_view.appendPlainText(text)

    # ──────────────────────────────────────── Theme ───────────────────────

    def _apply_theme(self, theme: str) -> None:
        self._theme = theme
        self.settings.setValue("theme", theme)
        from styles import load_qss
        app = QApplication.instance()
        if app:
            app.setStyleSheet(load_qss(theme))
        self._sync_theme_toggle(theme)
        self._vu_bars.set_accent(
            "#ce7de6" if theme == "dark" else "#8c38bf"
        )
        try:
            self.theme_action.setChecked(theme == "light")
        except Exception:
            pass

    def _sync_theme_toggle(self, theme: str) -> None:
        is_light = theme == "light"
        self._sun_btn.setProperty("active", "true" if is_light else "false")
        self._moon_btn.setProperty("active", "true" if not is_light else "false")
        for btn in (self._sun_btn, self._moon_btn):
            btn.style().unpolish(btn)
            btn.style().polish(btn)

    def _show_donation(self) -> None:
        DonationDialog(self).exec()
