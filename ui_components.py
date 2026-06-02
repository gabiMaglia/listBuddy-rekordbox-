from __future__ import annotations

from typing import ClassVar, List

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QGraphicsOpacityEffect,
    QHBoxLayout,
    QLabel,
    QVBoxLayout,
    QWidget,
)


# ──────────────────────── Theme-specific inline styles ───────────────────
# Usamos setStyleSheet() inline en lugar de unpolish/polish para evitar que
# Qt invalide el área de paint del parent y cause flicker en los siblings.

_CARD_STYLES: dict[str, dict[str, str]] = {
    "dark": {
        "card_on":   (
            "QWidget#playlist_card {"
            " background: rgba(206,125,230,30);"
            " border: 1.5px solid #b053d4;"
            " border-radius: 9px;"
            "}"
        ),
        "order_on":  "color: #ce7de6;",
        "check_on":  (
            "background: #ce7de6;"
            " border: 1.5px solid #b053d4;"
            " color: #1e0d29;"
            " border-radius: 6px;"
        ),
    },
    "light": {
        "card_on":   (
            "QWidget#playlist_card {"
            " background: rgba(140,56,191,20);"
            " border: 1.5px solid #7828ab;"
            " border-radius: 9px;"
            "}"
        ),
        "order_on":  "color: #8c38bf;",
        "check_on":  (
            "background: #8c38bf;"
            " border: 1.5px solid #7828ab;"
            " color: #fefefe;"
            " border-radius: 6px;"
        ),
    },
}


class PlaylistCard(QWidget):
    toggled: pyqtSignal = pyqtSignal(object)

    _theme: ClassVar[str] = "dark"

    @classmethod
    def set_theme(cls, theme: str) -> None:
        cls._theme = theme

    def __init__(
        self,
        playlist,
        count: int = 0,
        index: int = 0,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.playlist = playlist
        self._track_count = count
        self._checked = False
        self._empty = count == 0

        self.setObjectName("playlist_card")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setCursor(
            Qt.CursorShape.ForbiddenCursor
            if self._empty
            else Qt.CursorShape.PointingHandCursor
        )

        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 9, 13, 9)
        layout.setSpacing(12)

        # Large mono order number
        self._order_label = QLabel(str(index + 1).zfill(2))
        self._order_label.setObjectName("card_order")
        self._order_label.setFixedWidth(34)
        self._order_label.setAlignment(
            Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
        )
        layout.addWidget(self._order_label)

        # Name + meta tag
        info = QWidget()
        info.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        info_layout = QVBoxLayout(info)
        info_layout.setContentsMargins(0, 0, 0, 0)
        info_layout.setSpacing(4)

        self._name_label = QLabel(str(playlist.Name))
        self._name_label.setObjectName("card_name")
        info_layout.addWidget(self._name_label)

        meta_row = QWidget()
        meta_row.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        meta_layout = QHBoxLayout(meta_row)
        meta_layout.setContentsMargins(0, 0, 0, 0)
        meta_layout.setSpacing(5)

        tag_text = f"{count} tracks" if count > 0 else "vacía"
        self._tag = QLabel(tag_text)
        self._tag.setObjectName("card_tag")
        meta_layout.addWidget(self._tag)
        meta_layout.addStretch(1)
        info_layout.addWidget(meta_row)

        layout.addWidget(info, 1)

        # Check indicator
        self._check = QLabel()
        self._check.setObjectName("card_check")
        self._check.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._check.setFixedSize(21, 21)
        layout.addWidget(self._check)

        if self._empty:
            effect = QGraphicsOpacityEffect(self)
            effect.setOpacity(0.38)
            self.setGraphicsEffect(effect)

    # ── Refresh without unpolish/polish cascade ───────────────────────────

    def _refresh(self) -> None:
        """
        Actualiza la apariencia via setStyleSheet() directo.
        Evita unpolish/polish que invalida el parent y causa flicker en
        todos los siblings dentro del mismo QScrollArea.
        """
        on = self._checked
        s  = _CARD_STYLES.get(self._theme, _CARD_STYLES["dark"])

        if on:
            self.setStyleSheet(s["card_on"])
            self._order_label.setStyleSheet(s["order_on"])
            self._check.setStyleSheet(s["check_on"])
        else:
            # Vaciar inline stylesheet → retoma el QSS global
            self.setStyleSheet("")
            self._order_label.setStyleSheet("")
            self._check.setStyleSheet("")

        self._check.setText("✓" if on else "")

    # ─────────────────────────────────────────────────────────────────────

    def mousePressEvent(self, event) -> None:
        if not self._empty:
            self._checked = not self._checked
            self._refresh()
            self.toggled.emit(self)
        super().mousePressEvent(event)

    def set_order_num(self, s: str) -> None:
        self._order_label.setText(s)

    def setChecked(self, value: bool) -> None:
        if not self._empty:
            self._checked = value
            self._refresh()

    def isChecked(self) -> bool:
        return self._checked


class PlaylistGroup(QWidget):
    def __init__(self, name: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("playlist_group")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        header = QWidget()
        header.setObjectName("group_header")
        header.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        h_layout = QHBoxLayout(header)
        h_layout.setContentsMargins(12, 8, 12, 8)
        h_layout.setSpacing(8)

        icon = QLabel("▸")
        icon.setObjectName("group_icon")
        h_layout.addWidget(icon)

        title = QLabel(name)
        title.setObjectName("group_title")
        h_layout.addWidget(title, 1)

        layout.addWidget(header)

        self._body = QWidget()
        self._body.setObjectName("group_body")
        self._body.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self._body_layout = QVBoxLayout(self._body)
        self._body_layout.setContentsMargins(6, 4, 6, 6)
        self._body_layout.setSpacing(4)
        layout.addWidget(self._body)

    def add_card(self, card: PlaylistCard) -> None:
        self._body_layout.addWidget(card)

    def cards(self) -> List[PlaylistCard]:
        out: List[PlaylistCard] = []
        for i in range(self._body_layout.count()):
            w = self._body_layout.itemAt(i).widget()
            if isinstance(w, PlaylistCard):
                out.append(w)
        return out
