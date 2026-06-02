# Planes de implementación — List Buddy

Estos planes están pensados para **ejecutarse con Claude Sonnet** (más barato que
Opus). El diseño/arquitectura ya está resuelto acá; Sonnet solo ejecuta los pasos.

## Por qué esto ahorra tokens
- **Opus diseña, Sonnet ejecuta.** Sonnet cobra ~5× menos por token. Para trabajo
  mecánico (editar archivos siguiendo un plan exacto) rinde igual de bien.
- **El ahorro real depende de que el plan sea autocontenido.** Sonnet arranca sin
  el contexto de la conversación de diseño. Si tiene que explorar el código para
  entender qué hacer, gasta los tokens que querías ahorrar. Por eso cada plan trae
  rutas exactas, snippets del código actual y los pasos de verificación.

## Cómo correr un plan con Sonnet
1. Abrí una sesión nueva de Claude Code en este repo.
2. Cambiá el modelo a Sonnet: `/model sonnet`.
3. Pegá: `Implementá el plan en plans/01-seekbar.md al pie de la letra. No cambies
   nada fuera de lo que el plan indica. Al final, corré la verificación del plan.`
4. Revisá el diff antes de commitear.

## Orden sugerido
1. `01-seekbar.md` — barra de progreso + seek (lo más visible).
2. `02-playback-ux.md` — barra espaciadora, click-para-pausar, auto-avance.
3. `03-packaging-audio.md` — meter el motor de audio en el `.app` (para distribuir).

## Convenciones del proyecto (válidas para todos los planes)
- **UI en español rioplatense** (`Elegí`, `Marcá`). No neutro ni inglés.
- **Type hints en todo** con `from __future__ import annotations`.
- **Nada bloquea la UI.** El trabajo pesado va a QThread; los slots de Qt son
  livianos.
- **Una excepción no capturada en un slot de Qt aborta toda la app.** Cualquier
  acceso a un widget que puede haber sido borrado (`deleteLater`) va con guarda
  `try/except RuntimeError`. Ver `MainWindow._set_row_playing` en `ui.py` como
  patrón de referencia.
- **Estilos:** OFF-state en `qss/dark.qss` y `qss/light.qss` con tokens `@{...}`;
  estados dinámicos vía `setStyleSheet()` inline (NO `unpolish/polish`, que causa
  flicker en cascada).

## Estado actual del motor de audio (`audio_player.py`)
`AudioPlayer(QObject)` ya existe y envuelve `QMediaPlayer` + `QAudioOutput`:
- Señales: `playing_changed(bool)`, `track_changed(str)`, `error(str)`.
- Métodos: `play(path)`, `toggle()`, `stop()`, `set_volume(float)`,
  `current_path() -> str`, `is_playing() -> bool`.
- Atributos internos: `self._player` (QMediaPlayer), `self._output`, `self._current`.

Cada plan que necesite extender este motor describe exactamente qué señales/métodos
agregar.
