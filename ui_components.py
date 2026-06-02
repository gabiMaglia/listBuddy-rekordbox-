from __future__ import annotations

from typing import List

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QGraphicsOpacityEffect,
    QHBoxLayout,
    QLabel,
    QVBoxLayout,
    QWidget,
)

class PlaylistCard(QWidget):
    toggled = pyqtSignal(object)

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
        self.setProperty("card_state", "")
        # Required for rgba() backgrounds to render on QWidget
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setCursor(
            Qt.CursorShape.ForbiddenCursor
            if self._empty
            else Qt.CursorShape.PointingHandCursor
        )

        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 9, 12, 9)
        layout.setSpacing(11)

        # Large mono order number
        self._order_label = QLabel(str(index + 1).zfill(2))
        self._order_label.setObjectName("card_order")
        self._order_label.setProperty("card_state", "")
        self._order_label.setFixedWidth(34)
        self._order_label.setAlignment(
            Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
        )
        layout.addWidget(self._order_label)

        # Name + track count tag
        info = QWidget()
        info.setObjectName("card_info")
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
        self._check.setProperty("card_state", "")
        self._check.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._check.setFixedSize(21, 21)
        layout.addWidget(self._check)

        if self._empty:
            effect = QGraphicsOpacityEffect(self)
            effect.setOpacity(0.38)
            self.setGraphicsEffect(effect)

    def _refresh(self) -> None:
        state = "on" if self._checked else ""
        for w in (self, self._order_label, self._check):
            w.setProperty("card_state", state)
            w.style().unpolish(w)
            w.style().polish(w)
        self._check.setText("✓" if self._checked else "")

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
        h_layout.setContentsMargins(12, 7, 12, 7)
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
        self._body_layout.setContentsMargins(0, 0, 0, 0)
        self._body_layout.setSpacing(0)
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
