# Plan 02 — UX de playback (espaciadora · click-para-pausar · auto-avance)

## Objetivo
Tres mejoras de uso sobre la reproducción ya existente:
1. **Barra espaciadora** → play/pausa (sin romper la escritura en inputs).
2. **Click en la fila que ya está sonando** → pausa/reanuda (hoy reinicia).
3. **Auto-avance**: al terminar un track, suena el siguiente de la lista.

Leé `plans/README.md` primero. Hacé este plan **después** del 01 idealmente, pero
es independiente.

---

## Paso 1 — Extender `AudioPlayer` (`audio_player.py`)

Agregar señal de fin de track. En la lista de señales:
```python
track_finished: pyqtSignal = pyqtSignal()
```

En `__init__`, junto a las otras conexiones del `_player`:
```python
self._player.mediaStatusChanged.connect(self._on_media_status)
```

Slot interno (junto a `_on_state`):
```python
def _on_media_status(self, status: QMediaPlayer.MediaStatus) -> None:
    if status == QMediaPlayer.MediaStatus.EndOfMedia:
        self.track_finished.emit()
```

---

## Paso 2 — Refactor de `_play_track` + cola de reproducción (`ui.py`)

### 2a. Estado nuevo
En `__init__`, en el bloque `# ── Audio playback ──`, agregar:
```python
self._play_order: list[tuple[str, FileRow]] = []   # (raw_path, row) en orden
```
Y conectar el fin de track:
```python
self._audio.track_finished.connect(self._on_track_finished)
```

### 2b. Reemplazar `_play_track`
El método actual usa `self.sender()` para saber qué fila se clickeó. Lo separamos
en un slot fino + la lógica reusable. **Reemplazá** el `_play_track` actual por:

```python
def _play_track(self, raw_path: str) -> None:
    """Slot de FileRow.clicked. La fila emisora es self.sender()."""
    row = self.sender()
    self._play_file_row(row if isinstance(row, FileRow) else None, raw_path)

def _play_file_row(
    self,
    row: FileRow | None,
    raw_path: str,
    allow_toggle: bool = True,
) -> None:
    # Click en la fila que ya suena → pausa/reanuda en vez de reiniciar
    if allow_toggle and raw_path and raw_path == self._playing_path \
            and self._audio.current_path():
        self._audio.toggle()
        return

    if self._source == "traktor":
        resolved = raw_path if raw_path and Path(raw_path).exists() else None
    else:
        from rekordbox_export import resolve_path
        resolved = resolve_path(raw_path)
    if not resolved:
        return
    resolved = str(resolved)

    self._audio.play(resolved)
    self._playing_path = raw_path

    self._set_row_playing(self._playing_row, False)
    self._playing_row = None
    if isinstance(row, FileRow):
        self._set_row_playing(row, True)
        self._playing_row = row

    self._start_spectrogram(resolved)
```

### 2c. Auto-avance
Agregar el slot (cerca de `_on_playing_changed`):
```python
def _on_track_finished(self) -> None:
    """Reproduce el siguiente track existente de la cola, si lo hay."""
    if not self._play_order:
        return
    idx = next(
        (i for i, (rp, _) in enumerate(self._play_order)
         if rp == self._playing_path),
        -1,
    )
    if idx == -1 or idx + 1 >= len(self._play_order):
        return
    next_path, next_row = self._play_order[idx + 1]
    self._play_file_row(next_row, next_path, allow_toggle=False)
```

### 2d. Poblar y limpiar la cola
En `_clear_preview_layout`, donde ya se hace `self._playing_row = None`, agregar:
```python
self._play_order.clear()
```

En `_make_row_widget`, **antes del `return row`**, agregar (solo filas existentes):
```python
if track.exists and track.raw_path:
    self._play_order.append((track.raw_path, row))
```

> Nota: `_make_row_widget` ya construye `row = FileRow(...)`. La cola se arma en el
> mismo orden de render, que es el orden visual de la lista.

---

## Paso 3 — Barra espaciadora (`ui.py`)

### 3a. Imports
Agregar a los imports de `PyQt6.QtGui`:
```python
from PyQt6.QtGui import QKeySequence, QShortcut
```
(El archivo ya importa otras cosas de `QtGui`; sumá estas dos. `QAction` ya se
importa en una línea aparte — dejala como está.)

### 3b. Registrar el atajo
Al final de `__init__` (después de `self._load_playlists()`), agregar:
```python
self._space_shortcut = QShortcut(QKeySequence(Qt.Key.Key_Space), self)
self._space_shortcut.activated.connect(self._on_space)
```

### 3c. Handler con guarda de foco
Agregar el método (cerca de `_on_playing_changed`):
```python
def _on_space(self) -> None:
    # No robar la barra espaciadora cuando se está escribiendo o sobre un botón
    from PyQt6.QtWidgets import QAbstractButton
    fw = QApplication.focusWidget()
    if isinstance(fw, (QLineEdit, QPlainTextEdit, QAbstractButton)):
        return
    self._audio.toggle()
```
(`QApplication`, `QLineEdit`, `QPlainTextEdit` ya están importados en `ui.py`.)

---

## Verificación
1. `source .venv/bin/activate && python main.py`.
2. **Espaciadora**: con foco fuera de inputs, espaciadora pausa/reanuda. Escribiendo
   en el campo de carpeta, la espaciadora escribe un espacio (no pausa).
3. **Click-para-pausar**: click en la fila que suena → pausa; otro click → reanuda.
   Click en otra fila → cambia de track (no togglea).
4. **Auto-avance**: dejá terminar un track corto → arranca solo el siguiente de la
   lista. Al llegar al último, se detiene sin error.
5. Smoke headless:
   ```bash
   QT_QPA_PLATFORM=offscreen python -c "import ui, audio_player; print('OK')"
   ```

## Notas
- El auto-avance solo recorre las filas **existentes** del preview actual (las
  faltantes/rojas no entran a `_play_order`).
- Si el usuario re-renderiza el preview mientras suena, `_play_order` se reconstruye;
  el match es por `raw_path`, así que el avance sigue funcionando si la lista que
  suena sigue visible. Si dejó de estar visible, el auto-avance simplemente no
  encuentra el índice y se detiene (comportamiento aceptable).
- No uses `unpolish/polish`. No bloquees el hilo principal.
