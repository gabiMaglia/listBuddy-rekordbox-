<div align="center">

<img src="icon_preview.png" width="120" alt="listBuddy">

# listBuddy

**Exportá y previsualizá las playlists de tu librería de DJ.**
Lee Rekordbox 6 y Traktor Pro 3/4, y copia las pistas a carpetas numeradas en orden.

[![License: GPL v3](https://img.shields.io/badge/License-GPLv3-blue.svg)](https://www.gnu.org/licenses/gpl-3.0)
[![Ko-fi](https://img.shields.io/badge/Ko--fi-Donar-FF5E5B?logo=ko-fi&logoColor=white)](https://ko-fi.com/gabrielmaglia)

</div>

---

## Qué hace

listBuddy abre tu librería de **Rekordbox 6** o **Traktor Pro 3/4**, te muestra el árbol
de carpetas y playlists, y copia las pistas que elijas a carpetas organizadas con un
prefijo numérico de orden:

```
<destino>/<nombre de playlist>/
    001 - Artist - Title.mp3
    002 - Artist - Title.aiff
    003 - Artist - Title.flac
    ...
```

Además podés **escuchar las pistas antes de exportar**, sin salir de la app.

## Características

- 🎛 **Dos fuentes** — Rekordbox 6 y Traktor Pro 3/4, con un switch para cambiar entre ellas.
- 🔢 **Exportación numerada** — cada playlist va a su carpeta, con prefijo de orden y nombre `Artista - Título`.
- 🔊 **Reproductor integrado** — clickeá cualquier pista para escucharla. Soporta mp3, wav, aiff, mp4/m4a, **flac** y wma (backend FFmpeg de Qt).
- 📊 **Espectrograma de fondo** — se dibuja tenue detrás del banner mientras suena la pista (calculado en background, nunca bloquea).
- ⏯ **Controles** — play/pausa desde la nota ♪ o con la **barra espaciadora**, barra de progreso con seek, y auto-avance al siguiente track.
- ⚠️ **Detección de archivos faltantes** — las pistas cuyo archivo no está en disco se marcan en rojo y no se pueden reproducir.
- ⚙️ **Configuración** — selector de dispositivo de salida de audio, toggles de auto-avance y espectrograma, y override de la ruta de la librería.
- 🌗 **Tema claro / oscuro** estilo macOS.
- ⚡ **Sin congelamientos** — las operaciones pesadas (existencia de archivos, decodificación, copia) corren en hilos separados.

## Requisitos

- **Python 3.11+**
- **Rekordbox 6** y/o **Traktor Pro 3/4** instalados, con su librería configurada.
- El programa correspondiente debe estar **cerrado** al usar listBuddy (la librería queda bloqueada si está abierto).

## Instalación desde fuente

```bash
git clone https://github.com/gabiMaglia/listBuddy-rekordbox-.git
cd listBuddy-rekordbox-
python -m venv .venv
source .venv/bin/activate          # Windows: .\.venv\Scripts\activate
pip install -r requirements.txt
```

### Primera vez con Rekordbox: bajar la clave de desencriptado

Rekordbox 6 cifra su base de datos con SQLCipher. Antes de la primera ejecución, corré
una vez:

```bash
python -m pyrekordbox download-key
```

Esto descarga la clave y la guarda localmente. *(Traktor usa un XML sin cifrar, así que
no necesita este paso.)*

## Ejecutar

```bash
python main.py
```

## Uso

1. Elegí la **fuente** (Rekordbox o Traktor) con el switch de la izquierda.
2. Elegí la **carpeta de destino** donde se van a crear las subcarpetas.
3. Marcá las **playlists** que querés exportar (o usá **Todas** / **Ninguna**).
4. Revisá la **vista previa** a la derecha: ahí ves cómo van a quedar numeradas las
   pistas, y cuáles faltan (en rojo).
5. Hacé click en **Exportar en orden**.

Las pistas ya existentes en el destino se saltan, así que podés re-exportar sin duplicar.

### Reproducir

- Clickeá cualquier pista del panel de vista previa para escucharla.
- La nota **♪** del banner alterna play/pausa (también con la **barra espaciadora**).
- La **barra de progreso** debajo del banner permite saltar a cualquier punto.
- Al terminar una pista, suena la siguiente de la lista (configurable).

### Configuración (⚙ en el header)

- **Dispositivo de salida de audio** — elegí por qué salida suena la previsualización.
- **Auto-avance** y **espectrograma** — toggles on/off.
- **Librerías** — si tu `master.db` (Rekordbox) o `collection.nml` (Traktor) están en una
  ubicación no estándar (disco externo, varias versiones), configurá la ruta acá. El botón
  **Auto** vuelve a la autodetección.

## Empaquetar a ejecutable

```bash
pip install pyinstaller
pyinstaller rb_exporter.spec
```

El resultado queda en `dist/`. El `.spec` ya incluye el ícono, los hidden imports de
pyrekordbox/SQLCipher y el motor de audio (QtMultimedia + FFmpeg, que PyInstaller recoge
automáticamente).

> **No se puede cross-compilar:** el ejecutable de macOS solo se genera desde una Mac, y el
> de Windows solo desde Windows. Para distribuir en macOS hace falta firmar el binario
> (ver la sección de empaquetado en [CLAUDE.md](CLAUDE.md)).

Para regenerar el ícono:

```bash
python scripts/make_icon.py
```

## Logs

Si algo falla, listBuddy escribe un log rotativo que podés adjuntar para diagnosticar:

| OS | Ruta |
|---|---|
| macOS | `~/Library/Logs/listBuddy/listBuddy.log` |
| Windows | `%LOCALAPPDATA%\listBuddy\logs\listBuddy.log` |
| Linux | `~/.local/state/listBuddy/listBuddy.log` |

## Estructura del proyecto

```
main.py              # entry point + logging/excepthook
ui.py                # MainWindow (PyQt6): layout, reproducción, exportación, settings
ui_components.py     # widgets custom (cards, seek bar, file rows, rack head)
worker.py            # ExportWorker (QThread): copia y numera los archivos
preview_worker.py    # PreviewWorker (QThread): chequeo de existencia en background
audio_player.py      # AudioPlayer (QMediaPlayer + FFmpeg)
spectro_worker.py    # SpectrogramWorker (QThread): decodifica + STFT con numpy
db.py                # acceso a la librería de Rekordbox (pyrekordbox)
traktor_db.py        # parser de la colección NML de Traktor
rekordbox_export.py  # lógica base validada (acceso a DB + copia)
app_logging.py       # logging a archivo + manejo global de excepciones
styles.py + qss/     # design system (tokens + hojas QSS dark/light)
rb_exporter.spec     # spec de PyInstaller
scripts/make_icon.py # generador del ícono
```

## Tecnología

Python · PyQt6 · pyrekordbox · sqlcipher3 · numpy · PyInstaller

## Donaciones

listBuddy es gratuito y de código abierto. Si te sirvió, podés invitarme un café:

**[ko-fi.com/gabrielmaglia](https://ko-fi.com/gabrielmaglia)** — o escaneá el QR desde
el menú **Ayuda → Donar en Ko-fi…** dentro de la app.

## Licencia

GNU General Public License v3.0 — ver [LICENSE](LICENSE).

En resumen: podés usar, modificar y redistribuir este software libremente, siempre que
cualquier versión redistribuida también sea de código abierto bajo GPL v3.

---

<sub>Rekordbox es una marca de AlphaTheta / Pioneer DJ. Traktor es una marca de Native
Instruments. listBuddy es un proyecto independiente, sin afiliación ni respaldo de esas
empresas; lee sus librerías localmente para tu propio uso.</sub>
