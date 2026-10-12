"""Íconos SVG de trazo, teñidos por token. Sin glifos Unicode: se ven igual en macOS y Windows."""
from __future__ import annotations

from PySide6.QtCore import QByteArray, Qt
from PySide6.QtGui import QGuiApplication, QIcon, QPainter, QPixmap
from PySide6.QtSvg import QSvgRenderer

ICON_NAMES: tuple[str, ...] = (
    "sun", "moon", "heart", "gear", "folder", "note",
    "play", "pause", "close", "chevron_right",
    "wrench", "logo", "dot", "arrow_right",
)

# Grilla 24x24; `{c}` se reemplaza por el color (también para los rellenos de play/pause).
_PATHS: dict[str, str] = {
    "sun": (
        '<circle cx="12" cy="12" r="4"/>'
        '<path d="M12 2v2M12 20v2M4.9 4.9l1.4 1.4M17.7 17.7l1.4 1.4'
        'M2 12h2M20 12h2M4.9 19.1l1.4-1.4M17.7 6.3l1.4-1.4"/>'
    ),
    "moon": '<path d="M21 12.8A9 9 0 1 1 11.2 3a7 7 0 0 0 9.8 9.8z"/>',
    "heart": (
        '<path d="M20.8 4.6a5.5 5.5 0 0 0-7.8 0L12 5.7l-1-1.1a5.5 5.5 0 0 0-7.8 7.8'
        'l1 1.1L12 21.2l7.8-7.7 1-1.1a5.5 5.5 0 0 0 0-7.8z"/>'
    ),
    "gear": (
        '<circle cx="12" cy="12" r="3"/>'
        '<path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 1 1-2.83 2.83l-.06-.06'
        'a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 1 1-4 0v-.09A1.65 1.65 0 0 0 9 19.4'
        'a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 1 1-2.83-2.83l.06-.06A1.65 1.65 0 0 0 4.68 15'
        'a1.65 1.65 0 0 0-1.51-1H3a2 2 0 1 1 0-4h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82'
        'l-.06-.06a2 2 0 1 1 2.83-2.83l.06.06A1.65 1.65 0 0 0 9 4.68a1.65 1.65 0 0 0 1-1.51V3'
        'a2 2 0 1 1 4 0v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06'
        'a2 2 0 1 1 2.83 2.83l-.06.06A1.65 1.65 0 0 0 19.4 9a1.65 1.65 0 0 0 1.51 1H21'
        'a2 2 0 1 1 0 4h-.09a1.65 1.65 0 0 0-1.51 1z"/>'
    ),
    "folder": '<path d="M3 7a2 2 0 0 1 2-2h4l2 2h8a2 2 0 0 1 2 2v8a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z"/>',
    "note": '<path d="M9 18V5l12-2v13"/><circle cx="6" cy="18" r="3"/><circle cx="18" cy="16" r="3"/>',
    "play": '<path fill="{c}" d="M8 5v14l11-7z"/>',
    "pause": '<path fill="{c}" d="M7 5h3v14H7zM14 5h3v14h-3z"/>',
    "close": '<path d="M6 6l12 12M18 6L6 18"/>',
    "chevron_right": '<path d="M9 6l6 6-6 6"/>',
    "wrench": '<path d="M14.7 6.3a4 4 0 0 0-5.4 5.4L3 18l3 3 6.3-6.3a4 4 0 0 0 5.4-5.4l-2.6 2.6-2.4-.6-.6-2.4z"/>',
    # Las 4 barras del logo (diseño, grilla 22 -> 24): rellenas, sin trazo.
    "logo": (
        '<rect x="3" y="10" width="3" height="10" rx="1" fill="{c}" stroke="none"/>'
        '<rect x="8" y="5" width="3" height="15" rx="1" fill="{c}" stroke="none"/>'
        '<rect x="13" y="8" width="3" height="12" rx="1" fill="{c}" stroke="none"/>'
        '<rect x="18" y="13" width="3" height="7" rx="1" fill="{c}" stroke="none"/>'
    ),
    "dot": '<circle cx="12" cy="12" r="6" fill="{c}" stroke="none"/>',
    "arrow_right": '<path d="M5 12h14M13 6l6 6-6 6"/>',
}

_WRAP = (
    '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" '
    'stroke="{c}" stroke-width="1.75" stroke-linecap="round" stroke-linejoin="round">{body}</svg>'
)


def pixmap(name: str, color: str, size: int = 16) -> QPixmap:
    screen = QGuiApplication.primaryScreen()
    dpr = screen.devicePixelRatio() if screen else 1.0
    px = QPixmap(int(size * dpr), int(size * dpr))
    px.fill(Qt.GlobalColor.transparent)
    svg = _WRAP.format(c=color, body=_PATHS[name].replace("{c}", color))
    renderer = QSvgRenderer(QByteArray(svg.encode()))
    painter = QPainter(px)
    renderer.render(painter)
    painter.end()
    px.setDevicePixelRatio(dpr)
    return px


def icon(name: str, color: str, size: int = 16) -> QIcon:
    return QIcon(pixmap(name, color, size))
