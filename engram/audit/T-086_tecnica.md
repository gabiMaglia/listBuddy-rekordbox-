# T-086(d) — Auditoría técnica y de rendimiento pre-release 1.0.0

Autor: nerv-desktop · Fecha: 2026-10-15 · Alcance: solo lectura sobre el código de producción (no se modificó ni commiteó nada del repo; solo se escribió este archivo).
Entorno de medición: macOS 14 (Darwin 23.6, Intel x86_64), Python 3.14.3, PySide6 6.11.1, plataforma Qt `cocoa` (ventana real 980×700), venv `.venv`.
Scripts/fixtures/perfiles (reproducibles): `/private/tmp/claude-501/-Users-gabrielsk-Desktop-REKORDBOX-EXTRACTOR/0eba9834-e91d-46a2-813c-c2d961ec1706/scratchpad/audit-tecnica/` (`gen_fixture.py`, `bench_toggle.py`, `bench_parse.py`, `bench_boot.py`, `proto_listview.py`, `t1…t9_*.py`, `launch_time.py`, `sample.txt`).

> Caveat de medición: la máquina estuvo cargada (load average 70–100) durante las primeras corridas; esas se descartaron. Todos los números de este informe salen de corridas con load average ≈ 4. `ui_cpu_ms` es `time.thread_time()` del hilo de UI (CPU real, inmune a preempción); `maxgap`/`sum_gt16` son tiempos de pared de un heartbeat de 1 ms (hueco máximo entre ticks = peor frame). El arnés mete ≈150 ms de espera activa por click, así que las diferencias entre modos son válidas pero el valor absoluto de «click n=1» incluye ese piso.

---

## 1. Resumen ejecutivo

1. **Causa raíz del drop de fps (medida):** cada tilde de playlist destruye TODA la vista previa y la reconstruye entera, y cada fila es un `QWidget` con 5–6 `QLabel` hijos construidos en el hilo de UI (≈6 widgets y 0,8 ms de CPU de Python por fila, ≈2,4 ms por fila de punta a punta con layout/polish/paint). El costo por click crece linealmente con las playlists ya marcadas (697 → 4.779 ms de CPU de UI del click 1 al 10) y el acumulado es cuadrático (11.000 filas construidas para marcar 10 playlists de 200 pistas, 27,9 s de CPU de UI en total). Además cada tarjeta solo muestra ~5 filas (scroll interno de 190 px), pero se construyen las 200.
2. Alternativa medida: tarjeta con `QListView` + delegate pintado = 88 ms vs 3.861 ms para 10 tarjetas × 200 filas (44× menos, 68 vs 12.088 widgets vivos). Reusar las tarjetas ya dibujadas (diff por tilde) vuelve el costo por click constante.
3. **Crashes reproducidos (SIGABRT, exit 134):** (a) tildar una segunda playlist mientras el `PreviewWorker` anterior sigue chequeando archivos (≥5 ms por `stat`, típico de USB/red) → `QThread: Destroyed while thread is still running`; (b) cerrar la app en los primeros ~4 s con el chequeo de actualización en vuelo → mismo abort al salir. Ambos violan el contrato documentado de `~QThread`.
4. **Integridad de datos en export:** una copia interrumpida (disco lleno, USB desconectado) deja un archivo truncado que el reintento da por «Ya existe» y nunca repara (reproducido: 300.000 de 1.000.000 bytes quedaron como válidos). Dos playlists con el mismo nombre (carpetas distintas) se mezclan en una sola carpeta destino y pierden pistas por «Ya existe» (reproducido: 2 de 3 pistas no se copiaron).
5. **XML grande en el hilo de UI:** `open_library` corre sincrónico en `MainWindow.__init__` antes de `show()`: 1,0 s para 15 MB / 40k pistas, pero **7,9 s y 1,15 GB de RSS** para un XML de 148 MB con beatgrids/cues (realista para librerías grandes). La app queda sin ventana ese tiempo.
6. Reparación de enlaces: el matching no normaliza NFC/NFD, así que archivos con tildes en disco (NFD) no matchean el nombre del XML (NFC) → 0 candidatos (reproducido).
7. Empaquetado: arranque del .app ≈1,2 s hasta `main()` y ≈2,0–2,8 s hasta ventana visible (sin XML); 140 MB, de los cuales ≈21 MB son Qt sin uso (QtPdf, QtQuick/QtQml*, VirtualKeyboard). `scripts/build_windows.ps1` busca un `.exe` en una ruta que el spec nunca produce (siempre reporta «Build fallido»).
8. Lo bueno: sin fugas de memoria detectables en audio (400 cambios de pista a 15 ms: RSS +9 MB, fds/hilos vuelven al nivel base), `_wave_cache` sí tiene tope (32), las señales lambda de los workers se despachan al hilo de UI, escrituras atómicas con fsync+`os.replace`, logs rotativos, sin pyrekordbox/sqlalchemy/PyQt6 en el bundle.

---

## 2. Tabla de hallazgos priorizados

Esfuerzo: S ≤ 0,5 día · M ≈ 1 día · L ≈ 2–3 días. «Evidencia» = medición propia (comando en la sección 6) salvo que diga otra cosa.

| ID | Sev | archivo:línea | Descripción | Evidencia medida | Acción propuesta | Esf. |
|---|---|---|---|---|---|---|
| TEC-01 | **Alta** | `ui.py:1482-1512` (`_start_preview_worker`), `ui.py:1453-1473` (`_clear_preview_layout`), `ui.py:1609-1654` (`_pump_render_queue`), `ui.py:1675-1696` (`_batch_rows`), `ui.py:1734-1793` (`_make_row_widget`), `preview_card.py:148-149` | Cada tilde (vía `_update_order_numbers`, `ui.py:1391` → debounce 80 ms) borra todas las `PreviewGroupCard` y reconstruye todas; cada fila = `FileRow` + 5-6 `QLabel` creados en el hilo de UI; se construyen las N filas aunque el scroll de la tarjeta (190 px) muestre ~5. | 10 clicks sobre playlists de 200 pistas: CPU de UI del click n = 697 ms (n=1) … 4.779 ms (n=10); 11.000 filas construidas; 27,9 s de CPU total; hueco máx. 392 ms (frame budget 16,7 ms). Una playlist de 2.000 pistas: 8,3 s de CPU de UI en UN click, 12.211 widgets, 138 frames perdidos, y 17,7 s al segundo click. | Ver sección 3 (QListView+delegate y/o reuso de tarjetas; mínimo: filas perezosas). | L (A+B) / S (solo perezoso) |
| TEC-02 | **Alta** | `ui.py:1475-1480` + `ui.py:1497-1503`; `preview_worker.py:71,113` | `_cancel_preview_worker` solo marca `_stop` y suelta las señales; `_start_preview_worker` reasigna `self._preview_worker` y el wrapper Python del hilo viejo (aún corriendo en un `stat` lento) se destruye → Qt aborta. Además `PreviewWorker.finished` (línea 71) **pisa** `QThread.finished` y se emite desde `run()` antes de que el hilo termine realmente. | `t2_inapp_preview_crash.py`: ventana real, 2 clicks seguidos con `stat` de 50 ms → `QThread: Destroyed while thread '' is still running`, **exit 134**; reproduce con 5 ms/stat; con 1 ms o 0 no (el hilo termina antes). Doc Qt: «Deleting a running QThread (i.e. isFinished() returns false) will result in a program crash. Wait for the finished() signal before deleting the QThread» (doc.qt.io/qt-6/qthread.html, vía Context7). | Mantener los workers cancelados vivos en un set hasta su `QThread.finished` real (mismo patrón que `_live_wave_workers`, `ui.py:1946-1951`); renombrar la señal propia (`done`) para no pisar `finished`; `wait()` acotado en `closeEvent`. | S |
| TEC-03 | **Alta** | `ui.py:1970-2004` (`closeEvent`), `ui.py:2737-2744`, `update_checker.py:119-122` | `closeEvent` espera solo 200 ms al `UpdateCheckWorker`; `urlopen(timeout=4)` no cubre la resolución DNS (puede bloquear mucho más). Si el hilo sigue vivo al salir → abort. Mismo riesgo con `ExportWorker.wait(4000)` (`ui.py:1989-1991`) si una copia grande tarda más de 4 s: se destruye el hilo corriendo y queda un archivo truncado (ver TEC-04). | `t7_quit_update.py`: `urlopen` simulado de 3 s, cerrar a los 300 ms → `QThread: Destroyed while thread is still running`, **exit 134**. En el .app real, el chequeo hoy devuelve HTTP 404 (log: `Chequeo de actualización omitido (HTTPError: HTTP Error 404: Not Found)`), o sea que el hilo vive ~1,7 s en el arranque. | Hacer el hilo «huérfano seguro»: `setParent(None)`+referencia global hasta `finished`, o sacar el chequeo a `QNetworkAccessManager` (async, sin hilo); en export, esperar hasta que termine el archivo en curso (sin timeout fijo) o confirmar con el usuario. | S |
| TEC-04 | **Alta** | `worker.py:180-198` | `dest.exists()` → «Ya existe»; `shutil.copy2` escribe directo sobre el nombre final. Si falla a mitad (ENOSPC, USB desconectado, kill) queda un archivo parcial que el próximo export salta. | `t3_export.py`: ENOSPC simulado en la 3.ª copia deja `003 - …mp3` de 300.000 B (original 1.000.000 B); el reintento lo informa como «Ya existe» y devuelve `(179, 18, 3, 'ok')` con el parcial intacto. | Copiar a `dest.name + ".part"` y `os.replace` al terminar; en el skip comparar tamaño (`st_size`) con el origen; borrar el `.part` en `except`. | S |
| TEC-05 | **Alta** | `rekordbox_xml.py:231` (`ET.parse`), `rekordbox_xml.py:40,186` (`element=el`), `ui.py:362` (`_load_playlists()` en `__init__`, antes de `show()` en `main.py:30`), `ui.py:1209-1250` | Parseo completo del XML en el hilo de UI y antes de mostrar la ventana; cada `RbxTrack` retiene su `ET.Element` (con todos sus hijos TEMPO/POSITION_MARK) solo para el export de XML (`rekordbox_xml.py:317`). Sin tope de tamaño. | 15 MB / 40k pistas: 1.017 ms, RSS 15→142 MB. 148 MB (40k pistas, 48 hijos/pista): **7.874 ms, RSS 15→1.153 MB**. Carga de 200 playlists en la ventana: `_load_playlists` 1.435–1.992 ms + construcción de 200 `PlaylistCard`. | Mover `open_library` a un `QThread` con estado «Cargando…» (ventana visible primero); `iterparse` + `clear()` y guardar en `RbxTrack` solo los atributos (`dict(el.attrib)`) o re-leer el XML al exportar; mostrar error claro si supera un umbral. | M |
| TEC-06 | Media | `relocate_core.py:349,460,366-378` | El índice y el lookup usan `name.lower()` sin normalizar Unicode. XML (NFC) vs disco macOS (NFD, p. ej. copiado de otros Mac/Linux) → 0 candidatos; el fallback `_normalize_key` tampoco normaliza. (`rekordbox_xml.py:281` sí normaliza NFC para el export; acá no.) | `t6_nfd.py`: NFC(XML) vs NFD(disco) → **0 candidatos**; NFD vs NFD → 1. | `unicodedata.normalize("NFC", …)` en las claves de ambos índices y en `find_candidates`; test con nombre acentuado. | S |
| TEC-07 | Media | `worker.py:123`, `rekordbox_export.py:21-26` (`sanitize`) | Destino = `sanitize(pl.Name)`: dos playlists con igual nombre (carpetas distintas, o `#2` en la misma) escriben en la MISMA carpeta y los «Ya existe» ocultan pérdidas; `sanitize` no trata `..`, `.`, vacío (escribe en la raíz del destino o fuera de ella), nombres reservados de Windows (`CON`, `NUL`, `COM1`…) ni punto final. | `t9_perm_dup.py`: 2 playlists homónimas → una sola carpeta, resultado `(4 copiadas, 1 no encontrada, 2 saltadas)`; las 2 pistas «saltadas» de la segunda playlist nunca se copiaron. `t4_names.py`: `sanitize("..")=".."` y `(destino/"..").resolve()` escapa al padre; `CON`, `nul`, `COM1`, `Mi set.` pasan intactos. | Desambiguar carpeta (`Nombre (2)` / prefijar carpeta padre), avisar en la UI antes de exportar; endurecer `sanitize` (strip de `.`/espacios finales, prefijo `_` para reservados, vacío → «Sin nombre», chequear que `dest_dir.resolve()` quede bajo el destino). | S-M |
| TEC-08 | Media | `worker.py:96-117,237-250` | `_estimate_size` suma el tamaño de TODOS los archivos de origen, ignorando los que ya existen en el destino; un re-export incremental a un disco casi lleno aborta con «Espacio insuficiente» sin necesitar espacio. Además hace un `stat` extra por pista. | Por lectura de código (no reproducido con disco real; la rama `free < total_bytes` es incondicional). | Restar los destinos ya presentes (mismo nombre y tamaño) o reducir a «estimación ≥ libre + margen» solo como advertencia, no como abort. | S |
| TEC-09 | Media | `ui.py:2154-2157` (`_log`), `ui.py:963` (creación de `log_view`) | `QPlainTextEdit` sin `setMaximumBlockCount`; ExportWorker emite 2+ señales por archivo. Una exportación de 40k pistas deja 80k+ bloques y tiempo de append creciente. | `t5_log.py`: 40.000 `appendPlainText` → 11.444 ms, peor llamada 87 ms, RSS +207 MB. | `self.log_view.setMaximumBlockCount(5000)` (o agrupar logs por lote en el worker). | S |
| TEC-10 | Media | `worker.py:230-234`, `ui.py:1586-1587` | `except Exception: return []` / `pass`: si falla `get_songs` o la extracción, la playlist desaparece del export (o del preview, y el resultado vacío queda **cacheado** en `_track_meta_cache`, `ui.py:1588`) sin ningún mensaje. | Por lectura. `worker.py:89-91` descarta la playlist si `songs` está vacía sin loguear. | Loguear con `_log.exception` y emitir una línea `✗ no se pudieron leer las pistas de «X»`; no cachear en error. | S |
| TEC-11 | Media | `scripts/build_windows.ps1:50-56` | El script verifica `dist\listBuddy.exe`, pero el spec (one-dir) produce `dist\listBuddy\listBuddy.exe` (`rb_exporter.spec:132-141`) → imprime «Build fallido» aun con build correcto. Usa el `.venv` de desarrollo (en macOS ya se usa `.venv-build` limpio) y `pip install pyinstaller` sin pin (macOS pinea 6.20.0). | Por lectura (no hay Windows disponible; **no verificado en ejecución**). | Corregir ruta, venv limpio y pin de PyInstaller; sumar chequeo de hash/tamaño como en macOS. | S |
| TEC-12 | Baja | `rb_exporter.spec:48` (`excludes`), `rb_exporter.spec:38-43` | El bundle trae ≈21,5 MB de módulos Qt sin uso: QtPdf, QtQuick, QtQml(+Meta/Models/WorkerScript), QtVirtualKeyboard(+Qml), plugin `libqpdf` y `libqtvirtualkeyboardplugin`. Dependencias inversas verificadas con `otool -L`: solo los plugins de PDF/teclado virtual los enlazan; ni QtCore/Gui/Widgets/Multimedia. | `du -ck` sobre esos frameworks/plugins = 21.516 KB de 140 MB. | Agregar a `excludes` `PySide6.QtPdf`, `PySide6.QtQuick`, `PySide6.QtQml`, `PySide6.QtVirtualKeyboard` y filtrar los plugins; **no verificado con un build real** (no se rebuildeó para no tocar `dist/`/`build/`). | S |
| TEC-13 | Baja | `scripts/release_mac.sh:26,29-36,38-42,44-51`; `rb_exporter.spec:101-102` vs `ui.py:100` | Mayormente idempotente (borra `build`, `$APP`, `$DMG`; recrea el DMG con `-ov`). Detalles: sin `trap` para borrar `$STAGE` si falla `hdiutil`; con `DEVELOPER_ID` pero sin `NOTARY_PROFILE` firma y **no** notariza ni avisa; `codesign --deep` está desaconsejado por Apple para bundles con frameworks anidados (firma «de adentro hacia afuera» es lo robusto; **no verificado** que pase la notarización); la versión está duplicada (`ui.py:100` y el Info.plist del spec). `dist/` guarda artefactos viejos (`listBuddy-1.0.dmg`, `List Buddy` de junio) que el script no limpia. | Lectura + `ls dist`. El .app actual es ad-hoc (`codesign -dv`: `Signature=adhoc`, `TeamIdentifier=not set`). | `trap 'rm -rf "$STAGE"' EXIT`; abortar o avisar fuerte si hay `DEVELOPER_ID` sin `NOTARY_PROFILE`; leer la versión desde un único lugar. | S |
| TEC-14 | Baja | todo `ui.py` (2.754 líneas, 124 métodos en `MainWindow`, `__init__` de 160 líneas `ui.py:210`), `preview_card.py:37` (`__init__` 124 l.), `worker.py:77` (`run` 149 l.), `traktor_relocate.py:407` (`run` 126 l.) | God-object `MainWindow` (UI + estado de export + relocate + audio + tema + cache de preview). Acoplamientos: `ui_components ↔ preview_card` (ciclo roto con import diferido, `ui_components.py:271` en `FileRow.resizeEvent`), `ui_components`/`preview_card` importan `preview_worker` (capa worker) solo por el DTO `TrackRow`, `rekordbox_export.py:127` importa `rekordbox_xml` (inverso a la regla `… → rekordbox_export`, aunque solo en el CLI). ≈40 funciones sin type hints completos (`ui_components.py` 17, `rekordbox_export.py` 6, `ui.py` 6). | Análisis AST (script inline, ver sección 6). | Extraer `PreviewController` (cola, cache, worker) y `ExportController`; mover `TrackRow`/`GroupData` a un módulo de modelos sin Qt; completar hints. | L |
| TEC-15 | Baja | `ui.py:1808-1845`, `ui.py:1901-1908` | `_play_file_row` hace `resolve_path` (`stat`) y `QMediaPlayer.setSource/play` en el hilo de UI; `_row_for` recorre con `findChildren(FileRow)` todas las filas en cada fin de pista (O(filas)). | `t8_audio.py`: `AudioPlayer.play()` bloquea el hilo de UI 17,7 ms de media (máx 45,8 ms) con WAV locales; con un disco de red/USB lento será mayor. 400 cambios rápidos de pista: RSS 59→68 MB, fds 52→66→57, hilos 5→11→7 (sin fuga). | Mantener un `dict[raw_path, FileRow]` (o el modelo del TEC-01); aceptar el costo de `setSource`. | S |
| TEC-16 | Baja | `ui.py:187-203` | `DonationDialog._make_qr` importa `qrcode`, que **no** está en `requirements.txt` ni instalado en `.venv`/`.venv-build` → siempre cae al `except Exception` y muestra la URL como texto (código muerto). | `python -c "import qrcode"` → `ModuleNotFoundError` en ambos venv. | Agregar la dependencia (y a THIRD_PARTY_NOTICES) o borrar la rama QR. | S |
| TEC-17 | Baja | `rekordbox_xml.py:171-175` | `_track` hace `original.exists()` por cada pista con reparación guardada, en el hilo de UI al cargar/recargar. En un volumen de red colgado cada `stat` puede bloquear. | Por lectura; **no medido** con red real. | Resolver las reparaciones en el worker de carga (TEC-05) o lazy. | S |
| TEC-18 | Baja | `ui.py:275` (`_exists_cache`), `ui.py:1195-1207` | El cache de existencia solo se invalida al recargar/terminar un export/relocate; conectar el disco después de ver «roto» sigue mostrando roto hasta Ctrl+R. | Por lectura. | Botón/atajo «Revisar de nuevo» o TTL corto para entradas `False`. | S |
| TEC-19 | Baja | `rekordbox_export.py:40-45` (`resolve_path`) | La heurística `/X/…` → `X:/…` también transforma rutas POSIX reales de un solo carácter (`/a/b` → `a:/b`). Raro en la práctica (los volúmenes son `/Users`, `/Volumes`), pero no debería disparar en macOS. | Por lectura. | Aplicarla solo si `sys.platform == "win32"`. | S |
| TEC-20 | Baja | `app_logging.py:44-46` | Dos instancias de la app comparten `listBuddy.log` y `settings.ini`; en Windows el rollover de `RotatingFileHandler` con el archivo abierto por otro proceso lanza `PermissionError`. No hay guarda de instancia única. | **No verificado en Windows.** | Guarda de instancia única (`QLockFile`) o `delay=True` + manejo de error de rollover. | S |
| TEC-21 | Baja | `worker.py:36-63`, `worker.py:123-124` | `_MAX_STEM = 200` está en caracteres, pero los límites de nombre son 255 unidades UTF-16 (APFS/NTFS) o bytes (ext4); con títulos con muchos emojis falla. Ruta total en Windows > 260 (carpeta ≤ 80 + archivo 200 + destino) sin `\\?\` ni manifest long-path. | `t4_names.py`: título de ~200 emojis → `OSError 63 File name too long` en APFS (770 B); 200 caracteres acentuados/CJK pasan. Ruta Windows de ejemplo = 302 caracteres. **Long paths en Windows no verificado.** | Medir `len(stem.encode("utf-16-le"))//2`; usar prefijo `\\?\` en Windows. | S |

---

## 3. Causa raíz del drop de fps

### 3.1 Lo que pasa, paso a paso (código)
1. Click en `PlaylistCard` → `mousePressEvent` → `toggled` → `_on_card_toggled` → `_update_order_numbers` → `self._preview_debounce.start()` (`ui.py:1365-1391`).
2. A los 80 ms `_start_preview_worker` (`ui.py:1482`): `_clear_preview_layout()` borra **todas** las tarjetas del preview con `deleteLater`, `_extract_preview_data(selected)` reconstruye los `TrackRow` de **todas** las playlists marcadas en el hilo de UI (5→17 ms por click con 1→10 playlists), lanza un `PreviewWorker` nuevo y re-renderiza **todo** (`_pump_render_queue` un grupo por tick, `_batch_rows` de 15 filas por tick).
3. Cada fila (`_make_row_widget`, `ui.py:1734`) crea un `FileRow` + `QHBoxLayout` + 4 a 6 `QLabel` (índice, título, artista, aviso, key/BPM, chip), con `setObjectName` y `setProperty`, y la QSS global (194 reglas, `qss/app.qss`) hace polish de cada uno al mostrarse.
4. La tarjeta tiene `scroll.setFixedHeight(min(190, n*38))` (`preview_card.py:148-149`): muestra ≈5 filas, pero se instancian las 200 (o 2.000).
5. Al tildar la siguiente playlist se repite todo desde cero, con una tarjeta más.

### 3.2 Números medidos (playlists de 200 pistas, 5 % rotas, ventana real, 10 tildes seguidas, 150 ms entre clicks)
CPU del hilo de UI por click (`thread_time`, incluye ≈150 ms de espera activa del arnés) y peor frame:

| Click n (playlists marcadas) | CPU UI del click | Filas construidas hasta ahí (acum.) | Hueco máx. del event loop |
|---|---|---|---|
| 1 | 697 ms | 200 | 84 ms |
| 3 | 1.599 ms | 1.200 | 145 ms |
| 5 | 2.471 ms | 3.000 | 177 ms |
| 8 | 4.088 ms | 7.200 | 409 ms |
| 10 | 4.779 ms | 11.000 | 392 ms |
| **Suma 10 clicks** | **27,9 s** | **11.000** | — |

- Widgets: ≈1.200 nuevos por playlist de 200 pistas (`QApplication.allWidgets()`: 354 al arrancar → 9.887 con 10 playlists marcadas; 12.211 con una playlist de 2.000 pistas, ≈6 widgets/fila).
- Python (envolviendo con `time.thread_time`): `_make_row_widget` 11.000 llamadas = 7.061 ms (0,64 ms/fila), `_batch_rows` 7.660 ms, `_pump_render_queue` 865 ms, `_extract_preview_data` 62 ms, `_clear_preview_layout` 3 ms (solo agenda `deleteLater`), `PlaylistCard._refresh` 1,8 ms/click, `_update_order_numbers` 0,7 ms/click.
- Playlist de 2.000 pistas, un click: 8.290 ms de CPU de UI, 138 huecos > 16,7 ms (≈8,9 s sin fluidez); segundo click (2 playlists): 17.706 ms, hueco máx. 490 ms. Cada lote de 15 filas no cuesta mucho por sí solo, pero el layout del contenedor crece con las filas ya insertadas (≈4,1 ms/fila a 2.000 filas vs 2,4 ms/fila a 200 → superlineal).
- Todo en el hilo de UI: el `PreviewWorker` solo hace `stat` (con cache); la creación de widgets, el polish, el layout y el paint no pueden salir de ahí.
- Dónde se va el tiempo (perfil nativo con `sample <pid> 6`, 8 clicks, hilo principal, conteos inclusivos que se solapan): `QWidget::ensurePolished`/QSS ≈ 18 %, `QLayout::activate`/`QBoxLayout::setGeometry` (con `QLabel::sizeHint`) ≈ 16 %, `QWidgetRepaintManager::sync` (paint) ≈ 15 %, destrucción de widgets (`~QWidget`, `DeferredDelete` de tarjetas viejas: 100-165 ms por tarjeta de 200 filas con el arnés `notify`) ≈ 6 %, `QGraphicsEffect` (fade-in) ≈ 4 %, resto ≈ 41 % = construcción desde Python (PySide).
- Eventos de Qt vistos con un `QApplication.notify` instrumentado: 32.693 `PolishRequest` y 29.369 `UpdateLater` en 8 clicks (distorsionado por el overhead de la propia instrumentación; sirve solo como conteo).

### 3.3 Hipótesis puestas a prueba y descartadas (6 clicks, suma de CPU UI; dos repeticiones)
| Variante | Suma CPU UI 6 clicks | Conclusión |
|---|---|---|
| Base | 10.962 / 10.702 ms | — |
| Sin fade-in (`QGraphicsOpacityEffect` desactivado) | 10.558 / 10.926 ms | **No es la causa** (±4 %, dentro del ruido) |
| `setUpdatesEnabled(False)` alrededor de cada lote | 12.044 / 11.927 ms | **Empeora ~10 %** (fuerza repintado completo al reactivar) |
| Sin QSS global (`app.setStyleSheet("")`) | 7.458 / 7.244 ms | La QSS explica ≈ 32 % del costo; el 68 % restante es construcción + layout |

Doc de referencia: `QApplication::styleSheet` «replaces the application style with a style sheet style … every later change repolishes all widgets» (doc.qt.io/qt-6/qapplication.html, vía Context7). El costo de `QGraphicsOpacityEffect` en sí no está cuantificado en la doc; lo cubre la medición propia de arriba.

### 3.4 Solución recomendada (y por qué)
**A. Dejar de crear un widget por fila: `QListView` + modelo + `QStyledItemDelegate` pintando la fila.** El item view solo pinta lo visible (la doc de Qt lo describe como el mecanismo estándar para listas grandes; `uniformItemSizes` permite optimizaciones cuando todas las filas miden igual: doc.qt.io/qt-6/qlistview.html, vía Context7; que «solo pinta lo visible» es el comportamiento documentado de las vistas pero el snippet consultado no lo cita textualmente, lo respalda la medición de abajo). Prototipo medido (`proto_listview.py`, mismo dato, 10 tarjetas × 200 filas dentro de un `QScrollArea`):
- widgets por fila (actual): **3.861 ms** de CPU de UI, 12.088 widgets vivos;
- `QListView` + delegate: **88 ms**, 68 widgets vivos → **44× menos**.
Costos a resolver: el pintado a mano de los bloques de rotas contiguas (hoy en `FileRow.paintEvent`/`_paint_block`, `ui_components.py:274-288`), el resaltado de la fila sonando (hoy `setStyleSheet` inline), el hover, el click-para-reproducir (`indexAt`) y el cambio de tema (la delegate lee los tokens); y los tests que hoy buscan `FileRow`. Esfuerzo L (≈2-3 días con tests).

**B. No reconstruir lo que ya está dibujado: diff por tilde.** Mantener `dict[cache_key → PreviewGroupCard]`; al tildar solo se crea la tarjeta nueva y al destildar solo se quita esa (y se re-numeran los títulos `NN nombre` con `setText`). Con esto el costo por click pasa de O(N·filas) a O(1 tarjeta) (≈ el costo del «click n=1» de la tabla). Esfuerzo M. Combinado con A deja el click en ≈ 10-20 ms.

**C. Parche mínimo si no hay tiempo antes de 1.0.0: filas perezosas.** Construir las primeras ~12 filas y el resto solo cuando el usuario scrollea la tarjeta (o con un `QTimer` de baja prioridad cuando el hilo está ocioso). Medido (`MODE=LAZY`, solo 12 filas por tarjeta): el click n=10 baja de 4.779 a 692 ms de CPU de UI (6,9×), hueco máx. de 392 a 66 ms; el click sigue creciendo linealmente (cada click reconstruye N tarjetas ≈ 14 ms c/u) pero deja de ser perceptible; para una playlist de 2.000 pistas: 8.290 → 360 ms. Esfuerzo S, pero requiere cuidar `_playable_tracks`/auto-avance (ya lee de los datos, `ui.py:1891`) y `_row_for`.

**D. Complementos baratos:** subir el debounce de 80 ms a ~150-200 ms para que ráfagas de tildes colapsen en un solo rebuild; `QTimer` de 0 ms con lote adaptativo según el tiempo gastado (<8 ms por tick) en lugar de 15 filas fijas; destruir tarjetas viejas en un tick separado (un `PreviewGroupCard` de 200 filas tarda 100-165 ms en destruirse de golpe).

**Alternativas descartadas por la medición:** quitar el fade-in, `setUpdatesEnabled`, tocar la QSS (ganaría ≈ 32 % pero no resuelve la escala).

Síntoma del PO («pequeño drop de fps hasta que se abren, luego va formidable»): coincide exactamente con el modelo: el drop dura lo que tarda en construirse el preview completo tras cada tilde y se nota más cuantas más playlists haya marcadas o cuanto más larga sea la playlist; cuando termina, el resto de la UI (scroll de widgets ya construidos) es barato.

---

## 4. Robustez con datos reales (objetivo 3)

| Caso | Resultado | Ref. |
|---|---|---|
| XML 15 MB / 40k pistas | Carga 1,0 s (hilo UI); 200 playlists tardan 2,2–2,9 s en abrir la ventana | TEC-05 |
| XML 148 MB (beatgrids/cues) | 7,9 s bloqueado, 1,15 GB RSS | TEC-05 |
| Nombres con emojis / acentos | Export y preview OK en APFS (verificado con `🎵 áéí`); NFC/NFD en el export XML se maneja (`_file_key`); en el relocate NO | TEC-06 |
| Título de ~200 emojis | `File name too long` en APFS | TEC-21 |
| Playlists con el mismo nombre en distinta carpeta | Se mezclan en una carpeta y se pierden pistas por «Ya existe» | TEC-07 |
| Playlists vacías | Bien: `PlaylistCard._empty` bloquea la selección y el contador excluye vacías (`ui.py:1369`) | — |
| Rutas de red/UNC | `location_to_path` soporta `file://host/share` (`rekordbox_xml.py:105-125`); un volumen colgado bloquea la UI en `stat` de reparaciones y en `play` | TEC-17, TEC-15; no verificado con SMB real |
| Archivo sin permiso de lectura | Bien: `PermissionError` (subclase de `OSError`) cae en la rama genérica, se loguea y sigue (`worker.py:188-199`); verificado con `chmod 000` | `t9_perm_dup.py` |
| Disco de destino lleno | Se aborta con mensaje claro, pero deja un archivo parcial que el reintento da por válido | TEC-04 |
| Cancelación a mitad de copia | Se chequea entre archivos (`worker.py:142`); no deja parciales por cancelar, sí por cierre forzado a los 4 s (`ui.py:1989-1991`) | TEC-03/04 |
| Destino desmontado | Bien: `mkdir` falla con aviso en `_start_export` (`ui.py:2050-2058`) y en el worker (`worker.py:127-138`); pero el `mkdir` de `_start_export` corre en el hilo de UI | — |

---

## 5. Revisado y está bien (QA no hace falta que lo mire de nuevo)

- **Despacho de señales con lambdas**: `worker.ready.connect(lambda …)` en `ui.py:1946-1951` corre en el hilo de UI (PySide6 6.11.1: `t1_lambda_thread.py` → `{'lambda_thread_is_main': True}`).
- **Hilos y widgets**: ningún worker toca widgets; las señales llevan tipos inmutables o DTOs que el worker ya terminó de llenar (`GroupData.card` viaja como `object` sin ser tocado, `preview_worker.py:50`). El `excepthook` encola el diálogo al hilo de UI (`app_logging.py:100-108`).
- **WaveformWorker**: cancelación por generación (`ui.py:1963`), hilos cancelados quedan en `_live_wave_workers` hasta su `finished` (`ui.py:1946-1951`), `closeEvent` hace `wait(1500)`, decode con tope de 20 min y timeout de 90 s (`waveform_worker.py:23-24`). `_wave_cache` tiene tope de 32 entradas (`ui.py:1966-1968`, FIFO; peor caso acotado en decenas de MB).
- **AudioPlayer**: 400 cambios de pista a 15 ms sin errores ni fuga (RSS +9 MB, fds y hilos vuelven a ~base tras `stop`) — `t8_audio.py`.
- **Escrituras atómicas**: `rekordbox_fixes.save`, `write_playlists_xml`, `restore_backup`, `write_atomic` (NML) usan tmp en la misma carpeta + `fsync` + `os.replace` y limpian el tmp en error. (Caveat Windows: `os.replace` falla con `PermissionError` si un antivirus tiene el destino abierto; los llamadores ya capturan `OSError`.)
- **Logs**: `RotatingFileHandler` 512 KB × 3, ruta por OS, `excepthook` global con log + diálogo no crudo (`app_logging.py`).
- **Bundle**: sin `pyrekordbox`/`sqlcipher`/`sqlalchemy`/`PyQt6` (`find` vacío sobre el .app); `upx=False`; datos (`qss`, `fonts`, `certifi`, licencias) presentes; la app arranca (hiddenimports suficientes); ffmpeg plugin presente.
- **Copia de archivos**: nombres con prefijo único por pista, `_safe_filename` acota el stem (`worker.py:39-63`), ENOSPC detectado por `errno 28`, chequeo previo de espacio libre.
- **Filtro y tema**: `_apply_filter` desactiva layout/updates (`ui.py:1284-1303`); `_apply_theme` destruye el preview antes de `setStyleSheet` (`ui.py:2703-2712`).
- **Regla de imports**: `main → ui → worker/db → rekordbox_export` se respeta salvo las excepciones de TEC-14; sin ciclos de import a nivel módulo (análisis AST).

---

## 6. Cómo reproducir (comandos usados)

Todo con `cd /Users/gabrielsk/Desktop/REKORDBOX_EXTRACTOR`, `S=<scratchpad>/audit-tecnica`, `.venv/bin/python`.

- Fixtures: `python $S/gen_fixture.py $S/fx30x200 30 200 0.05` (también `fx200x200`, `fx2x2000`; `fx200x200_real` = 40k pistas + 48 hijos/pista, 148 MB).
- Costo por tilde: `python $S/bench_toggle.py $S/fx30x200 10 150` (`MODE=LAZY|NOFADE|NOQSS|SETUPD` para variantes; `TIMED=1` instrumenta `QApplication.notify`).
- Perfil nativo: lanzar el bench y `sample <pid> 6 -file $S/sample.txt`.
- Parseo XML: `python $S/bench_parse.py $S/fx200x200_real/rekordbox.xml`; arranque de ventana: `python $S/bench_boot.py $S/fx200x200`.
- Prototipo QListView: `python $S/proto_listview.py list|widgets`.
- Crash del preview: `python $S/t2_inapp_preview_crash.py $S/fx30x200 0.05; echo $?` (134). Crash al salir: `python $S/t7_quit_update.py; echo $?` (134).
- Export: `t3_export.py` (parcial), `t9_perm_dup.py` (permisos + homónimas), `t4_names.py` (nombres/longitud), `t5_log.py` (log), `t6_nfd.py` (relocate NFC/NFD).
- Audio: `t8_audio.py $S`. Arranque del .app: `python $S/launch_time.py $S/fakehome` (HOME aislado; no toca los datos del usuario).
- Docs consultadas (Context7, `/websites/doc_qt_io_qt-6`): `QThread::~QThread`, `QThread::finished`, `QListView::uniformItemSizes/layoutMode`, `QAbstractItemView::setIndexWidget` (advierte usarlo solo para contenido estático visible), `QApplication::styleSheet`.

### Arranque y tamaño del .app (build existente del 14/10, ad-hoc)
- Tamaño 140 MB (63 MB el DMG): `Frameworks` 124 MB (PySide6 97 MB, numpy 9,5 MB, Python 5,3 MB), `Resources` 11 MB.
- Arranque medido con `launch_time.py` (3 corridas, HOME vacío, sin XML, load ≈ 15): `main()` alcanzado a los 1,16 / 1,16 / 1,22 s (imports de `ui`, Qt y numpy incluidos) y ventana visible a los 2,05 / 2,08 / 2,76 s. La primera ejecución tras un build puede ser más lenta por Gatekeeper/XProtect (una corrida fría midió 4,5 s hasta `main()` y 7,0 s hasta ventana, con la máquina en load 80).
- Con un XML grande el arranque se alarga por TEC-05 (la ventana no se muestra hasta terminar el parseo).
- Importante: ese .app es del 14/10 20:41 y hay commits posteriores (`b84656a`, 14/10 23:33, tocó `ui.py`/`preview_card.py`/`worker.py`); estas mediciones del bundle son de ese build, **no** de HEAD.

---

## 7. Qué NO se verificó
- Windows en general (rutas > 260, nombres reservados, `os.replace` con AV, doble instancia, DPI, `build_windows.ps1` en ejecución): solo lectura de código.
- El efecto real de las `excludes` propuestas (TEC-12) sin rebuildear, y si `codesign --deep` + notarización pasa con Developer ID (TEC-13).
- XML reales de Rekordbox (el fixture sintético tiene 48 hijos/pista; los exports reales varían) y discos de red/USB reales (se simuló latencia con `sleep` en `PreviewWorker._check`).
- Escala de pantalla 2× (Retina) y GPU: las mediciones son en la pantalla de esta Mac (Intel); un Apple Silicon más rápido reducirá los números absolutos, no la forma cuadrática.
- `traktor_db.py`/`traktor_relocate.py`/`relocate_core.py` se revisaron por muestreo (parseo, escritura atómica, índice de discos); no se auditó línea por línea el loop de resolución ni el modal `RelocateDialog`.
- El costo de `QGraphicsOpacityEffect` en sí no figura en la documentación consultada; se concluyó solo por medición (sin efecto apreciable).
