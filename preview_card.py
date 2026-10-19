# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2025-2026 Gabriel Maglia
"""Tarjeta de carpeta de la vista previa (T-065): cabecera con estado + filas en scroll interno.

Sin animaciones ni timers propios: el fade-in lo hace MainWindow (T-029).
"""
from __future__ import annotations

from collections.abc import Callable

from PySide6.QtCore import QSize, Qt, Signal
from PySide6.QtWidgets import (
    QHBoxLayout, QLabel, QPushButton, QScrollArea, QScrollBar, QSizePolicy, QVBoxLayout, QWidget,
)

import icons
import row_blocks as rb
from preview_worker import GroupData
from styles import apply_caps_tracking, token
from ui_components import broken_badge_text

ROW_HEIGHT = 38
# Anchos compartidos con las filas (ui._make_row_widget) para que la cabecera de columnas alinee.
IDX_W = 56
CHIP_W = 68
KEYBPM_W = 84   # «10B · 127.5» en mono 11 px cabe con aire
WARN_W = 16
ROW_GAP = 12
# Por debajo de este ancho de fila la columna KEY · BPM se oculta (cabecera y filas): a 820 px de
# ventana la fila mide ~460 px y el título perdería un tercio de su ancho (T-067).
KEYBPM_MIN_ROW_W = 560
INITIAL_ROWS = 12           # filas que se construyen al crear la tarjeta (T-089); el resto, al scrollear
ROW_MARGIN = 6              # filas de aire que se construyen por encima/debajo de lo visible
ROWS_VISIBLE_HEIGHT = 190   # ≈ 5 filas de 38 px (D2): las demás se alcanzan con el scroll interno


class PreviewGroupCard(QWidget):
    repair_requested = Signal()        # «Reparar enlaces» (estado partial): alcance = esta carpeta
    auto_resolve_requested = Signal()  # «Auto-resolver» (estado all_broken): alcance = esta carpeta
    expand_toggled = Signal(bool)      # chevron del estado all_broken
    close_requested = Signal()         # ✕ de T-015

    def __init__(self, data: GroupData, theme: str, parent: QWidget | None = None,
                 can_repair: bool = True) -> None:
        super().__init__(parent)
        self.setObjectName("preview_card")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.state = rb.group_state(len(data.tracks), data.missing_count)
        self._title: QLabel | None = None
        self._data = data
        # Filas perezosas (T-089): ventana contigua [_lo, _hi) entre dos espaciadores de alto fijo,
        # así el scroll mide lo mismo que con todas las filas construidas.
        self._rows: list[tuple[object, str]] = []
        self._row_factory: Callable[..., QWidget] | None = None
        self._reserve_note = False
        self._built: list[QWidget] = []
        self._lo = 0
        self._hi = 0
        self._top_spacer: QWidget | None = None
        self._bottom_spacer: QWidget | None = None
        self.scroll_bar_width = QScrollBar().sizeHint().width()
        self._expanded = self.state != rb.ALL_BROKEN
        self._theme = theme
        n_broken = data.missing_count

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        self._head = QWidget()
        self._head.setObjectName("preview_card_head")
        self._head.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self._head.setProperty("state", self.state)
        self._head.setProperty("expanded", "true" if self._expanded else "false")
        head_col = QVBoxLayout(self._head)
        head_col.setContentsMargins(14, 10, 14, 10)
        head_col.setSpacing(6)
        top = QHBoxLayout()
        top.setSpacing(10)
        head_col.addLayout(top)

        folder = QLabel()
        folder.setObjectName("card_folder_icon")
        folder.setPixmap(icons.pixmap(
            "folder", token(theme, "danger" if self.state == rb.ALL_BROKEN else "muted"), 16))
        top.addWidget(folder)

        title = QLabel(f"{data.order:02d} {data.name}")
        title.setObjectName("card_title")
        title.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        self._title = title
        top.addWidget(title, 1)
        count = QLabel(f"{data.total_count} archivos")
        count.setObjectName("card_count")
        top.addWidget(count)

        self.expand_btn: QPushButton | None = None
        if self.state == rb.OK:
            top.addWidget(self._status_icon("check", "ok"))
            top.addWidget(self._status_label(rb_text="todo ok"))
        elif self.state == rb.PARTIAL:
            top.addWidget(self._status_icon("warning", "danger"))
            top.addWidget(self._status_label(rb_text=broken_badge_text(n_broken)))
            if can_repair:
                top.addWidget(self._action_btn(
                    "card_repair_btn", "Reparar enlaces", "Reparar enlaces de esta carpeta…",
                    self._on_repair_clicked))
        elif self.state == rb.ALL_BROKEN:
            top.addWidget(self._status_icon("warning", "danger"))
            if can_repair:
                top.addWidget(self._action_btn(
                    "card_auto_btn", "Auto-resolver", "Auto-resolver esta carpeta…",
                    self._on_auto_clicked))
            self.expand_btn = QPushButton()
            self.expand_btn.setObjectName("card_expand_btn")
            self.expand_btn.setCursor(Qt.CursorShape.PointingHandCursor)
            self.expand_btn.clicked.connect(self._on_expand_clicked)
            top.addWidget(self.expand_btn)
            msg = self._status_label(rb_text=rb.all_broken_text(n_broken))
            msg.setWordWrap(True)
            head_col.addWidget(msg)
            self._sync_expand_btn()

        if data.card is not None:
            close = QPushButton()
            close.setObjectName("card_close_btn")
            close.setIcon(icons.icon("close", token(theme, "muted"), 12))
            close.setIconSize(QSize(12, 12))
            close.setToolTip("Sacar esta playlist de la cola (destilda en la lista)")
            close.setAccessibleName("Quitar playlist de la cola")
            close.setCursor(Qt.CursorShape.PointingHandCursor)
            close.clicked.connect(self._on_close_clicked)
            top.addWidget(close)
        root.addWidget(self._head)

        self.cols = QWidget()
        self.cols.setObjectName("card_cols")
        self.cols.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        cl = QHBoxLayout(self.cols)
        # Si el scroll interno muestra barra, las filas son más angostas: la cabecera cede lo mismo.
        bar_w = self.scroll_bar_width if len(data.tracks) * ROW_HEIGHT > ROWS_VISIBLE_HEIGHT else 0
        cl.setContentsMargins(14, 6, 14 + bar_w, 6)
        cl.setSpacing(ROW_GAP)
        self.keybpm_head: QLabel | None = None
        for text, width, stretch in (
            ("NÚMERO", IDX_W, 0), ("TÍTULO — ARTISTA", 0, 1), ("KEY · BPM", KEYBPM_W, 0),
            ("FORMATO", CHIP_W, 0),
        ):
            lbl = QLabel(text)
            lbl.setObjectName("card_col_label")
            if width:
                lbl.setFixedWidth(width)
            else:
                lbl.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
            apply_caps_tracking(lbl, 11)
            cl.addWidget(lbl, stretch)
            if text == "KEY · BPM":
                self.keybpm_head = lbl
        root.addWidget(self.cols)

        self.scroll = QScrollArea()
        self.scroll.setObjectName("card_scroll")
        self.scroll.setWidgetResizable(True)
        self.scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        self.scroll.setFixedHeight(
            min(ROWS_VISIBLE_HEIGHT, max(ROW_HEIGHT, len(data.tracks) * ROW_HEIGHT)))
        self.scroll.viewport().setObjectName("card_scroll_vp")
        files = QWidget()
        files.setObjectName("grp_files_container")
        self.files_layout = QVBoxLayout(files)
        self.files_layout.setContentsMargins(0, 0, 0, 0)
        self.files_layout.setSpacing(0)
        self._top_spacer = self._make_spacer()
        self._bottom_spacer = self._make_spacer()
        self.files_layout.addWidget(self._top_spacer)
        self.files_layout.addWidget(self._bottom_spacer)
        self.files_layout.addStretch(1)
        self.scroll.setWidget(files)
        bar = self.scroll.verticalScrollBar()
        bar.valueChanged.connect(self._on_scrolled)
        bar.rangeChanged.connect(self._on_scrolled)
        root.addWidget(self.scroll)

        self.cols.setVisible(self._expanded)
        self.scroll.setVisible(self._expanded)

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        if self.keybpm_head is not None:
            bar = self.scroll_bar_width if self.scroll.verticalScrollBar().isVisible() else 0
            self.keybpm_head.setVisible(self.width() - bar >= KEYBPM_MIN_ROW_W)

    # ── piezas de la cabecera ───────────────────────────────────────────
    def _status_icon(self, name: str, color_token: str) -> QLabel:
        lbl = QLabel()
        lbl.setObjectName("card_status_icon")
        lbl.setPixmap(icons.pixmap(name, token(self._theme, color_token), 14))
        return lbl

    def _status_label(self, rb_text: str) -> QLabel:
        lbl = QLabel(rb_text)
        lbl.setObjectName("card_status")
        lbl.setProperty("state", self.state)
        return lbl

    def _action_btn(self, name: str, text: str, tip: str, slot) -> QPushButton:
        btn = QPushButton(text)
        btn.setObjectName(name)
        btn.setToolTip(tip)
        btn.setAccessibleName(tip)
        btn.setCursor(Qt.CursorShape.PointingHandCursor)
        btn.clicked.connect(slot)
        return btn

    # ── API ─────────────────────────────────────────────────────────────
    def is_expanded(self) -> bool:
        return self._expanded

    def set_order(self, order: int) -> None:
        """Renumera el título sin tocar las filas (al tildar/destildar otra playlist)."""
        self._data.order = order
        if self._title is not None:
            self._title.setText(f"{order:02d} {self._data.name}")

    @staticmethod
    def _make_spacer() -> QWidget:
        spacer = QWidget()
        spacer.setFixedHeight(0)
        spacer.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        return spacer

    def set_lazy_rows(
        self, rows: list[tuple[object, str]], factory: Callable[..., QWidget],
        reserve_note: bool,
    ) -> None:
        """Registra las filas (pista, posición de bloque) y construye solo las primeras. Una
        carpeta 100 % rota colapsada no construye nada hasta expandirse (D4)."""
        self._rows = rows
        self._row_factory = factory
        self._reserve_note = reserve_note
        self._sync_spacers()
        if self._expanded:
            self._ensure_window()

    @property
    def data(self) -> GroupData:
        return self._data

    def built_row_count(self) -> int:
        return len(self._built)

    def _need_range(self) -> tuple[int, int]:
        n = len(self._rows)
        if not self._built:
            return 0, min(n, INITIAL_ROWS)
        bar = self.scroll.verticalScrollBar()
        first = bar.value() // ROW_HEIGHT
        last = (bar.value() + self.scroll.viewport().height()) // ROW_HEIGHT + 1
        return max(0, first - ROW_MARGIN), min(n, last + ROW_MARGIN)

    def _on_scrolled(self, *_: int) -> None:
        if self._expanded:
            self._ensure_window()

    def _ensure_window(self) -> None:
        if self._row_factory is None or not self._rows:
            return
        need_lo, need_hi = self._need_range()
        if need_hi <= need_lo:
            return
        if self._built and (need_hi < self._lo or need_lo > self._hi):
            # Salto lejos de lo construido: se rehace la ventana en vez de rellenar el hueco.
            self._discard_rows()
        if not self._built:
            self._lo = self._hi = need_lo
        while self._lo > need_lo:
            self._lo -= 1
            self._add_row(self._lo, prepend=True)
        while self._hi < need_hi:
            self._add_row(self._hi, prepend=False)
            self._hi += 1
        self._sync_spacers()

    def _add_row(self, index: int, prepend: bool) -> None:
        """Inserta la fila entre los dos espaciadores (el layout empieza en el índice 1)."""
        assert self._row_factory is not None
        track, pos = self._rows[index]
        row = self._row_factory(track, pos, self._reserve_note)
        if prepend:
            self.files_layout.insertWidget(1, row)
            self._built.insert(0, row)
        else:
            self.files_layout.insertWidget(1 + len(self._built), row)
            self._built.append(row)

    def _discard_rows(self) -> None:
        for row in self._built:
            self.files_layout.removeWidget(row)
            row.hide()
            row.deleteLater()
        self._built.clear()
        self._lo = self._hi = 0

    def _sync_spacers(self) -> None:
        assert self._top_spacer is not None and self._bottom_spacer is not None
        if not self._built:
            self._top_spacer.setFixedHeight(0)
            self._bottom_spacer.setFixedHeight(len(self._rows) * ROW_HEIGHT)
            return
        self._top_spacer.setFixedHeight(self._lo * ROW_HEIGHT)
        self._bottom_spacer.setFixedHeight((len(self._rows) - self._hi) * ROW_HEIGHT)

    def set_expanded(self, on: bool) -> None:
        if self.state != rb.ALL_BROKEN or on == self._expanded:
            return
        self._expanded = on
        self.cols.setVisible(on)
        self.scroll.setVisible(on)
        if on:
            self._ensure_window()
        self._head.setProperty("expanded", "true" if on else "false")
        # Solo la cabecera de ESTA tarjeta se re-pulea (no hay re-polish global).
        self._head.style().unpolish(self._head)
        self._head.style().polish(self._head)
        self._sync_expand_btn()
        self.expand_toggled.emit(on)

    def _sync_expand_btn(self) -> None:
        if self.expand_btn is None:
            return
        name = "chevron_down" if self._expanded else "chevron_right"
        self.expand_btn.setIcon(icons.icon(name, token(self._theme, "muted"), 16))
        self.expand_btn.setIconSize(QSize(16, 16))
        label = "Contraer carpeta" if self._expanded else "Expandir carpeta"
        self.expand_btn.setAccessibleName(label)
        self.expand_btn.setToolTip(label)

    # Slots propios (sin lambdas que capturen widgets: T-029).
    def _on_repair_clicked(self) -> None:
        self.repair_requested.emit()

    def _on_auto_clicked(self) -> None:
        self.auto_resolve_requested.emit()

    def _on_expand_clicked(self) -> None:
        self.set_expanded(not self._expanded)

    def _on_close_clicked(self) -> None:
        self.close_requested.emit()
