# Plan 01 — Barra de progreso + seek

## Objetivo
Mostrar una barra de progreso del track que suena, debajo del rack-head (el banner
de la columna izquierda). Permitir hacer click/arrastrar para saltar a un punto
(seek). Mostrar tiempo transcurrido / total. Se oculta cuando no hay nada cargado.

Leé `plans/README.md` primero (convenciones y estado de `audio_player.py`).

---

## Paso 1 — Extender `AudioPlayer` (`audio_player.py`)

`AudioPlayer` ya existe. Agregar posición/duración y seek.

En la lista de señales, agregar:
```python
position_changed: pyqtSignal = pyqtSignal(int, int)   # (pos_ms, dur_ms)
```

En `__init__`, después de conectar `playbackStateChanged` y `errorOccurred`,
agregar:
```python
self._player.positionChanged.connect(self._on_position)
self._player.durationChanged.connect(self._on_duration)
```

Agregar métodos públicos (junto a `stop`/`set_volume`):
```python
def seek(self, ms: int) -> None:
    self._player.setPosition(int(ms))

def duration(self) -> int:
    return self._player.duration()
```

Agregar slots internos (junto a `_on_state`/`_on_error`):
```python
def _on_position(self, pos: int) -> None:
    self.position_changed.emit(pos, self._player.duration())

def _on_duration(self, dur: int) -> None:
    self.position_changed.emit(self._player.position(), dur)
```

---

## Paso 2 — Widget `SeekBar` (`ui_components.py`)

Agregar al final de `ui_components.py`. Custom-painted para respetar el design
system (igual criterio que `VuBars` en `ui.py`). Imports necesarios ya presentes
en el archivo: `Qt`, `pyqtSignal`, `QPainter`, `QWidget`. Agregar `QColor` al import
de `PyQt6.QtGui` (la línea actual es `from PyQt6.QtGui import QPainter, QPainterPath,
QPixmap`).

```python
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
```

---

## Paso 3 — Integrar en `MainWindow` (`ui.py`)

### 3a. Import
Agregar `SeekBar` al import de `ui_components`:
```python
from ui_components import (
    ClickableLabel,
    FileRow,
    PlaylistCard,
    PlaylistGroup,
    RackHead,
    SeekBar,
)
```

### 3b. Builder de la barra
Agregar este método a `MainWindow` (cerca de `_build_rack_head`):
```python
def _build_seek_row(self) -> QWidget:
    row = QWidget()
    row.setObjectName("seek_row")
    row.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
    lo = QHBoxLayout(row)
    lo.setContentsMargins(2, 0, 2, 0)
    lo.setSpacing(8)

    self._time_cur = QLabel("0:00")
    self._time_cur.setObjectName("seek_time")
    lo.addWidget(self._time_cur)

    self._seek_bar = SeekBar()
    self._seek_bar.seek_requested.connect(self._audio.seek)
    lo.addWidget(self._seek_bar, 1)

    self._time_total = QLabel("0:00")
    self._time_total.setObjectName("seek_time")
    lo.addWidget(self._time_total)

    row.setVisible(False)          # oculto hasta que cargue un track
    self._seek_row = row
    return row
```

### 3c. Colocarlo en la columna izquierda
En `_build_left_col`, justo después de `lo.addWidget(self._build_rack_head())`,
agregar:
```python
lo.addWidget(self._build_seek_row())
```

### 3d. Conexiones en `__init__`
En el bloque `# ── Audio playback ──` de `__init__`, después de conectar
`error`, agregar:
```python
self._audio.position_changed.connect(self._on_position_changed)
self._audio.track_changed.connect(lambda _p: self._seek_row.setVisible(True))
```

### 3e. Slot de posición + helper de formato
Agregar a `MainWindow` (cerca de `_on_playing_changed`):
```python
@staticmethod
def _fmt_ms(ms: int) -> str:
    s = max(0, ms // 1000)
    return f"{s // 60}:{s % 60:02d}"

def _on_position_changed(self, pos: int, dur: int) -> None:
    self._seek_bar.set_progress(pos, dur)
    self._time_cur.setText(self._fmt_ms(pos))
    self._time_total.setText(self._fmt_ms(dur))
```

### 3f. Theming
En `_apply_theme`, donde se hace `self._vu_bars.set_accent(...)`, agregar al lado:
```python
self._seek_bar.set_accent("#ce7de6" if theme == "dark" else "#8c38bf")
```
Y en `__init__`, donde se hace `self._vu_bars.set_accent(...)` (al final del init),
agregar la misma línea para el estado inicial.

---

## Paso 4 — QSS (mínimo)
En `qss/dark.qss` y `qss/light.qss`, agregar la etiqueta de tiempo:
```css
QLabel#seek_time { font-family: "SF Mono","Menlo",monospace; font-size: 10px; color: @{faint}; background: transparent; }
```

---

## Verificación
1. `source .venv/bin/activate && python main.py` (Rekordbox/Traktor cerrado).
2. Seleccioná una playlist, clickeá un track → debe sonar y aparecer la barra
   bajo el banner, avanzando, con los tiempos `0:0X / M:SS`.
3. Click en otro punto de la barra → el audio salta a ahí.
4. Arrastrar sobre la barra → seek continuo.
5. Cambiar de track → la barra se reinicia y sigue el nuevo.
6. Toggle de tema → el accent de la barra cambia.
7. Smoke headless (no debe tirar excepción de import):
   ```bash
   QT_QPA_PLATFORM=offscreen python -c "import ui, ui_components, audio_player; print('OK')"
   ```

## Notas
- No toques la lógica de `_play_track` ni del espectrograma.
- `position_changed` puede emitir con `dur=0` al inicio (antes de que QMediaPlayer
  resuelva la duración); `set_progress` y `_fmt_ms` ya lo toleran.
