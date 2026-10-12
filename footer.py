"""footer.py — footer de 76 px: reproductor, destino, exportar y progreso (T-063)."""
from __future__ import annotations

from collections.abc import Sequence
from typing import Literal

from PySide6.QtCore import QSize, Qt, Signal
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QProgressBar,
    QPushButton,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

import icons
from styles import token
from ui_components import ElidedLabel, WaveformSeek

ExportMode = Literal["idle", "running", "cancelling"]


def export_label(n: int) -> str:
    if n <= 0:
        return "Exportar playlists"
    return f"Exportar {n} playlist" if n == 1 else f"Exportar {n} playlists"


def format_ms(ms: int) -> str:
    s = max(0, ms // 1000)
    return f"{s // 60}:{s % 60:02d}"


class FooterBar(QWidget):
    """Footer de 76 px. Sin lógica de negocio: señales hacia afuera, set_* hacia adentro."""

    play_clicked = Signal()
    seek_requested = Signal(int)
    change_dest_clicked = Signal()
    dest_changed = Signal(str)
    export_clicked = Signal()
    finder_clicked = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("footer_bar")
        self.setFixedHeight(76)
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self._theme = "dark"
        self._count = 0
        self._mode: ExportMode = "idle"
        self._play_name = "note"
        self._dest = ""
        self._progress_active = False

        lo = QHBoxLayout(self)
        lo.setContentsMargins(20, 0, 20, 0)
        lo.setSpacing(10)

        self.play_btn = QPushButton()
        self.play_btn.setObjectName("footer_play")
        self.play_btn.setFixedSize(40, 40)
        self.play_btn.setIconSize(QSize(18, 18))
        self.play_btn.setToolTip("Reproducir / pausar")
        self.play_btn.setAccessibleName("Reproducir / pausar")
        self.play_btn.clicked.connect(self.play_clicked)
        lo.addWidget(self.play_btn)

        info = QWidget()
        info.setMinimumWidth(100)
        info.setMaximumWidth(220)
        il = QVBoxLayout(info)
        il.setContentsMargins(0, 0, 0, 0)
        il.setSpacing(2)
        self.title_lbl = ElidedLabel()
        self.title_lbl.setObjectName("footer_title")
        self.artist_lbl = ElidedLabel()
        self.artist_lbl.setObjectName("footer_artist")
        il.addWidget(self.title_lbl)
        il.addWidget(self.artist_lbl)
        lo.addWidget(info, 2)

        wave_box = QWidget()
        wl = QHBoxLayout(wave_box)
        wl.setContentsMargins(0, 0, 0, 0)
        wl.setSpacing(10)
        self.time_cur = QLabel("0:00")
        self.time_cur.setObjectName("footer_time")
        self.wave = WaveformSeek()
        self.wave.seek_requested.connect(self.seek_requested)
        self.time_total = QLabel("0:00")
        self.time_total.setObjectName("footer_time")
        wl.addWidget(self.time_cur)
        wl.addWidget(self.wave, 1)
        wl.addWidget(self.time_total)
        lo.addWidget(wave_box, 4)

        # Destino y progreso comparten lugar: uno a la vez (D6).
        self._right = QStackedWidget()
        self._right.setMaximumWidth(340)
        self._right.setMinimumWidth(150)
        self._right.setFixedHeight(40)
        self._right.addWidget(self._build_dest())
        self._right.addWidget(self._build_progress())
        lo.addWidget(self._right, 5)

        self.export_btn = QPushButton()
        self.export_btn.setObjectName("footer_export")
        self.export_btn.setFixedHeight(44)
        self.export_btn.setLayoutDirection(Qt.LayoutDirection.RightToLeft)  # flecha a la derecha
        self.export_btn.setIconSize(QSize(16, 16))
        self.export_btn.clicked.connect(self.export_clicked)
        lo.addWidget(self.export_btn)

        self.apply_theme("dark")
        self.set_dest("")

    def _build_dest(self) -> QWidget:
        box = QWidget()
        box.setObjectName("footer_dest")
        box.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        hl = QHBoxLayout(box)
        hl.setContentsMargins(12, 0, 6, 0)
        hl.setSpacing(8)
        self._dest_icon = QLabel()
        self._dest_icon.setObjectName("footer_dest_icon")
        self.dest_label = ElidedLabel(Qt.TextElideMode.ElideLeft)
        self.dest_label.setObjectName("footer_dest_path")
        self.change_btn = QPushButton("Cambiar")
        self.change_btn.setObjectName("footer_dest_change")
        self.change_btn.setFixedHeight(28)
        self.change_btn.clicked.connect(self.change_dest_clicked)
        hl.addWidget(self._dest_icon)
        hl.addWidget(self.dest_label, 1)
        hl.addWidget(self.change_btn)
        return box

    def _build_progress(self) -> QWidget:
        box = QWidget()
        box.setObjectName("footer_progress")
        vl = QVBoxLayout(box)
        vl.setContentsMargins(0, 0, 0, 0)
        vl.setSpacing(6)
        row = QHBoxLayout()
        row.setSpacing(8)
        self.prog_label = ElidedLabel()
        self.prog_label.setObjectName("footer_prog_label")
        self.finder_btn = QPushButton("Abrir en Finder")
        self.finder_btn.setObjectName("footer_finder")
        self.finder_btn.setFixedHeight(24)
        self.finder_btn.hide()
        self.finder_btn.clicked.connect(self.finder_clicked)
        self.prog_pct = QLabel("0%")
        self.prog_pct.setObjectName("footer_prog_pct")
        row.addWidget(self.prog_label, 1)
        row.addWidget(self.finder_btn)
        row.addWidget(self.prog_pct)
        self.prog_bar = QProgressBar()
        self.prog_bar.setObjectName("footer_prog_bar")
        self.prog_bar.setTextVisible(False)
        self.prog_bar.setRange(0, 100)
        self.prog_bar.setFixedHeight(6)
        vl.addLayout(row)
        vl.addWidget(self.prog_bar)
        return box

    # ── Reproductor ──────────────────────────────────────────────

    def set_now_playing(self, title: str, artist: str) -> None:
        self.title_lbl.set_full_text(title)
        self.artist_lbl.set_full_text(artist)

    def set_play_glyph(self, name: Literal["play", "pause", "note"]) -> None:
        self._play_name = name
        self.play_btn.setIcon(icons.icon(name, token(self._theme, "on_accent"), 18))

    def set_position(self, pos_ms: int, dur_ms: int) -> None:
        self.wave.set_progress(pos_ms, dur_ms)
        self.time_cur.setText(format_ms(pos_ms))
        self.time_total.setText(format_ms(dur_ms))

    def set_peaks(self, peaks: Sequence[float] | None) -> None:
        self.wave.set_peaks(peaks)

    # ── Destino ──────────────────────────────────────────────────

    def set_dest(self, text: str) -> None:
        self._dest = text
        self.dest_label.set_full_text(text or "Elegí dónde exportar…")
        # Sin destino el placeholder necesita el lugar del ícono para entrar a 820 px.
        self._dest_icon.setVisible(bool(text))
        self.dest_label.setProperty("empty", not text)
        self.dest_label.style().unpolish(self.dest_label)
        self.dest_label.style().polish(self.dest_label)
        self.dest_changed.emit(text)

    def dest_text(self) -> str:
        return self._dest

    # ── Exportar ─────────────────────────────────────────────────

    def set_export_count(self, n: int) -> None:
        self._count = n
        self._refresh_export()

    def set_export_mode(self, mode: ExportMode) -> None:
        self._mode = mode
        self._refresh_export()

    def _refresh_export(self) -> None:
        if self._mode == "running":
            text, enabled = "Cancelar", True
        elif self._mode == "cancelling":
            text, enabled = "Cancelando…", False
        else:
            text, enabled = export_label(self._count), self._count > 0
        self.export_btn.setText(text)
        self.export_btn.setEnabled(enabled)
        arrow = self._mode == "idle" and enabled
        self.export_btn.setIcon(
            icons.icon("arrow_right", token(self._theme, "on_accent"), 16) if arrow else QIcon()
        )

    # ── Progreso ─────────────────────────────────────────────────

    def begin_progress(self, label: str) -> None:
        self._progress_active = True
        self.prog_label.set_full_text(label)
        self.prog_pct.setText("0%")
        self.prog_bar.setValue(0)
        self.finder_btn.hide()
        self._right.setCurrentIndex(1)

    def set_progress(self, done: int, total: int) -> None:
        self.prog_bar.setMaximum(max(total, 1))
        self.prog_bar.setValue(done)
        self.prog_pct.setText(f"{int(done / total * 100) if total > 0 else 0}%")

    def end_progress(self, label: str, glyph: str) -> None:
        # El resumen queda visible hasta hide_progress (timer de la ventana).
        self._progress_active = False
        self.prog_label.set_full_text(label)
        self.prog_pct.setText(glyph)

    def set_finder_visible(self, visible: bool) -> None:
        self.finder_btn.setVisible(visible)

    def hide_progress(self) -> None:
        if self._progress_active:
            return
        self._right.setCurrentIndex(0)
        self.finder_btn.hide()
        self.prog_bar.setValue(0)

    def progress_active(self) -> bool:
        return self._progress_active

    # ── Tema ─────────────────────────────────────────────────────

    def apply_theme(self, theme: str) -> None:
        self._theme = theme
        self.wave.set_colors(token(theme, "accent"), token(theme, "line"))
        self.set_play_glyph(self._play_name)  # type: ignore[arg-type]
        self._dest_icon.setPixmap(icons.pixmap("folder", token(theme, "muted"), 16))
        self._refresh_export()
