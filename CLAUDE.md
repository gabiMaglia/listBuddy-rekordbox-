# CLAUDE.md — listBuddy

## Rol esperado

Sos un experto en Python, empaquetado de apps de escritorio para macOS/Windows, y en el funcionamiento interno de Rekordbox y Traktor (todas sus versiones). Conocés la estructura de sus bases de datos, el esquema de sus tablas, cómo pyrekordbox y el NML de Traktor funcionan, y los problemas habituales de integración.

---

## El proyecto

**listBuddy** es una app de escritorio (PyQt6) que lee la librería de Rekordbox 6 o Traktor Pro 3/4 y copia las canciones de las playlists seleccionadas a carpetas organizadas con prefijo numérico de orden. También permite previsualizar y reproducir audio directamente desde la interfaz.

### Flujo de usuario

1. La app abre la DB de Rekordbox 6 al iniciar (requiere que RB esté cerrado).
2. Muestra un árbol de carpetas y playlists con checkboxes tri-estado.
3. El usuario elige carpeta de destino, marca playlists, y exporta.
4. Un `QThread` copia los archivos con nombre `001 - Artist - Title.mp3`, mostrando progreso y log.

---

## Arquitectura

```
main.py              → entry point. Solo QApplication + MainWindow.show().
ui.py                → MainWindow (PyQt6). Árbol de playlists, preview, reproducción, exportación.
worker.py            → ExportWorker (QThread). Copia archivos; emite signals log/progress/finished_ok.
db.py                → Capa de acceso a pyrekordbox. open_database(), list_playlists(), get_playlist_tree().
rekordbox_export.py  → Lógica base validada. NO modificar sin causa mayor.
traktor_db.py        → Parser de colección NML de Traktor Pro 3/4. open_collection(), get_playlist_tree().
preview_worker.py    → PreviewWorker (QThread). Existence checks en background; emite GroupData.
audio_player.py      → AudioPlayer (QMediaPlayer+FFmpeg). play/pause/seek; señales playing_changed, position_changed, track_finished.
spectro_worker.py    → SpectrogramWorker (QThread). QAudioDecoder + numpy STFT → QImage tenue de fondo.
ui_components.py     → PlaylistCard, PlaylistGroup, SeekBar, FileRow, RackHead, ClickableLabel.
styles.py            → Tokens de diseño dark/light + load_qss().
rb_exporter.spec     → Spec de PyInstaller para empaquetar (produce "listBuddy" ejecutable).
requirements.txt     → Dependencias pineadas exactas.
plans/               → Planes de implementación autocontenidos para ejecutar con Sonnet.
```

**Regla de imports:** `main → ui → worker/db → rekordbox_export`. Nunca al revés.

### Funciones clave de `rekordbox_export.py` (no duplicar, solo envolver)

| Función | Qué hace |
|---|---|
| `get_all_playlists(db)` | Lista plana de playlists (Attribute==0, ignora carpetas) |
| `get_songs(playlist)` | Songs de una playlist; prueba `Songs`, `songs`, `items` |
| `get_content(song)` | DjmdContent del song; prueba `Content` y `content` |
| `get_artist(content)` | Artista; prueba `ArtistName`, `Artist`, `artist_name`, `artist` |
| `resolve_path(raw_path)` | Normaliza rutas `/C/Users/...` → `C:/Users/...` y verifica existencia |
| `sanitize(name)` | Elimina chars inválidos para nombres de archivo (`\/:*?"<>|`) |

---

## Entorno de desarrollo

```
Python       3.14.3  (CPython)
PyQt6        6.11.0
PyQt6-Qt6    6.11.1
PyQt6_sip    13.11.1
pyrekordbox  0.4.4
sqlcipher3-wheels 0.5.7
numpy        2.4.6
```

Entorno virtual en `.venv/`. Activar antes de correr:

```bash
source .venv/bin/activate        # macOS/Linux
.\.venv\Scripts\activate         # Windows
python main.py                   # arrancar la app
```

---

## Rekordbox — conocimiento experto

### Versiones y bases de datos

| Versión RB | Formato DB | Biblioteca Python |
|---|---|---|
| 5.x | XML (`rekordbox.xml`) + colección propia | `pyrekordbox` (modo XML) |
| 6.x | SQLite cifrado con SQLCipher | `pyrekordbox.Rekordbox6Database` |
| 6.7+ | Misma DB, cambia la clave de cifrado con cada update | requiere `python -m pyrekordbox download-key` |

> Este proyecto solo soporta **Rekordbox 6**. La DB es un archivo SQLite cifrado con SQLCipher 4. La clave se descarga una vez con `python -m pyrekordbox download-key` y queda guardada localmente.

### Ubicación de la base de datos de Rekordbox 6

| OS | Ruta |
|---|---|
| Windows | `%APPDATA%\Pioneer\rekordbox\master.db` |
| macOS | `~/Library/Pioneer/rekordbox/master.db` |

`pyrekordbox.Rekordbox6Database()` la encuentra automáticamente si la instalación de RB es estándar. Si falla, se puede pasar la ruta explícitamente.

**La DB queda bloqueada mientras Rekordbox está abierto.** Siempre pedir al usuario que cierre RB antes de usar la app.

### Esquema de tablas relevantes (pyrekordbox 0.4.x)

#### `DjmdPlaylist` — playlists y carpetas

| Campo | Tipo | Notas |
|---|---|---|
| `ID` | str | Identificador único |
| `ParentID` | str | `"root"` si es nodo raíz; ID de la carpeta padre si está anidado |
| `Attribute` | int | `0` = playlist, `1` = carpeta |
| `Name` | str | Nombre visible en RB |
| `Seq` | int | Orden de visualización dentro del nivel |
| `is_playlist` | bool | Propiedad de conveniencia: `Attribute == 0` |
| `is_folder` | bool | Propiedad de conveniencia: `Attribute == 1` |

Para obtener todas las entradas: `db.get_playlist()` devuelve un iterable de `DjmdPlaylist`.

Las canciones de una playlist están en la relación `Songs` (o `songs` o `items` según versión de pyrekordbox — siempre usar `get_songs()` del proyecto en lugar de acceder directo).

#### `DjmdContent` — pistas

| Campo | Tipo | Notas |
|---|---|---|
| `ID` | str | |
| `Title` | str | Título de la pista |
| `ArtistName` | str | Nombre del artista (puede ser `None`) |
| `FolderPath` | str | Ruta al archivo en disco (puede ser `/C/Users/...` o `C:\Users\...`) |
| `TrackNo` | int | Orden dentro de la playlist (puede ser `None` o duplicado) |
| `BeatCount` | int | BPM×10 |
| `ColorID` | int | Color de la pista en RB |

Acceso: `get_content(song)` prueba los atributos `Content` y `content` para compatibilidad cross-versión.

#### Normalización de rutas (`FolderPath`)

Rekordbox en Windows guarda las rutas con separador Unix al inicio: `/C/Users/usuario/Music/track.mp3`. La función `resolve_path()` ya convierte esto a `C:/Users/usuario/Music/track.mp3`. En macOS las rutas son `/Users/usuario/Music/track.mp3` y pasan sin tocar.

### pyrekordbox 0.4.4 — notas de integración

- `Rekordbox6Database()` → abre la DB, descifra con la clave local. Lanza excepción si falla.
- `db.get_playlist()` → genera `DjmdPlaylist` uno a uno.
- `db.get_content()` → genera `DjmdContent` uno a uno.
- Las relaciones SQLAlchemy (como `playlist.Songs`) se cargan lazy. Si se itera fuera del contexto de sesión puede fallar — `get_songs()` del proyecto maneja esto.
- **No asumir nombres de campo** de pyrekordbox. Si surge una versión nueva, verificar con `dir(objeto)` antes de codear.

---

## Empaquetado — macOS

### PyInstaller en macOS (prioridad actual)

```bash
pip install pyinstaller
pyinstaller rb_exporter.spec
# El bundle queda en dist/RB Exporter.app
```

El `.spec` ya está configurado. Para macOS el resultado es un `.app` bundle. **No se puede cross-compilar:** el `.app` solo se puede generar desde una Mac, y el `.exe` de Windows solo desde Windows.

#### Checklist para que el .app funcione correctamente

1. **SQLCipher:** `sqlcipher3-wheels` incluye el `.dylib`. El spec ya hace `collect_dynamic_libs('sqlcipher3')`. Si el .app abre pero falla al leer la DB, verificar que `libsqlcipher.dylib` esté en `dist/RB Exporter.app/Contents/Frameworks/`.

2. **Hidden imports de pyrekordbox:** el spec ya declara:
   ```python
   hiddenimports=[
       'pyrekordbox', 'pyrekordbox.db6', 'pyrekordbox.db6.tables',
       'pyrekordbox.db6.registry', 'sqlcipher3',
       'sqlalchemy', 'sqlalchemy.dialects.sqlite', 'sqlalchemy.orm',
   ]
   ```
   Si aparece `ModuleNotFoundError` en runtime, agregar el módulo faltante aquí.

3. **Clave de desencriptado en el bundle:** pyrekordbox guarda la clave en `~/.pyrekordbox/` (o similar). En una app empaquetada, la ruta puede no existir. Verificar dónde busca la clave en runtime y si es necesario incluir un runtime hook que la precargue.

4. **Ícono:** crear `icon.icns` (macOS). Descomentar `icon='icon.icns'` en el spec antes de buildear.

5. **Firma de código (Code Signing):** sin firma, macOS Gatekeeper bloquea el .app. Para distribuir:
   - **Sin firma** (solo para el propio usuario): click derecho → Abrir → Confirmar en el diálogo.
   - **Con firma ad-hoc** (para distribuir a conocidos sin Developer ID):
     ```bash
     codesign --force --deep --sign - "dist/RB Exporter.app"
     ```
   - **Con Developer ID** (distribución pública sin Mac App Store):
     ```bash
     codesign --force --deep --options runtime \
       --sign "Developer ID Application: Tu Nombre (TEAMID)" \
       "dist/RB Exporter.app"
     xcrun notarytool submit "dist/RB Exporter.zip" --apple-id ... --password ... --team-id ...
     xcrun stapler staple "dist/RB Exporter.app"
     ```

6. **Arquitectura:** por defecto PyInstaller empaqueta para la arquitectura del sistema donde se corre. Para crear un **Universal Binary** (arm64 + x86_64):
   ```bash
   pyinstaller rb_exporter.spec --target-arch universal2
   ```
   Requiere que todas las dependencias nativas (SQLCipher .dylib) también sean universal. `sqlcipher3-wheels` puede no tener universal en todas sus versiones — verificar antes de intentarlo.

8. **Audio (QtMultimedia + FFmpeg):** el spec declara `PyQt6.QtMultimedia` y `numpy`
   en `hiddenimports`. **PyInstaller 6.x recoge automáticamente** los plugins
   multimedia (`libffmpegmediaplugin.dylib`, `libdarwinmediaplugin.dylib`,
   `QtMultimedia.framework`, `libavcodec/format/util`) — no hace falta colectar
   manualmente. Verificar en runtime que aparezca:
   `qt.multimedia.ffmpeg: Using Qt multimedia with FFmpeg version ...`
   Si el audio no suena en el bundle, incluir manualmente con:
   ```python
   collect_dynamic_libs('PyQt6', subdir='Qt6/plugins/multimedia')
   collect_dynamic_libs('PyQt6', subdir='Qt6/lib')  # libav*
   ```

7. **Entitlements** (si se firma con hardened runtime):
   ```xml
   <!-- entitlements.plist -->
   <?xml version="1.0" encoding="UTF-8"?>
   <!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" ...>
   <plist version="1.0"><dict>
     <key>com.apple.security.cs.allow-unsigned-executable-memory</key><true/>
   </dict></plist>
   ```
   PyInstaller+PyQt6 puede requerir `cs.allow-unsigned-executable-memory`. Pasar con `--entitlements entitlements.plist` en codesign.

### Alternativas a PyInstaller en macOS

| Herramienta | Ventaja | Desventaja |
|---|---|---|
| **PyInstaller** (actual) | Universal, maduro, el spec ya está | A veces necesita ajuste de hidden imports |
| **py2app** | Nativo macOS, .app más limpio | Solo macOS, menos activo |
| **Briefcase (BeeWare)** | Multi-plataforma, genera instaladores | Curva de configuración mayor |
| **Nuitka** | Compila a C, binario más pequeño y rápido | Compilación lenta, requiere compilador C |

Para este proyecto, **seguir con PyInstaller** salvo que surja un problema grave.

---

## Empaquetado — Windows

```bash
pyinstaller rb_exporter.spec
# El ejecutable queda en dist/RB Exporter.exe
```

- `icon.ico` para el ícono (descomentar línea en spec).
- UPX está habilitado (`upx=True`) para reducir tamaño. Si da problemas de antivirus, deshabilitar.
- Si el .exe abre pero falla al leer la DB: agregar hidden imports de SQLCipher en el spec.

---

## Convenciones del proyecto

- **Idioma de la UI:** español rioplatense (`Elegí`, `Marcá`, `Hacé click`). No cambiar a español neutro ni inglés.
- **Type hints en todo.** Funciones y métodos tipados con `from __future__ import annotations`.
- **Sin estado global.** Dependencias explícitas por parámetro.
- **No reescribir** `rekordbox_export.py` sin causa mayor. Es la lógica base validada; las otras capas la envuelven.
- **Rekordbox debe estar cerrado** al testear (la DB queda bloqueada si está abierto).
- **Ante cualquier ambigüedad sobre campos de pyrekordbox o estructura de DB:** preguntar antes de asumir. Los nombres de campo pueden variar entre versiones de pyrekordbox.

---

## Reglas de trabajo (para Claude)

- Antes de modificar `rekordbox_export.py`, verificar que el cambio no rompa las funciones que `db.py` y `worker.py` consumen.
- Si se agregan campos nuevos de `DjmdContent` o `DjmdPlaylist`, siempre usar `getattr(obj, 'campo', None)` con fallback defensivo.
- Si algo del spec de PyInstaller no se entiende, verificar la documentación de PyInstaller antes de modificar flags al azar.
- Los errores de apertura de DB deben siempre mostrar un mensaje claro al usuario vía `QMessageBox`, nunca stacktrace crudo.
- `ExportWorker` corre en un `QThread` — nunca actualizar widgets de Qt directamente desde `run()`, siempre via signals.
- El conteo de progreso usa `total_songs` acumulado antes del loop; no recalcular mid-flight.
