# T-094 — Verificación ciega (nerv-verifier, nivel X)

Fecha: 2026-10-15 · Árbol juzgado: `release/1.0.0-rc2` @ 7d10c38 (worktree aislado y descartable). Diff de referencia: `git diff main...release/1.0.0-rc2` sobre los archivos del ticket.
No leí `engram/qa/T-094*.md` ni los handoffs. Los criterios salen de `engram/03_backlog.md:72` (fila T-094), `engram/plans/T-094.md` (QUÉ/CÓMO y revisión de arquitectura C1-C3) y ADR-006 (`engram/02_architecture.md:199-212`).
Intérprete: `.venv/bin/python` (CPython 3.14.7, expat 2.8.4), Intel, `QT_QPA_PLATFORM=offscreen`. Las sondas están en `/private/tmp/claude-501/-Users-gabrielsk-Desktop-REKORDBOX-EXTRACTOR/b4fcb7d1-4284-4b55-9f7a-dc9bfcfaff16/scratchpad/vprobe/` (`p1.py`-`p5.py`, `gen.py`, `measure.py`, `cancel.py`). La única mutación fue en `ui.py:1239` y la revertí con `git checkout ui.py` (árbol limpio).

## §Criterios

| # | Criterio | Tipo | Veredicto | Cita / evidencia |
|---|---|---|---|---|
| 1a | Ventana visible ≤ 1,5 s con un XML de 40k pistas (ratificado por el PO) | Especificado (`03_backlog.md:72`) | Cumple, con poco margen | `ui.py:381` lanza la carga en el constructor; `ui.py:1245-1266` crea el worker y vuelve enseguida con la tarjeta «Cargando…» (`ui.py:1393-1399`). Medición propia (`measure.py`, de `MainWindow()` a `show()`+`processEvents()`): 21,8 MB → 1,333/1,367/1,377/1,445 s; 133,9 MB con 47 hijos por pista → 1,332/1,370/1,388/1,412 s. Sin carga (XML de 1 pista): 0,829 s, así que el hilo de carga le suma unos 0,5 s al arranque por la competencia por el GIL. Contando desde el inicio del proceso (con imports) da 2,04-2,26 s; la ratificación del PO usa la medida desde el constructor («medido 1,3 s»). |
| 1b | RSS ≤ 3× el tamaño del XML (medido) | Especificado | Cumple con un XML realista; **ambiguo** con un XML de 40k pistas sin cues (ver supuesto A1) | Proceso completo con ventana: 133,9 MB → RSS pico 341-353 MB = **2,55-2,64×**. Solo `open_library`, sin Qt: 1,65× de delta (1,76× absoluto) contra 8,46× de `ET.parse` en `main`. Con 21,8 MB sin cues: proceso 10,1-10,5×, `open_library` 4,60× de delta (5,30× absoluto) contra 5,83× de `main`. La evidencia `engram/evidence/T-094_load.txt` declara que con fx40k el cociente «no aplica»; esa exención no está ratificada. |
| 2 | Export XML con cues/beatgrid idénticos (test de round-trip) | Especificado | Cumple | Test `tests/test_t094_load.py:33-41` contra fixtures generados con `main`. Prueba independiente (`p5.py`): cargo `rekordbox_xml.py` de `main` (`git show main:`) y el de rc2, exporto los mismos 13 XML (UTF-8, UTF-8 con BOM, UTF-16, CDATA, comentarios, PI, entidades, `&#10;`, atributos de 1,1 MB, pistas reparadas, de streaming, sin Location, duplicadas, `KeyType="1"`, nombres de NODE repetidos) completos y con una sola playlist: **0 diferencias byte a byte**. |
| 3 | Suite completa exit 0 | Especificado | **Me abstengo** | Por instrucción no corrí la suite completa. Sí corrí en serie (`-n 0`) los archivos del ticket: `test_t094_load.py` 18, `test_t094_arq.py` 10, `test_t094_arq_enc.py` 17, `test_t094_arq_export.py` 1 y `test_library_load_t094.py` 6: todos verdes. |
| D-a | TEC-17: ningún `exists()` de reparaciones en el hilo de UI | Deducido (plan CÓMO 5) | Cumple | `rekordbox_xml.py:197` se ejecuta en el worker (`library_load_worker.py:73-75`). `measure.py` intercepta `Path.exists` con 2.000 reparaciones: en el hilo de UI solo aparecen 2 llamadas, y son de assets de tema (`qss/app.qss` y `tick-*.png`), no de pistas. |
| D-b | Errores de apertura claros, sin stacktrace (CLAUDE.md) | Deducido | Cumple | `rekordbox_xml.py:382-385`, `:395-396`, `:444-448`; `library_load_worker.py:55-63`; export `ui.py:2394-2401`. |
| D-c | QThread solo por señales; cancelación sin crash (ADR-006 §3) | Deducido | Cumple | `ui.py:1268-1276` (generación + `disconnect` + `requestInterruption`), descarte por token en `ui.py:1279` y `:1305`, `closeEvent` en `ui.py:2122`. |
| D-d | Recarga conserva las playlists marcadas (plan CÓMO 4: «`_reload_after_path_change` restaura las marcas en el callback de `loaded`») | Especificado en el plan aprobado; regresión respecto de `main` | **No cumple** si la recarga llega durante otra carga (defecto 1) | `ui.py:1235` y `ui.py:1239` |

Criterios con cita: 7 de 8 (el 3 queda en abstención).

## §Pase hostil

1. **Ventana de bytes y corte del TRACK** (`rekordbox_xml.py:274-285`, `:333-342`): `p1.py` compara cada `t.element` contra el TRACK que da `ET.parse` del documento entero. Con fuzz de 6 documentos de 59 pistas (atributos de 70 KB y 1,6 MB, multibyte de 2 y 4 bytes, `&lt;`/`&gt;`/`&#10;`, comillas mezcladas, CDATA con `<TRACK>` adentro, comentarios y PI con `<`, `</TRACK  >`, `/>` dentro de un valor), más BOM, UTF-16 y Latin-1, hubo **0 diferencias**. Con TRACK que empiezan o terminan a ±3 bytes del límite de 1 MiB, también 0. Con `_CHUNK` entre 1 y 257 y `_MARGIN` entre 0 y 16 (`p2.py`, 108 casos), 0 fallos. Un `<` crudo dentro de un atributo no es XML válido: expat lo rechaza y el usuario ve el error amigable.
2. **Sin `SetReparseDeferralEnabled`** (`rekordbox_xml.py:371-372`). Lo simulé envolviendo el parser para que el atributo no exista, así que la postergación queda activa. Con bloques reales de 1 MiB y etiquetas de 1,1 MB: 0 fallos (`p3.py`). Con bloques de 1 byte, 104 de 108 casos fallan, pero con el `RuntimeError` amigable de la guarda de `:335-337`: nunca exporta un `raw` corrupto en silencio. El intérprete que se distribuye (3.14) tiene el método.
3. **`encoding` declarada** (`rekordbox_xml.py:238-271`): `zlib_codec`, `zlib`, `bz2_codec`, `base64`, `rot13`, `hex`, `uu`, `quopri`, `utf-7`, `idna`, `punycode`, `unicode_escape`, `undefined`, `mbcs` y un nombre inexistente dan el error amigable en 0,00 s, sin crecimiento de RSS: zlib no se descomprime aunque le puse 200 MB comprimidos. Los alias (`UTF-8`, `utf_8`, `U8`, `latin1`, `windows-1252`, `MacRoman`, `SJIS`, `euc-jp`) cargan. BOM UTF-16/32, UTF-16BE sin BOM y BOM UTF-16 con una declaración que dice UTF-8 también cargan. Bytes inválidos en UTF-8 y Shift_JIS, UTF-16 con un byte de menos, binario, archivo vacío, solo BOM y un directorio: todos dan `RuntimeError` amigable (`p4.py`).
4. **Reparseo al exportar** (`rekordbox_xml.py:49-50`): las entidades del DTD interno y los prefijos de namespace cargan, pero `t.element` lanza `ET.ParseError`. La UI lo atrapa (`ui.py:2394-2401`) y lo cubre `tests/test_t094_arq_export.py:21`. Es el invariante (b) de ADR-006: el export cambia respecto de `main`, pero el cambio está aceptado. Billion laughs y XXE se cortan en la carga con un error amigable.
5. **Cancelación** (`cancel.py`, exit 0 en todos los casos, sin «Destroyed while thread» y sin abort en stderr): 15 Ctrl+R seguidos durante la carga terminan con 200 tarjetas, 0 hilos vivos y el worker en `None`. Cambiar Rekordbox → Traktor → Rekordbox → Traktor a mitad de la carga deja el estado de Traktor correcto, y volver da 200 tarjetas. Cerrar a 0,2, 2 y 6 s de empezada la carga tarda 0,03 s y no deja hilos corriendo. Riesgo heredado, no verificado: un `exists()` colgado en red supera el `wait(2000)` (`ui.py:2136-2139`); ya estaba aceptado en T-088.
6. **Responsividad**: durante la carga, el mayor hueco del event loop es de 421-482 ms y cae en el último tick (`_populate_playlists` con 200 tarjetas en el hilo de UI, `ui.py:1287`), no en el parseo.
7. **Traktor** (`traktor_db.py`, `_scan`): `iterparse` hace `clear()` de ENTRY y de COLLECTION, y la cancelación se consulta cada 2048 eventos. Un `OSError` de `iterparse` no está en el `except ET.ParseError`, pero el catch-all del worker lo convierte en mensaje (`library_load_worker.py:59-63`). Traktor no tenía requisito de medición y no lo medí.

## §Supuestos marcados

- **A1 (al Orquestador/PO):** el criterio 1b («XML de 40k pistas … RSS ≤ 3×») no dice qué XML. Con 40k pistas con cues (≈134-169 MB, el caso de SEC-09/TEC-05) se cumple con holgura. Con 40k pistas sin cues (12-22 MB) no se cumple ni medido como delta de `open_library` (4,6×) ni como proceso (10×), aunque sigue por debajo de `main`. La exención «no aplica» de la evidencia es una interpretación propia. Hace falta que el PO la ratifique; no la cuento como defecto.
- **A2:** los tiempos son en offscreen e Intel. No medí la plataforma Cocoa real ni Windows. Hubo una corrida de 1,445 s, con apenas 55 ms de margen contra la cota.

## §Veredicto

**REFUTADO.**

1. **Una segunda recarga durante una carga en curso pierde las playlists marcadas** (`ui.py:1235` y `ui.py:1239`). Mientras hay carga, `_all_cards` está vacío (`_load_playlists` → `_clear_playlist_area`, `ui.py:1251`), así que `keep` da `set()` y pisa el `_keep_after_load` pendiente. Lo reproduje así: marcar 3 playlists, Ctrl+R (se conservan) y después Ctrl+R dos veces con 0,4 s de diferencia. Resultado: `checked after double reload []` (`cancel.py keep_marks`, fx40k). En `main` la recarga era síncrona y siempre volvía a marcar (`git show main:ui.py`, l.1198-1209). Viola el plan CÓMO 4 (`engram/plans/T-094.md`): el código lo cumple para una sola recarga y lo rompe para recargas encadenadas. También pasa con Ctrl+R repetido, con elegir otra ruta en Configuración durante la carga (`ui.py:1199-1225`) y con una reparación que termina mientras se carga. El único test (`tests/test_library_load_t094.py:69-76`) no cubre el caso. Para confirmar la causa raíz, muté la línea 1239 a `keep if self._load_worker is None else (keep | self._keep_after_load)`: las marcas sobreviven (`['Playlist 3','Playlist 4','Playlist 5']`). Después la revertí.

Abstenciones: criterio 3 (suite completa, no corrida por instrucción). Supuestos para el PO: A1 y A2.

## Verificación 2 (2026-10-16)

Árbol juzgado: `release/1.0.0-rc2` @ f895c84 (worktree aislado y descartable; incluye el fix fece472). No leí `engram/qa/T-094.md` ni los handoffs ni la narrativa del implementador. Criterios: `engram/03_backlog.md:72` (texto ratificado: RSS sobre XML con cues) y `engram/plans/T-094.md:19` (CÓMO 4). Intérprete `.venv/bin/python`, Intel, `QT_QPA_PLATFORM=offscreen`. Sondas en `/private/tmp/claude-501/-Users-gabrielsk-Desktop-REKORDBOX-EXTRACTOR/b4fcb7d1-4284-4b55-9f7a-dc9bfcfaff16/scratchpad/vprobe2/k.py` (escenarios) más `vprobe/measure.py` de la verificación 1. La única mutación fue en `ui.py:1236-1238` y la revertí con `git checkout ui.py` (árbol limpio).

Diff del fix (`git show fece472`): `ui.py:1236-1238` agrega `if self._load_worker is not None: keep |= self._keep_after_load`. Suma 3 tests en `tests/test_library_load_t094.py`: recargas encadenadas, cambio de ruta en vuelo y cambio de fuente en vuelo. Desde 7d10c38, el resto del código que cambió es de T-095 (`ui.py:1628`, `:1676-1677`, `worker.py`, `audio_player.py`) y no toca la carga.

### §Criterios

| # | Criterio | Veredicto | Cita / evidencia |
|---|---|---|---|
| 1a | Ventana visible ≤ 1,5 s con 40k pistas | Cumple, con poco margen | `measure.py` sobre `fx40k_cues.xml` (133,9 MB): 1,231 / 1,249 / 1,465 s desde el constructor. La última corrida deja 35 ms de margen (ver supuesto A2 de la verificación 1). |
| 1b | RSS ≤ 3× sobre un XML con cues/beatgrid (ratificado) | Cumple | Pico de RSS de 341,8-347,3 MB contra 133,9 MB = **2,55-2,59×** (las mismas 3 corridas). El caso sin cues (4,6×) queda como nota, según la ratificación de `03_backlog.md:72`. Cierra A1. |
| 2 | Export con cues/beatgrid idénticos (round-trip) | Cumple | `tests/test_t094_load.py:33` (18 tests verdes con `-n 0`) y `tests/test_t094_arq_export.py` (1 verde). El fix no toca `rekordbox_xml.py`. El byte a byte de la verificación 1 (`p5.py`, 13 XML) sigue valiendo porque `rekordbox_xml.py` no cambió desde 7d10c38. |
| 3 | Suite completa exit 0 | **Me abstengo** | No la corrí por instrucción (hay otro agente en paralelo). `tests/test_library_load_t094.py` con `-n 0` da 9/9 verdes. |
| CÓMO 4 | La recarga y el cambio de fuente cancelan y relanzan; las marcas se restauran en `loaded` | Cumple | Cancelar y relanzar: `ui.py:1253` y `:1270-1279`. La recarga acumula las marcas pendientes mientras hay un worker (`ui.py:1236-1238`, `:1242`). La restauración y el consumo en `loaded` están en `ui.py:1299-1304`. El cambio de fuente descarta: `ui.py:826`. Las claves llevan la fuente como prefijo (`ui.py:1658-1664`). |

Criterios con cita: 4 de 5 (el 3 queda en abstención).

### §Pase hostil (`k.py`, fx40k: 3 playlists marcadas, Playlist 3/4/5; exit 0 en todos)

1. **Sonda de la verificación 1** (2 Ctrl+R separados por 0,4 s): `['Playlist 3','Playlist 4','Playlist 5']`. Antes daba `[]`.
2. **3 Ctrl+R** separados por 0,2 y 0,3 s: se conservan las 3. **Dos rondas de doble Ctrl+R** seguidas: se conservan.
3. **Cambio de ruta a mitad de la carga** (Ctrl+R y, a los 0,3 s, `_reload_after_path_change`): se conservan.
4. **Recarga, cambio a Traktor y recarga en vuelo**: en Traktor quedan `[]` marcadas y `_keep_after_load == set()`. Al volver a Rekordbox y recargar: `[]`. Las marcas de Rekordbox no se filtran a Traktor ni vuelven solas. Es lo mismo que hace `main` y lo fija el test nuevo. Además, la clave con prefijo de fuente (`ui.py:1664`) impide un cruce aunque quedara algo pendiente.
5. **Carga fallida y después una recarga exitosa** (ruta inexistente a mitad de la carga, luego la ruta buena): al fallar queda `pending set()` (`ui.py:1311`) y después `[]`. Se pierden las marcas. Es igual que en `main`: en `git show main:ui.py` l.1198-1209 la clave se calcula de las tarjetas, y tras un fallo no hay tarjetas. No es una regresión ni viola un criterio. Lo dejo como **Deducido N1 para el PO**: el usuario que se equivoca de XML a mitad de una recarga y lo corrige pierde la selección.
6. **La playlist marcada ya no existe en el XML nuevo** (`tiny.xml`, 1 playlist «P»): 1 tarjeta, ninguna marcada y `pending set()`. No queda nada colgado. Al volver al XML original: `[]`. La selección no se resucita, igual que en `main`.
7. **Sin resurrección de desmarcas**: con la carga terminada desmarco Playlist 4 y hago Ctrl+R ×2: queda `['Playlist 3','Playlist 5']`. El pendiente se consume en `ui.py:1299`, así que una selección vieja no vuelve a entrar.
8. **Cerrar la ventana con la carga en vuelo** tras 2 Ctrl+R: cierra en 0,00 s, sin hilos corriendo y sin crash. Las líneas de stderr que no son `qt.*` no muestran errores. `_keep_after_load` queda con las 3 claves, pero no tiene consumidor: `_cancel_library_load` (`ui.py:2125`) sube la generación y desconecta. Es inofensivo.
9. **Mutación**: dejé `ui.py:1238` sin efecto. Fallan `test_checked_playlists_survive_chained_reloads_before_the_first_one_shows_cards` y `test_checked_playlists_survive_a_path_change_in_the_middle_of_a_reload`, y la sonda vuelve a dar `x2 False []`. Los tests nuevos sí discriminan. Revertida.
10. **Invariante del guard**: `_load_worker is not None` implica que no hay tarjetas, porque `_load_playlists` llama a `_clear_playlist_area` (`ui.py:1254`, `:1375`). Además, `_on_library_loaded` pone el worker en `None` antes de poblar (`ui.py:1284`). No encontré un estado en el que haya worker vivo y tarjetas marcadas a la vez.

### §Veredicto

**CONFIRMADO.** El defecto 1 de la verificación 1 está cerrado (`ui.py:1236-1238`, evidencia en los puntos 1-3 y 9). No encontré defectos nuevos. Abstención: criterio 3 (suite completa). Nota para el PO: N1 (Deducido, igual que en `main`). A2 (offscreen/Intel) sigue abierto: una corrida dio 1,465 s.
