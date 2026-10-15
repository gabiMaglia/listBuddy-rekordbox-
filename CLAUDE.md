# CLAUDE.md — listBuddy

## Rol esperado

Sos un experto en Python, empaquetado de apps de escritorio para macOS/Windows, y en el funcionamiento interno de Rekordbox y Traktor (todas sus versiones). Conocés la estructura de sus librerías, cómo el XML exportado de Rekordbox y el NML de Traktor funcionan, y los problemas habituales de integración.

---

## El proyecto

**listBuddy** es una app de escritorio (PySide6) que lee la librería de Rekordbox (6 o 7, vía el XML que exporta) o Traktor Pro 3/4 y copia las canciones de las playlists seleccionadas a carpetas organizadas con prefijo numérico de orden. También permite previsualizar y reproducir audio directamente desde la interfaz.

### Flujo de usuario

1. La app lee el `rekordbox.xml` exportado de Rekordbox (no hace falta cerrar RB) o la colección NML de Traktor.
2. Muestra las playlists agrupadas en carpetas plegables; solo las playlists tienen checkbox (las carpetas no se marcan).
3. El usuario elige carpeta de destino, marca playlists, y exporta.
4. Un `QThread` copia los archivos con nombre `001 - Artist - Title.mp3`, mostrando progreso y log.

---

## Arquitectura

```
main.py              → entry point. Solo QApplication + MainWindow.show().
ui.py                → MainWindow (PySide6). Árbol de playlists, preview, reproducción, exportación.
worker.py            → ExportWorker (QThread). Copia archivos; emite signals log/progress/finished_ok.
db.py                → Utilidades compartidas: order_playlist_songs(), key_bpm_of().
rekordbox_xml.py     → Lector del rekordbox.xml exportado. open_library(), get_playlist_tree(), get_songs().
rekordbox_export.py  → Lógica base validada. NO modificar sin causa mayor.
app_paths.py         → Carpeta de datos del usuario (settings.ini, rekordbox_fixes.json): Application Support (macOS) / %APPDATA% (Windows).
rekordbox_fixes.py   → Persistencia de reparaciones de Rekordbox en rekordbox_fixes.json; se aplican al cargar el XML.
rekordbox_xml_relocate.py → Reparar enlaces de la fuente Rekordbox (busca por nombre); las rutas nuevas van a rekordbox_fixes.json. El XML nuevo importable lo escribe rekordbox_xml.write_playlists_xml.
traktor_db.py        → Parser de colección NML de Traktor Pro 3/4. open_collection(), get_playlist_tree().
preview_worker.py    → PreviewWorker (QThread). Existence checks en background; emite GroupData.
audio_player.py      → AudioPlayer (QMediaPlayer+FFmpeg). play/pause/seek; señales playing_changed, position_changed, track_finished.
waveform_worker.py   → WaveformWorker (QThread). Picos de la onda del footer.
audio_decode.py      → buffer_to_mono (helper de decode compartido).
footer.py            → FooterBar (reproductor, destino, exportar, progreso).
ui_components.py     → PlaylistCard, PlaylistGroup, SeekBar, WaveformSeek, ElidedLabel, FileRow, ClickableLabel.
styles.py            → Tokens de diseño dark/light + load_qss().
about_dialog.py      → «Acerca de» (avisos GPL) + visor de LICENSE y THIRD_PARTY_NOTICES.md.
licenses/            → Textos completos de licencias de terceros (regenerar con scripts/collect_licenses.py).
rb_exporter.spec     → Spec de PyInstaller para empaquetar (produce "listBuddy" ejecutable).
requirements.txt     → Dependencias pineadas exactas.
plans/               → Planes de implementación autocontenidos para ejecutar con Sonnet.
```

**Regla de imports:** `main → ui → worker/db → rekordbox_export`. Nunca al revés.

### Funciones clave de `rekordbox_export.py` (no duplicar, solo envolver)

| Función | Qué hace |
|---|---|
| `get_songs(playlist)` | Songs de una playlist; prueba `Songs`, `songs`, `items` |
| `get_content(song)` | Contenido (pista) del song; prueba `Content` y `content` |
| `get_artist(content)` | Artista; prueba `ArtistName`, `Artist`, `artist_name`, `artist` |
| `resolve_path(raw_path)` | Normaliza rutas `/C/Users/...` → `C:/Users/...` y verifica existencia |
| `sanitize(name)` | Elimina chars inválidos para nombres de archivo (`\/:*?"<>|`) |

---

## Entorno de desarrollo

```
Python       3.14.3  (CPython)
PySide6             6.12.0
PySide6_Essentials  6.12.0
PySide6_Addons      6.12.0
shiboken6           6.12.0
certifi      2026.7.22
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

### Fuente: el rekordbox.xml exportado (ADR-004)

List Buddy lee Rekordbox **solo** del XML que el usuario exporta (Archivo → Exportar colección en formato xml; formato publicado por AlphaTheta para terceros, `xml_format_list.pdf`) y lo elige en ⚙ Configuración → Librerías. Sirve igual para Rekordbox 6 y 7, y funciona con Rekordbox abierto. El usuario reexporta cuando cambia sus playlists. El parser es `rekordbox_xml.py` (`open_library()`, `get_playlist_tree()`, `get_songs()`).

**Regla: nunca abrir ni escribir `master.db`; nada de pyrekordbox/sqlcipher3 en el proyecto ni en el bundle (ADR-004).** Para reparar enlaces rotos en Rekordbox se le indica al usuario usar Reubicar de Rekordbox y reexportar, o usar la reparación de List Buddy (ver Addendum T-081).

**Regla (T-081): las reparaciones de Rekordbox van a `rekordbox_fixes.json` (carpeta de datos, `app_paths.py`); nunca al XML del usuario ni a `master.db`.** «Exportar XML para Rekordbox…» escribe un XML nuevo y rechaza el XML cargado como destino.

| Elemento / atributo del XML | Qué es |
|---|---|
| `DJ_PLAYLISTS` | Raíz del documento |
| `COLLECTION/TRACK` | Una pista: `TrackID`, `Name` (título), `Artist`, `Location`, `AverageBpm`, `Tonality` |
| `AverageBpm` | BPM como float plano (`128.00`); `0` o vacío = sin dato (no hay ×100 como en la vieja DB) |
| `Tonality` | Tonalidad tal cual la exporta Rekordbox (`8A`, `Am`) |
| `Location` | URI `file://localhost/...` con escapes `%xx`; en Windows `file://localhost/C:/Users/...` |
| `PLAYLISTS/NODE` | Árbol de carpetas y playlists: `Type="0"` carpeta, `Type="1"` playlist; `Name` |
| `NODE[Type=1]/TRACK` | Entrada de playlist en el orden real; `Key` referencia `TrackID` (o `Location` si `KeyType="1"`) |

`Location` se convierte con `location_to_path()` (decodifica `%xx`, saca la barra previa de `/C:/`, soporta UNC). El orden de la playlist es el orden de los `TRACK` dentro del `NODE`.

---

## Empaquetado — macOS

### PyInstaller en macOS (prioridad actual)

```bash
pip install pyinstaller
pyinstaller rb_exporter.spec
# El bundle queda en dist/List Buddy.app (Intel o arm64 según la Mac que buildea; mínimo macOS 13)
```

El `.spec` ya está configurado. Para macOS el resultado es un `.app` bundle. **No se puede cross-compilar:** el `.app` solo se puede generar desde una Mac, y el `.exe` de Windows solo desde Windows.

#### Checklist para que el .app funcione correctamente

1. **Sin SQLCipher ni pyrekordbox:** el spec los lista en `excludes=` (junto con `sqlalchemy`) y `tests/test_packaging_manifest.py` lo verifica. Tras buildear, `find "dist/List Buddy.app" -iname "*pyrekordbox*" -o -iname "*sqlcipher*" -o -iname "*sqlalchemy*"` debe dar vacío.

2. **Sin clave de desencriptado:** no hay nada que descifrar; no se incluye ninguna clave de AlphaTheta (ADR-004).

3. **Hidden imports:** el spec declara solo `PySide6.QtMultimedia`, `PySide6.QtSvg`, `numpy`, `certifi`. Si aparece `ModuleNotFoundError` en runtime, agregar el módulo faltante.

4. **Ícono:** crear `icon.icns` (macOS). Descomentar `icon='icon.icns'` en el spec antes de buildear.

5. **Firma de código (Code Signing):** sin firma, macOS Gatekeeper bloquea el .app. Para distribuir:
   - **Sin firma** (solo para el propio usuario): click derecho → Abrir → Confirmar en el diálogo.
   - **Con firma ad-hoc** (para distribuir a conocidos sin Developer ID):
     ```bash
     codesign --force --deep --sign - "dist/List Buddy.app"
     ```
   - **Con Developer ID** (distribución pública sin Mac App Store):
     ```bash
     codesign --force --deep --options runtime \
       --sign "Developer ID Application: Tu Nombre (TEAMID)" \
       "dist/List Buddy.app"
     xcrun notarytool submit "dist/List Buddy.zip" --apple-id ... --password ... --team-id ...
     xcrun stapler staple "dist/List Buddy.app"
     ```

6. **Arquitectura:** por defecto PyInstaller empaqueta para la arquitectura del sistema donde se corre. Para crear un **Universal Binary** (arm64 + x86_64):
   ```bash
   pyinstaller rb_exporter.spec --target-arch universal2
   ```
   Requiere que las dependencias nativas (PySide6/Qt, numpy) también sean universal.

8. **Audio (QtMultimedia + FFmpeg):** el spec declara `PySide6.QtMultimedia` y `numpy`
   en `hiddenimports`. **PyInstaller 6.x recoge automáticamente** los plugins
   multimedia (`libffmpegmediaplugin.dylib`, `libdarwinmediaplugin.dylib`,
   `QtMultimedia.framework`, `libavcodec/format/util`) — no hace falta colectar
   manualmente. Verificar en runtime que aparezca:
   `qt.multimedia.ffmpeg: Using Qt multimedia with FFmpeg version ...`
   QtMultimedia y FFmpeg vienen en `PySide6_Addons`, no en Essentials. Layout
   verificado en Windows: `PySide6/plugins/multimedia/ffmpegmediaplugin.dll` y
   `avcodec/avformat/avutil/swresample/swscale-*.dll` en la raíz de `PySide6/`.
   Layout en macOS: a verificar en T-055.
   Si el audio no suena en el bundle, incluir manualmente con (rglob recursivo,
   conserva la jerarquía del paquete):
   ```python
   binaries += collect_dynamic_libs(
       'PySide6', search_patterns=['*mediaplugin*', 'av*', 'sw*', 'libav*', 'libsw*'],
   )
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
   PyInstaller+PySide6 puede requerir `cs.allow-unsigned-executable-memory`. Pasar con `--entitlements entitlements.plist` en codesign.

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
# El ejecutable queda en dist/listBuddy/listBuddy.exe
```

- `icon.ico` para el ícono (descomentar línea en spec).
- UPX está habilitado (`upx=True`) para reducir tamaño. Si da problemas de antivirus, deshabilitar.
- Si el .exe abre pero falla al leer el XML/NML: revisar el log (`%LOCALAPPDATA%\listBuddy\logs\listBuddy.log`).

---

## Convenciones del proyecto

- **Idioma de la UI:** español rioplatense (`Elegí`, `Marcá`, `Hacé click`). No cambiar a español neutro ni inglés.
- **Type hints en todo.** Funciones y métodos tipados con `from __future__ import annotations`.
- **Sin estado global.** Dependencias explícitas por parámetro.
- **No reescribir** `rekordbox_export.py` sin causa mayor. Es la lógica base validada; las otras capas la envuelven.
- **Rekordbox no hace falta cerrarlo** (se lee un XML exportado). Traktor sí debe estar cerrado al reparar enlaces.
- **Ante cualquier ambigüedad sobre el formato del XML de Rekordbox o el NML de Traktor:** preguntar antes de asumir.

---

## Reglas de trabajo (para Claude)

- Antes de modificar `rekordbox_export.py`, verificar que el cambio no rompa las funciones que `db.py` y `worker.py` consumen.
- Nunca abrir ni escribir `master.db`; no reintroducir pyrekordbox/sqlcipher3 (ADR-004).
- Si se leen atributos nuevos del XML, usar `el.get('Atributo')` con fallback defensivo (pueden faltar).
- Si algo del spec de PyInstaller no se entiende, verificar la documentación de PyInstaller antes de modificar flags al azar.
- Los errores de apertura de la librería (XML/NML) deben siempre mostrar un mensaje claro al usuario vía `QMessageBox`, nunca stacktrace crudo.
- `ExportWorker` corre en un `QThread` — nunca actualizar widgets de Qt directamente desde `run()`, siempre via signals.
- El conteo de progreso usa `total_songs` acumulado antes del loop; no recalcular mid-flight.

---

## Tests (T-075)

```bash
python -m pytest -q          # ~45 s: pytest.ini fija -n 4 (pytest-xdist, requirements-dev.txt)
python -m pytest -q -n 0     # en serie, ~2-2,5 min (para depurar un test)
```

- Los tests de Qt corren en un intérprete **aparte** del de pytest (aislamiento de binding, T-033: PyQt6 sigue instalado en el venv y nunca deben convivir dos Qt en un proceso).
- Los que arrancan con `BOOT` (`tests/_window_boot.py`) reutilizan un único intérprete Qt por worker de pytest (`tests/_qt_warm_worker.py`): entre snippets cierra las ventanas, frena timers, restaura los atributos de módulos y clases del proyecto y vuelve al tema dark.
- Siguen con un proceso nuevo por test (`cold=True` o sin `BOOT`): los de `test_fade_lifecycle.py` (miran SIGSEGV/stderr), `test_fonts_icons.py`, `test_styles_static.py`, `test_contrast.py`, `test_audio_decode.py`, `test_playlist_order.py`, `test_excepthook_slot.py`, `test_qt_binding.py` (necesitan import/arranque limpio o miran el estado del proceso).
