from __future__ import annotations

from pathlib import Path
from typing import ClassVar, List

from PyQt6.QtCore import QPoint, QRectF, Qt, pyqtSignal
from PyQt6.QtGui import (
    QColor,
    QFontMetrics,
    QMouseEvent,
    QPainter,
    QPainterPath,
    QPalette,
    QPixmap,
)
from PyQt6.QtWidgets import (
    QDialog,
    QGraphicsOpacityEffect,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QSizePolicy,
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

    clicked: pyqtSignal = pyqtSignal()

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self._draw_pause_bars = False

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit()
        super().mousePressEvent(event)

    def set_pause_icon(self, active: bool) -> None:
        """
        T-015: el glyph Unicode de pausa (⏸, U+23F8) no existe en la fuente
        base de UI de Windows — el fallback de fuente cae a Segoe UI Emoji,
        que pinta el ícono con sus propios colores (celeste), ignorando el
        `color: @{on_accent}` del QSS. Ni siquiera el variation selector
        U+FE0E (fuerza presentación de texto) lo evita en Qt. Con `active`
        se dibuja la pausa a mano en paintEvent, con el color de paleta que
        el QSS ya resolvió para este QLabel — sin fuente de por medio, así
        que no puede volver a pintarse "a color" en ninguna plataforma.
        """
        self._draw_pause_bars = active
        if active:
            self.setText("")
        self.update()

    def paintEvent(self, event) -> None:
        if not self._draw_pause_bars:
            super().paintEvent(event)
            return
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        color = self.palette().color(QPalette.ColorRole.WindowText)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(color)
        w, h = self.width(), self.height()
        bar_w = max(3, round(w * 0.13))
        bar_h = round(h * 0.36)
        gap = max(3, round(w * 0.11))
        total_w = bar_w * 2 + gap
        x0 = (w - total_w) // 2
        y0 = (h - bar_h) // 2
        radius = bar_w * 0.35
        painter.drawRoundedRect(x0, y0, bar_w, bar_h, radius, radius)
        painter.drawRoundedRect(x0 + bar_w + gap, y0, bar_w, bar_h, radius, radius)


# ──────────────────────────── Rack-head con espectrograma de fondo ────────

class RackHead(QWidget):
    """
    Banner del rack con un espectrograma tenue pintado detrás del contenido.
    super().paintEvent() dibuja el fondo del QSS; encima va el pixmap clippeado
    al borde redondeado. Los hijos (nota, brand, VU) pintan después, arriba.
    """

    _RADIUS = 12.0

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._spectro: QPixmap | None = None

    def set_spectrogram(self, pixmap: QPixmap | None) -> None:
        self._spectro = pixmap
        self.update()

    def paintEvent(self, event) -> None:
        super().paintEvent(event)               # fondo + borde del QSS
        if self._spectro is None:
            return
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        path = QPainterPath()
        rect = QRectF(self.rect()).adjusted(1.5, 1.5, -1.5, -1.5)
        path.addRoundedRect(rect, self._RADIUS, self._RADIUS)
        p.setClipPath(path)
        scaled = self._spectro.scaled(
            self.size(),
            Qt.AspectRatioMode.IgnoreAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
        p.drawPixmap(0, 0, scaled)


# ──────────────────────────────────────── File row (clickable) ───────────

class FileRow(QWidget):
    """
    Fila de archivo en el preview. Si el archivo existe, es clickeable y emite
    `clicked(raw_path)` para reproducir. Los faltantes quedan inertes.
    set_playing() usa setStyleSheet inline (no unpolish/polish) para evitar el
    flicker en cascada documentado en este archivo.
    """

    clicked: pyqtSignal = pyqtSignal(str)

    def __init__(
        self,
        raw_path: str,
        exists: bool,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._raw_path = raw_path
        self._exists = exists
        self.setObjectName("output_file_row")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setProperty("file_missing", "false" if exists else "true")
        if exists:
            self.setCursor(Qt.CursorShape.PointingHandCursor)

    def mousePressEvent(self, event) -> None:
        if self._exists and event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit(self._raw_path)
        super().mousePressEvent(event)

    def set_playing(self, playing: bool) -> None:
        if playing:
            theme = PlaylistCard._theme
            accent = "#ce7de6" if theme == "dark" else "#8c38bf"
            soft = (
                "rgba(206,125,230,28)" if theme == "dark"
                else "rgba(140,56,191,22)"
            )
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

    seek_requested: pyqtSignal = pyqtSignal(int)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._pos = 0
        self._dur = 0
        self._accent = QColor(206, 125, 230)
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
        # T-015: densidad — reducido de (12,9,13,9)/spacing 12 para que entren
        # más playlists sin scroll en la mayoría de los casos (con ~35 igual
        # puede hacer falta scrollear, ver nota en el handoff de T-015).
        layout.setContentsMargins(11, 6, 12, 6)
        layout.setSpacing(10)

        # Large mono order number
        self._order_label = QLabel(str(index + 1).zfill(2))
        self._order_label.setObjectName("card_order")
        self._order_label.setFixedWidth(30)
        self._order_label.setAlignment(
            Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
        )
        layout.addWidget(self._order_label)

        # Name + meta tag
        info = QWidget()
        info.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        info_layout = QVBoxLayout(info)
        info_layout.setContentsMargins(0, 0, 0, 0)
        info_layout.setSpacing(2)

        # Nombre completo guardado aparte: el label muestra una versión
        # recortada con "…" según el ancho real disponible (recalculada en
        # resizeEvent), para que un nombre largo nunca fuerce el contenedor
        # a ser más ancho que la columna — sin esto, el QScrollArea de la
        # lista queda desplazable horizontalmente (sin barra visible, porque
        # el policy la oculta, pero el desplazamiento sigue existiendo).
        self._full_name = str(playlist.Name)
        self._name_label = QLabel(self._full_name)
        self._name_label.setObjectName("card_name")
        self._name_label.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        self._name_label.setToolTip(self._full_name)
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
        self._check.setFixedSize(19, 19)
        layout.addWidget(self._check)

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


# ──────────────────────────── Modal de desambiguación (relocate) ─────────

def _fmt_size(num_bytes: int) -> str:
    size = float(num_bytes)
    for unit in ("B", "KB", "MB", "GB"):
        if size < 1024 or unit == "GB":
            return f"{size:.1f} {unit}" if unit != "B" else f"{int(size)} {unit}"
        size /= 1024
    return f"{size:.1f} GB"


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
        for cand in request.candidates:
            hint_parts = []
            if cand.matched_artist or cand.matched_title:
                hint_parts.append(
                    " - ".join(p for p in (cand.matched_artist, cand.matched_title) if p)
                )
            hint = f"  ·  {hint_parts[0]}" if hint_parts else ""
            item = QListWidgetItem(
                f"{cand.path}\n{_fmt_size(cand.size)}  ·  score {cand.score:.2f}{hint}"
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
        target_name: str,  # "collection.nml" | "master.db"
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
