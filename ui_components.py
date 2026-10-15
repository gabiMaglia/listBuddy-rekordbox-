from __future__ import annotations

import math
from pathlib import Path
from collections.abc import Sequence
from typing import ClassVar, List

import numpy as np

import icons
import styles
from preview_worker import TrackRow
from row_blocks import NONE, border_sides, corner_radii
from waveform_worker import WaveData

from PySide6.QtCore import QEasingCurve, QEvent, QPoint, QRectF, QSize, Qt, QVariantAnimation, Signal
from PySide6.QtGui import (
    QColor,
    QFontMetrics,
    QMouseEvent,
    QPainter,
    QPainterPath,
    QPen,
    QPixmap,
)
from PySide6.QtWidgets import (
    QDialog,
    QGraphicsOpacityEffect,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QStyledItemDelegate,
    QStyleOptionViewItem,
    QPushButton,
    QSizePolicy,
    QStackedLayout,
    QVBoxLayout,
    QWidget,
)


# ───────────────────────── Botón Mantenimiento del header (T-062) ──

def broken_badge_text(n: int) -> str:
    """Texto del badge de Mantenimiento; vacío = sin badge."""
    if n <= 0:
        return ""
    return "1 roto" if n == 1 else f"{n} rotos"


class MaintenanceButton(QPushButton):
    """Botón del header: ícono + «Mantenimiento» + badge de rotos.

    Los hijos son QLabel transparentes al mouse para que todo el botón sea
    clickeable; sizeHint sale del layout porque QPushButton ignora sus hijos.
    """

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("maint_btn")
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFixedHeight(34)
        self.setAccessibleName("Mantenimiento")
        lo = QHBoxLayout(self)
        lo.setContentsMargins(12, 0, 12, 0)
        lo.setSpacing(8)
        self._icon = QLabel()
        self._icon.setObjectName("maint_icon")
        self._text = QLabel("Mantenimiento")
        self._text.setObjectName("maint_text")
        self._badge = QLabel()
        self._badge.setObjectName("maint_badge")
        self._badge.setFixedHeight(18)   # píldora chica: el radio del QSS es la mitad
        self._badge.setVisible(False)
        for w in (self._icon, self._text, self._badge):
            w.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
            lo.addWidget(w)
        lo.setAlignment(self._badge, Qt.AlignmentFlag.AlignVCenter)

    def icon_label(self) -> QLabel:
        return self._icon

    def set_broken(self, n: int) -> None:
        txt = broken_badge_text(n)
        self._badge.setText(txt)
        self._badge.setVisible(bool(txt))
        self.setAccessibleDescription(txt)

    def set_compact(self, compact: bool) -> None:
        self._text.setVisible(not compact)
        self.setToolTip("Mantenimiento" if compact else "")

    def sizeHint(self) -> QSize:
        return self.layout().sizeHint()

    def minimumSizeHint(self) -> QSize:
        return self.layout().sizeHint()


# ───────────────────────── Custom title bar (T-010, Windows-only chrome) ──

class TitleBar(QWidget):
    """
    Barra usada como chrome de ventana en `MainWindow._build_header()`
    (reemplaza el frame nativo de Windows — ventana frameless, ver
    `MainWindow.__init__`). Agrega drag-to-move y doble click para
    maximizar/restaurar sobre el fondo de la barra; los botones propios de
    minimizar/maximizar/cerrar son hijos normales y consumen su propio click,
    así que nunca disparan un arrastre.

    El resize por los bordes NO se maneja acá (T-016) — se resuelve con
    `_ResizeGrip` (ui.py), widgets finitos en los bordes/esquinas que llaman
    `self.windowHandle().startSystemResize(edge)` — API alto nivel de Qt6,
    sin ctypes ni lectura de structs nativos (ver D-06 en
    engram/03_backlog.md sobre el intento anterior con `nativeEvent()`).

    Windows-only por ahora: en otras plataformas la ventana conserva el
    frame nativo (`MainWindow` no aplica `FramelessWindowHint` fuera de
    win32), así que esta clase igual se instancia pero el drag/doble-click
    quedan sin efecto práctico porque el SO ya mueve/maximiza la ventana con
    su propio frame.
    """

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._drag_offset: QPoint | None = None

    def mousePressEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            win = self.window()
            self._drag_offset = event.globalPosition().toPoint() - win.frameGeometry().topLeft()
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        if self._drag_offset is not None and event.buttons() & Qt.MouseButton.LeftButton:
            win = self.window()
            if not win.isMaximized():
                win.move(event.globalPosition().toPoint() - self._drag_offset)
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        self._drag_offset = None
        super().mouseReleaseEvent(event)

    def mouseDoubleClickEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            win = self.window()
            win.showNormal() if win.isMaximized() else win.showMaximized()
        super().mouseDoubleClickEvent(event)


# ──────────────────────────────────────── Clickable note (♪) ─────────────

class ClickableLabel(QLabel):
    """QLabel que emite `clicked`. Usado para el ícono play/pausa/nota del rack-head."""

    clicked: Signal = Signal()

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit()
        super().mousePressEvent(event)


# ───────────────────────────────────────── Texto multilínea que no se corta ────

class WrapLabel(QLabel):
    """QLabel con word wrap que pide el alto real para su ancho.

    Un QLabel con wordWrap estima su alto con un ancho mayor al que termina
    teniendo; en una columna angosta las últimas líneas quedan recortadas.
    Al conocer su ancho final fija el alto mínimo que ese ancho necesita.
    """

    def __init__(self, text: str = "", parent: QWidget | None = None) -> None:
        super().__init__(text, parent)
        self.setWordWrap(True)

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        needed = self.heightForWidth(self.width())
        if needed > 0 and needed != self.minimumHeight():
            self.setMinimumHeight(needed)


# ─────────────────────────────────── Etiqueta con elipsis (footer, T-063) ────

class ElidedLabel(QLabel):
    """QLabel con elipsis (inicio o final) y tooltip = texto completo."""

    def __init__(
        self,
        mode: Qt.TextElideMode = Qt.TextElideMode.ElideRight,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._mode = mode
        self._full = ""
        # Ignored: el layout no le pide el ancho del texto completo.
        self.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        self.setMinimumWidth(0)

    def set_full_text(self, text: str) -> None:
        self._full = text
        self.setToolTip(text)
        self._apply()

    def full_text(self) -> str:
        return self._full

    def set_mode(self, mode: Qt.TextElideMode) -> None:
        self._mode = mode
        self._apply()

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self._apply()

    def changeEvent(self, event) -> None:
        super().changeEvent(event)
        if event.type() in (QEvent.Type.FontChange, QEvent.Type.StyleChange):
            self._apply()

    def _apply(self) -> None:
        width = self.width() - 2
        shown = (
            self.fontMetrics().elidedText(self._full, self._mode, width)
            if width > 0 else self._full
        )
        if shown != self.text():
            self.setText(shown)


class FileRow(QWidget):
    """
    Fila de archivo en el preview. Si el archivo existe, es clickeable y emite
    `clicked(raw_path)` para reproducir. Los faltantes quedan inertes.
    set_playing() usa setStyleSheet inline (no unpolish/polish) para evitar el
    flicker en cascada documentado en este archivo.
    """

    clicked: Signal = Signal(str)

    def __init__(
        self,
        raw_path: str,
        exists: bool,
        parent: QWidget | None = None,
        block_pos: str = NONE,
    ) -> None:
        super().__init__(parent)
        self._raw_path = raw_path
        self._exists = exists
        self.track: TrackRow | None = None   # el dato de la fila (lo fija MainWindow)
        self.keybpm_label: QWidget | None = None   # se oculta si la fila es angosta (T-067)
        self.block_pos = block_pos if not exists else NONE
        self.setObjectName("output_file_row")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setProperty("file_missing", "false" if exists else "true")
        if exists:
            self.setCursor(Qt.CursorShape.PointingHandCursor)

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        if self.keybpm_label is not None:
            from preview_card import KEYBPM_MIN_ROW_W   # import diferido: preview_card importa este módulo
            self.keybpm_label.setVisible(self.width() >= KEYBPM_MIN_ROW_W)

    def paintEvent(self, event) -> None:
        # Estilo D: los rotos contiguos se pintan como un solo bloque; el fondo y
        # el borde van acá porque QSS no puede dar radio por esquina según el vecino.
        if not self._exists:
            theme = PlaylistCard._theme
            self._paint_block(styles.token(theme, "broken_bg"), styles.token(theme, "danger"))
        else:
            # Separador de 1 px pintado acá: un border-bottom QSS pelearía con el bloque (T6).
            QPainter(self).fillRect(
                0, self.height() - 1, self.width(), 1,
                QColor(styles.token(PlaylistCard._theme, "row_line")),
            )
        super().paintEvent(event)

    def _paint_block(self, fill_hex: str, border_hex: str) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        w, h = float(self.width()), float(self.height())
        tl, tr, br, bl = (float(r) for r in corner_radii(self.block_pos))
        # Medio píxel adentro: el trazo de 1 px queda entero dentro del widget.
        x0, y0, x1, y1 = 0.5, 0.5, w - 0.5, h - 0.5
        top_b, right_b, bottom_b, left_b = border_sides(self.block_pos)

        def corner(
            path: QPainterPath, cx: float, cy: float, r: float, start: float, sweep: float = -90,
        ) -> None:
            # Qt mide los ángulos en sentido antihorario: -90 recorre la esquina en horario.
            if r:
                path.arcTo(QRectF(cx, cy, 2 * r, 2 * r), start, sweep)

        shape = QPainterPath()
        shape.moveTo(x0 + tl, y0)
        shape.lineTo(x1 - tr, y0)
        corner(shape, x1 - 2 * tr, y0, tr, 90)
        shape.lineTo(x1, y1 - br)
        corner(shape, x1 - 2 * br, y1 - 2 * br, br, 0)
        shape.lineTo(x0 + bl, y1)
        corner(shape, x0, y1 - 2 * bl, bl, 270)
        shape.lineTo(x0, y0 + tl)
        corner(shape, x0, y0, tl, 180)
        shape.closeSubpath()
        p.fillPath(shape, QColor(fill_hex))

        edge = QColor(border_hex)
        edge.setAlphaF(0.38)
        pen = QPen(edge)
        pen.setWidthF(1.0)
        p.setPen(pen)
        p.setBrush(Qt.BrushStyle.NoBrush)
        if all((top_b, right_b, bottom_b, left_b)):
            p.drawPath(shape)
            return
        # Bloque abierto: solo los lados exteriores (sin línea entre filas del bloque).
        open_path = QPainterPath()
        if top_b:  # START: izquierda -> arriba -> derecha
            open_path.moveTo(x0, y1 + 1)
            open_path.lineTo(x0, y0 + tl)
            corner(open_path, x0, y0, tl, 180)
            open_path.lineTo(x1 - tr, y0)
            corner(open_path, x1 - 2 * tr, y0, tr, 90)
            open_path.lineTo(x1, y1 + 1)
        elif bottom_b:  # END
            open_path.moveTo(x0, y0 - 1)
            open_path.lineTo(x0, y1 - bl)
            corner(open_path, x0, y1 - 2 * bl, bl, 180, 90)
            open_path.lineTo(x1 - br, y1)
            corner(open_path, x1 - 2 * br, y1 - 2 * br, br, 270, 90)
            open_path.lineTo(x1, y0 - 1)
        else:  # MIDDLE
            open_path.moveTo(x0, y0 - 1)
            open_path.lineTo(x0, y1 + 1)
            open_path.moveTo(x1, y0 - 1)
            open_path.lineTo(x1, y1 + 1)
        p.drawPath(open_path)

    def mousePressEvent(self, event) -> None:
        if self._exists and event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit(self._raw_path)
        super().mousePressEvent(event)

    def set_playing(self, playing: bool) -> None:
        if playing:
            theme = PlaylistCard._theme
            accent = styles.token(theme, "accent")
            soft = styles.token(theme, "sel_bg")
            self.setStyleSheet(
                "QWidget#output_file_row {"
                f" background: {soft};"
                f" border-left: 2px solid {accent};"
                "}"
            )
        else:
            self.setStyleSheet("")


class SeekBar(QWidget):
    """Barra de progreso clickeable/arrastrable. Emite seek_requested(ms)."""

    seek_requested: Signal = Signal(int)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._pos = 0
        self._dur = 0
        self._accent = QColor(styles.token("dark", "accent"))
        self.setFixedHeight(14)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)

    def set_accent(self, hex_color: str) -> None:
        self._accent = QColor(hex_color)
        self.update()

    def set_progress(self, pos: int, dur: int) -> None:
        self._pos = pos
        self._dur = dur
        self.update()

    def _fraction_at(self, x: int) -> float:
        w = max(1, self.width())
        return min(1.0, max(0.0, x / w))

    def mousePressEvent(self, event) -> None:
        self._emit_seek(event)

    def mouseMoveEvent(self, event) -> None:
        if event.buttons() & Qt.MouseButton.LeftButton:
            self._emit_seek(event)

    def _emit_seek(self, event) -> None:
        if self._dur <= 0:
            return
        frac = self._fraction_at(int(event.position().x()))
        self._pos = int(frac * self._dur)     # feedback inmediato
        self.update()
        self.seek_requested.emit(self._pos)

    def paintEvent(self, _event) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        h = self.height()
        track_h = 4
        y = (h - track_h) // 2
        radius = track_h / 2

        # Riel de fondo
        bg = QColor(self._accent)
        bg.setAlphaF(0.20)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(bg)
        p.drawRoundedRect(0, y, self.width(), track_h, radius, radius)

        # Porción reproducida
        if self._dur > 0:
            frac = min(1.0, self._pos / self._dur)
            fill_w = int(self.width() * frac)
            p.setBrush(self._accent)
            p.drawRoundedRect(0, y, fill_w, track_h, radius, radius)
            # Handle
            cx = fill_w
            p.drawEllipse(
                max(5, min(self.width() - 5, cx)) - 5, y + track_h // 2 - 5, 10, 10
            )


def bar_means(values: Sequence[float], n: int) -> list[float]:
    """n valores por promedio de cada tramo (mean-pool); sin datos, lista vacía."""
    if n <= 0 or len(values) == 0:
        return []
    arr = np.asarray(values, dtype=np.float64)
    idx = np.arange(n + 1) * arr.size // n
    starts = np.minimum(idx[:-1], arr.size - 1)
    ends = np.maximum(idx[1:], starts + 1)
    csum = np.concatenate([[0.0], np.cumsum(arr)])
    return ((csum[ends] - csum[starts]) / (ends - starts)).tolist()


def bar_heights(levels: Sequence[float], n: int, floor: float = 0.12) -> list[float]:
    """n alturas 0..1 por promedio de los niveles; sin datos, barras planas al piso."""
    if n <= 0:
        return []
    if len(levels) == 0:
        return [floor] * n
    return [max(floor, v) for v in bar_means(levels, n)]


def _mix(a: QColor, b: QColor, t: float) -> QColor:
    t = min(1.0, max(0.0, t))
    return QColor.fromRgbF(
        a.redF() + (b.redF() - a.redF()) * t,
        a.greenF() + (b.greenF() - a.greenF()) * t,
        a.blueF() + (b.blueF() - a.blueF()) * t,
    )


class WaveformSeek(SeekBar):
    """SeekBar con forma de onda: mismo click/arrastre, barras en vez de riel.

    Altura = energía (dB); color = tono (acento = graves → `hi` = agudos). Las barras se
    pre-renderizan UNA vez en dos pixmaps (reproducido / pendiente) y recién se vuelven a
    armar si cambian datos, tamaño, colores o DPR; cada tick de posición solo recorta.
    """

    _BAR, _GAP = 2, 1
    _GROW_MS = 400
    _PENDING_MIX = 0.72     # cuánto se acerca el color pendiente al color de reposo

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setFixedHeight(32)
        self._data: WaveData | None = None
        self._hi = QColor(styles.token("dark", "wave_hi"))
        self._rest = QColor(styles.token("dark", "line"))
        self._pm_played: QPixmap | None = None
        self._pm_pending: QPixmap | None = None
        self._pm_key: tuple | None = None
        self._rebuilds = 0
        self._grow = 1.0
        self._anim = QVariantAnimation(self)
        self._anim.setDuration(self._GROW_MS)
        self._anim.setStartValue(0.0)
        self._anim.setEndValue(1.0)
        self._anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        self._anim.valueChanged.connect(self._on_grow)

    def _on_grow(self, value: object) -> None:
        self._grow = float(value)  # type: ignore[arg-type]
        self.update()

    def set_wave(self, data: WaveData | None) -> None:
        if data is self._data:
            return                      # mismo objeto: no se reinicia la animación
        self._data = data
        self._anim.stop()
        if data is None or not data.levels:
            self._grow = 1.0            # piso plano inmediato, sin animar
        else:
            self._grow = 0.0
            self._anim.start()
        self.update()

    def set_colors(self, lo_hex: str, hi_hex: str, rest_hex: str) -> None:
        self._accent = QColor(lo_hex)
        self._hi = QColor(hi_hex)
        self._rest = QColor(rest_hex)
        self.update()

    def _bar_count(self) -> int:
        return max(1, (self.width() + self._GAP) // (self._BAR + self._GAP))

    def _ensure_pixmaps(self) -> None:
        dpr = self.devicePixelRatioF()
        key = (id(self._data), self.width(), self.height(), dpr,
               self._accent.rgba(), self._hi.rgba(), self._rest.rgba())
        if key == self._pm_key and self._pm_played is not None:
            return
        self._pm_key = key
        self._rebuilds += 1
        n = self._bar_count()
        d = self._data
        heights = bar_heights(d.levels if d else (), n)
        tones = bar_means(d.tone, n) if d and d.tone else [0.0] * n
        w, h = self.width(), self.height()
        pms: list[QPixmap] = []
        for pending in (False, True):
            pm = QPixmap(max(1, int(w * dpr)), max(1, int(h * dpr)))
            pm.setDevicePixelRatio(dpr)
            pm.fill(Qt.GlobalColor.transparent)
            p = QPainter(pm)
            p.setRenderHint(QPainter.RenderHint.Antialiasing, False)
            p.setPen(Qt.PenStyle.NoPen)
            mid = h / 2
            step = self._BAR + self._GAP
            for i, level in enumerate(heights):
                col = _mix(self._accent, self._hi, tones[i])
                if pending:
                    col = _mix(col, self._rest, self._PENDING_MIX)
                bh = max(2.0, level * (h - 2))
                p.setBrush(col)
                p.drawRect(QRectF(i * step, mid - bh / 2, self._BAR, bh))
            p.end()
            pms.append(pm)
        self._pm_played, self._pm_pending = pms

    def paintEvent(self, _event) -> None:
        self._ensure_pixmaps()
        assert self._pm_played is not None and self._pm_pending is not None
        p = QPainter(self)
        w, h = self.width(), self.height()
        if self._grow < 1.0:
            mid = h / 2
            p.setOpacity(self._grow)
            p.translate(0, mid)
            p.scale(1.0, self._grow)
            p.translate(0, -mid)
        p.drawPixmap(0, 0, self._pm_pending)
        frac = (self._pos / self._dur) if self._dur > 0 else 0.0
        step = self._BAR + self._GAP
        # La barra cuenta como reproducida si su centro ya fue pasado.
        played = min(self._bar_count(), max(0, math.floor(frac * w / step - self._BAR / 2 / step) + 1))
        cut = played * step
        if cut > 0:
            p.setClipRect(QRectF(0, 0, cut, h))
            p.drawPixmap(0, 0, self._pm_played)


class PlaylistCard(QWidget):
    toggled: Signal = Signal(object)

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
        layout.setContentsMargins(10, 8, 10, 8)
        layout.setSpacing(10)

        # Checkbox a la izquierda (diseño F1)
        self._check = QLabel()
        self._check.setObjectName("card_check")
        self._check.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._check.setFixedSize(18, 18)
        layout.addWidget(self._check)

        # Dos etiquetas de Nº apiladas: el estilo lo da la QSS por objectName y
        # alternar es setCurrentWidget (sin unpolish/polish, ver _refresh).
        self._num_holder = QWidget()
        self._num_holder.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self._num_holder.setFixedWidth(30)
        self._num_stack = QStackedLayout(self._num_holder)
        self._num_stack.setContentsMargins(0, 0, 0, 0)
        align = Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
        self._pos_label = QLabel(str(index + 1).zfill(2))
        self._pos_label.setObjectName("card_pos")
        self._pos_label.setAlignment(align)
        self._order_label = QLabel("")
        self._order_label.setObjectName("card_order")
        self._order_label.setAlignment(align)
        self._num_stack.addWidget(self._pos_label)
        self._num_stack.addWidget(self._order_label)
        self._num_stack.setCurrentWidget(self._pos_label)
        layout.addWidget(self._num_holder)

        # Nombre completo aparte: el label muestra una versión recortada con «…»
        # según el ancho real (resizeEvent); sin esto un nombre largo ensancha el
        # contenedor y el QScrollArea queda desplazable en horizontal.
        self._full_name = str(playlist.Name)
        self._name_label = QLabel(self._full_name)
        self._name_label.setObjectName("card_name")
        self._name_label.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        self._name_label.setToolTip(self._full_name)
        layout.addWidget(self._name_label, 1)

        self._tag = QLabel(f"{count} tracks" if count > 0 else "vacía")
        self._tag.setObjectName("card_tag")
        layout.addWidget(self._tag)

        if self._empty:
            effect = QGraphicsOpacityEffect(self)
            effect.setOpacity(0.38)
            self.setGraphicsEffect(effect)

    def resizeEvent(self, event) -> None:
        self._elide_name()
        super().resizeEvent(event)

    def _elide_name(self) -> None:
        """Recorta `_full_name` con '…' al ancho real del label — sin esto,
        un nombre largo fuerza el layout a ser más ancho que la columna y
        el QScrollArea de la lista queda desplazable horizontalmente."""
        width = self._name_label.width()
        if width <= 0:
            return
        fm = QFontMetrics(self._name_label.font())
        elided = fm.elidedText(self._full_name, Qt.TextElideMode.ElideRight, width)
        self._name_label.setText(elided)

    # ── Refresh without unpolish/polish cascade ───────────────────────────

    def _refresh(self) -> None:
        """
        Actualiza la apariencia via setStyleSheet() directo.
        Evita unpolish/polish que invalida el parent y causa flicker en
        todos los siblings dentro del mismo QScrollArea.
        """
        on = self._checked
        s = styles.card_styles(self._theme)
        if on:
            self.setStyleSheet(s["card_on"])
            self._check.setStyleSheet(s["check_on"])
            self._num_stack.setCurrentWidget(self._order_label)
        else:
            # Vaciar inline stylesheet → retoma el QSS global
            self.setStyleSheet("")
            self._check.setStyleSheet("")
            self._num_stack.setCurrentWidget(self._pos_label)
        self._check.setText("✓" if on else "")

    # ─────────────────────────────────────────────────────────────────────

    def mousePressEvent(self, event) -> None:
        if not self._empty:
            self._checked = not self._checked
            self._refresh()
            self.toggled.emit(self)
        super().mousePressEvent(event)

    @property
    def name(self) -> str:
        return self._full_name

    def set_numbers(self, position: int, order: int | None) -> None:
        """position: lugar en la lista (se ve sin marcar); order: rango de
        exportación (se ve marcada). Qué etiqueta se muestra lo decide _refresh."""
        self._pos_label.setText(f"{position:02d}")
        if order is not None:
            self._order_label.setText(f"{order:02d}")

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

        self._chevron = QLabel()
        self._chevron.setObjectName("group_icon")
        h_layout.addWidget(self._chevron)
        self.set_theme(PlaylistCard._theme)

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

    def set_theme(self, theme: str) -> None:
        self._chevron.setPixmap(icons.pixmap("chevron_right", styles.token(theme, "accent"), 14))

    def add_card(self, card: PlaylistCard) -> None:
        self._body_layout.addWidget(card)

    def cards(self) -> List[PlaylistCard]:
        out: List[PlaylistCard] = []
        for i in range(self._body_layout.count()):
            w = self._body_layout.itemAt(i).widget()
            if isinstance(w, PlaylistCard):
                out.append(w)
        return out


# ──────────────────────────── Modal de desambiguación (relocate) ─────────

def _fmt_size(num_bytes: int) -> str:
    size = float(num_bytes)
    for unit in ("B", "KB", "MB", "GB"):
        if size < 1024 or unit == "GB":
            return f"{size:.1f} {unit}" if unit != "B" else f"{int(size)} {unit}"
        size /= 1024
    return f"{size:.1f} GB"


class _ElideLinesDelegate(QStyledItemDelegate):
    """Qt solo elide bien texto de una línea: acá cada línea del ítem se recorta con «…»."""

    _H_PADDING = 9 * 2 + 8  # padding del QSS + margen de texto del estilo

    def initStyleOption(self, option: QStyleOptionViewItem, index) -> None:
        super().initStyleOption(option, index)
        width = max(option.rect.width() - self._H_PADDING, 0)
        # option.fontMetrics ignora el font-size del QSS; el widget sí lo tiene aplicado.
        fm = QFontMetrics(option.widget.font()) if option.widget is not None else option.fontMetrics
        # Qt reemplaza el \n del ítem por U+2028 en option.text.
        option.text = "\u2028".join(
            fm.elidedText(line, Qt.TextElideMode.ElideRight, width)
            for line in option.text.replace("\n", "\u2028").split("\u2028")
        )


class RelocateDialog(QDialog):
    """
    Modal de desambiguación (ADR-001, punto 3 y contrato del modal).
    Entrada: RelocateRequest (broken + candidates), inyectado por
    RelocateWorker.ask_user desde el hilo del worker (queued connection).
    Salida: `chosen_path` — Path elegido, o None si el usuario saltea la
    pista o cierra el modal sin elegir (sin default silencioso).
    El modal NO escribe nada; solo devuelve la decisión.
    """

    def __init__(self, request, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._request = request
        self.chosen_path: Path | None = None

        broken = request.broken
        self.setObjectName("relocate_dialog")
        self.setWindowTitle("Elegí el archivo correcto")
        self.setMinimumWidth(480)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(22, 20, 22, 18)
        layout.setSpacing(12)

        title = QLabel(f"Se encontraron {len(request.candidates)} coincidencias")
        title.setObjectName("relocate_title")
        title.setWordWrap(True)
        layout.addWidget(title)

        sub_text = broken.title or broken.original_path.name
        if broken.artist:
            sub_text = f"{broken.artist} — {sub_text}"
        sub = QLabel(f"Pista rota: {sub_text}")
        sub.setObjectName("relocate_sub")
        sub.setWordWrap(True)
        layout.addWidget(sub)

        orig = QLabel(f"Ruta original: {broken.original_path}")
        orig.setObjectName("relocate_orig")
        orig.setWordWrap(True)
        layout.addWidget(orig)

        self._list = QListWidget()
        self._list.setObjectName("relocate_list")
        self._list.setItemDelegate(_ElideLinesDelegate(self._list))
        self._list.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        for cand in request.candidates:
            hint_parts = []
            if cand.matched_artist or cand.matched_title:
                hint_parts.append(
                    " - ".join(p for p in (cand.matched_artist, cand.matched_title) if p)
                )
            hint = f"  ·  {hint_parts[0]}" if hint_parts else ""
            # T-028 (criterio 3): un candidato que solo matcheó por clave
            # normalizada (sin prefijo NN- y/o sin extensión exacta) se
            # marca explícito — no es el mismo nivel de certeza que un
            # nombre de archivo idéntico, y acá SIEMPRE requiere que el
            # usuario elija (nunca se auto-resuelve, ver relocate_core.py
            # `_run_resolution`).
            match_note = (
                "  ·  ⚠ coincidencia aproximada (nombre normalizado, no exacto)"
                if getattr(cand, "match_type", "exact") == "normalized"
                else ""
            )
            item = QListWidgetItem(
                f"{cand.path}\n{_fmt_size(cand.size)}  ·  score {cand.score:.2f}{hint}{match_note}"
            )
            item.setData(Qt.ItemDataRole.UserRole, cand.path)
            self._list.addItem(item)
        if self._list.count():
            self._list.setCurrentRow(0)
        self._list.itemDoubleClicked.connect(lambda _item: self._accept_selected())
        layout.addWidget(self._list, 1)

        btn_row = QWidget()
        bl = QHBoxLayout(btn_row)
        bl.setContentsMargins(0, 0, 0, 0)
        bl.setSpacing(8)

        skip_btn = QPushButton("Saltar (dejar sin reparar)")
        skip_btn.setObjectName("relocate_skip_btn")
        skip_btn.clicked.connect(self._reject_as_skip)
        bl.addWidget(skip_btn)
        bl.addStretch(1)

        use_btn = QPushButton("Usar este archivo")
        use_btn.setObjectName("relocate_use_btn")
        use_btn.clicked.connect(self._accept_selected)
        bl.addWidget(use_btn)

        layout.addWidget(btn_row)

    def _accept_selected(self) -> None:
        item = self._list.currentItem()
        if item is not None:
            self.chosen_path = item.data(Qt.ItemDataRole.UserRole)
        self.accept()

    def _reject_as_skip(self) -> None:
        self.chosen_path = None
        self.reject()

    def reject(self) -> None:  # type: ignore[override]
        # Cerrar el modal (X, Esc, o "Saltar") sin elegir = SKIP, nunca un
        # default silencioso (ADR-001, contrato del modal).
        self.chosen_path = None
        super().reject()


# ──────────────────────────── Modal de restauración de backup (B-4, T-019) ─

class RestoreBackupDialog(QDialog):
    """
    Modal de B-4: lista los backups disponibles de la fuente activa
    (Traktor o Rekordbox, cada una con su propia carpeta `listBuddy_backups`)
    con fecha/hora legible y tamaño (`_fmt_size`, la misma función que ya usa
    `RelocateDialog` para los candidatos). Si no hay backups, lo dice
    explícito en vez de mostrar una lista vacía confusa.

    Salida: `chosen_backup` — el `relocate_core.BackupInfo` elegido (con
    `.path`/`.timestamp`/`.size` ya resueltos, para que `ui.py` arme el
    texto de confirmación sin volver a parsear el nombre de archivo), o
    `None` si el usuario cancela/cierra sin elegir. Igual que
    `RelocateDialog`, este modal NO restaura nada — solo devuelve la
    decisión; `ui.py` hace el chequeo de la app de origen cerrada, la
    confirmación explícita ("esto va a reemplazar tu librería actual...")
    y la llamada real a `relocate_core.restore_backup` en background.
    """

    def __init__(
        self,
        backups: list,  # list[relocate_core.BackupInfo]
        target_name: str,  # "collection.nml"
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.chosen_backup = None  # relocate_core.BackupInfo | None

        self.setObjectName("restore_backup_dialog")
        self.setWindowTitle(f"Restaurar copia de seguridad — {target_name}")
        self.setMinimumWidth(480)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(22, 20, 22, 18)
        layout.setSpacing(12)

        title = QLabel(f"Copias de seguridad de {target_name}")
        title.setObjectName("relocate_title")
        title.setWordWrap(True)
        layout.addWidget(title)

        if not backups:
            empty = QLabel(
                "Todavía no hay copias de seguridad para esta librería.\n\n"
                "Se crea una automáticamente la primera vez que uses "
                "\"Reparar enlaces rotos…\" sobre ella."
            )
            empty.setObjectName("relocate_sub")
            empty.setWordWrap(True)
            layout.addWidget(empty)

            btn_row = QWidget()
            bl = QHBoxLayout(btn_row)
            bl.setContentsMargins(0, 0, 0, 0)
            bl.addStretch(1)
            close_btn = QPushButton("Cerrar")
            close_btn.setObjectName("relocate_skip_btn")
            close_btn.clicked.connect(self.reject)
            bl.addWidget(close_btn)
            layout.addWidget(btn_row)
            return

        # I-7: el informe señala que los backups pueden sumar hasta ~2.5GB
        # de Rekordbox sin que el usuario se entere nunca — mostrar el total
        # acá es el bonus de bajo costo pedido por el ticket.
        total_size = sum(b.size for b in backups)
        total_label = QLabel(
            f"{len(backups)} copia(s) · {_fmt_size(total_size)} ocupados en disco"
        )
        total_label.setObjectName("relocate_orig")
        total_label.setWordWrap(True)
        layout.addWidget(total_label)

        self._list = QListWidget()
        self._list.setObjectName("relocate_list")
        for b in backups:
            when = (
                b.timestamp.strftime("%d/%m/%Y %H:%M:%S")
                if b.timestamp is not None else b.path.name
            )
            item = QListWidgetItem(f"{when}\n{_fmt_size(b.size)}")
            item.setData(Qt.ItemDataRole.UserRole, b)
            self._list.addItem(item)
        self._list.setCurrentRow(0)
        self._list.itemDoubleClicked.connect(lambda _item: self._accept_selected())
        layout.addWidget(self._list, 1)

        btn_row = QWidget()
        bl = QHBoxLayout(btn_row)
        bl.setContentsMargins(0, 0, 0, 0)
        bl.setSpacing(8)

        cancel_btn = QPushButton("Cancelar")
        cancel_btn.setObjectName("relocate_skip_btn")
        cancel_btn.clicked.connect(self.reject)
        bl.addWidget(cancel_btn)
        bl.addStretch(1)

        restore_btn = QPushButton("Restaurar esta copia…")
        restore_btn.setObjectName("relocate_use_btn")
        restore_btn.clicked.connect(self._accept_selected)
        bl.addWidget(restore_btn)

        layout.addWidget(btn_row)

    def _accept_selected(self) -> None:
        item = self._list.currentItem()
        if item is not None:
            self.chosen_backup = item.data(Qt.ItemDataRole.UserRole)
        self.accept()

    def reject(self) -> None:  # type: ignore[override]
        self.chosen_backup = None
        super().reject()
