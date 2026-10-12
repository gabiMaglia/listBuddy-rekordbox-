"""Tarjeta de carpeta de la vista previa (T-065): cabecera con estado + filas en scroll interno.

Sin animaciones ni timers propios: el fade-in lo hace MainWindow (T-029).
"""
from __future__ import annotations

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
NOTE_W = 150    # «· archivo no encontrado»
WARN_W = 16
ROW_GAP = 12
ROWS_VISIBLE_HEIGHT = 190   # ≈ 5 filas de 38 px (D2): las demás se alcanzan con el scroll interno


class PreviewGroupCard(QWidget):
    repair_requested = Signal()        # «Reparar enlaces» (estado partial): alcance = esta carpeta
    auto_resolve_requested = Signal()  # «Auto-resolver» (estado all_broken): alcance = esta carpeta
    expand_toggled = Signal(bool)      # chevron del estado all_broken
    close_requested = Signal()         # ✕ de T-015

    def __init__(self, data: GroupData, theme: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("preview_card")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.state = rb.group_state(len(data.tracks), data.missing_count)
        self.rows_built = False
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
            top.addWidget(self._action_btn(
                "card_repair_btn", "Reparar enlaces", "Reparar enlaces de esta carpeta…",
                self._on_repair_clicked))
        elif self.state == rb.ALL_BROKEN:
            top.addWidget(self._status_icon("warning", "danger"))
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
        for text, width, stretch in (
            ("NÚMERO", IDX_W, 0), ("TÍTULO — ARTISTA", 0, 1), ("FORMATO", CHIP_W, 0),
        ):
            lbl = QLabel(text)
            lbl.setObjectName("card_col_label")
            if width:
                lbl.setFixedWidth(width)
            else:
                lbl.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
            apply_caps_tracking(lbl, 11)
            cl.addWidget(lbl, stretch)
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
        self.scroll.setWidget(files)
        root.addWidget(self.scroll)

        self.cols.setVisible(self._expanded)
        self.scroll.setVisible(self._expanded)

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

    def set_expanded(self, on: bool) -> None:
        if self.state != rb.ALL_BROKEN or on == self._expanded:
            return
        self._expanded = on
        self.cols.setVisible(on)
        self.scroll.setVisible(on)
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
