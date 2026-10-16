# T-094 — return handoff (nerv-desktop, 2026-10-15, transcripto tal cual)

> Índice P-1 (agregado por nerv-orquestador para nerv-gate; el texto de abajo es el original sin cambios):
> status: ver primer párrafo (listo para QA, sin merge ni push) · files touched (del diff real main..rama): CLAUDE.md, engram/evidence/T-094_load.txt, engram/plans/T-094.md, library_load_worker.py, load_cancel.py, rekordbox_xml.py, tests/_window_boot.py, tests/data/t094_roundtrip_all.xml, tests/data/t094_roundtrip_in.xml, tests/data/t094_roundtrip_one.xml, tests/test_library_load_t094.py, tests/test_t094_load.py, traktor_db.py, ui.py · risks: ver «No verificado» / «Riesgos» / «Diferencias» del texto · how to test: suite completa (`pytest -q`) más los tests nuevos y la evidencia que nombra el texto.

T-094 listo para QA. Estado: En revisión QA, no Done. Sin merge ni push. Suite completa exit 0 (corrida 2 veces).

**Rama:** `feat/t094-carga-worker`, 7 commits (el último es `5f3f6e5`) con `Co-Authored-By: Claude Fable 5.1`. Plan en `engram/plans/T-094.md`. La fila T-094 no existe en `engram/03_backlog.md` (grep sin resultados), así que no la actualicé. Faltan también la corrida de `bin/nerv-index.sh` (P-22) y la verificación del stamp de P-19.

**Diseño cues/beatgrid: opción A, pero con texto crudo en vez de elementos.** Primero implementé `iterparse`. Medí que solo el `iterparse` ya tardaba 13,7 s en 169 MB, contra 10 s de `ET.parse`. Re-serializar los hijos a mano sumaba otros 8 s. Quedó expat directo: por cada `<TRACK>` de COLLECTION guardo 5 strings más el texto crudo del elemento, cortado con `CurrentByteIndex`. `RbxTrack.element` es ahora una propiedad que hace `ET.fromstring(raw)`. El round-trip es idéntico por construcción, porque es el mismo texto que antes parseaba `ET.parse`.
Descarté la opción B (releer el XML al exportar): el archivo puede cambiar o desaparecer entre la carga y el export, y obliga a un segundo parseo enorme. Maneja UTF-8, UTF-16 y Latin-1, y TRACKs partidos entre bloques de lectura.

**Cambios por ítem:**
- **SEC-09:** `open_library` (rekordbox_xml.py) y `open_collection` (traktor_db.py, con `iterparse`) ya no retienen el DOM. Los guards de samefile/tmp de `write_playlists_xml` no se tocaron. Agregué `load_cancel.py` con `should_cancel` y `LoadCancelled`.
- **Round-trip:** `tests/data/t094_roundtrip_{in,all,one}.xml`; los esperados los generé con el código de main antes de tocarlo. Comparación byte a byte, pasa antes y después.
- **TEC-05:** nuevo `library_load_worker.py` (`LibraryLoadWorker`, señales `loaded(result)` / `failed(token, msg)`). La UI muestra «Cargando librería…». Recargar y cambiar de fuente cancelan la carga vigente y descartan lo ya encolado por generación. `_retain_thread` y `closeEvent` cubren el hilo.
- **TEC-17:** `exists()` de las reparaciones corre en el worker. Test con spy sobre `Path.exists`, que verifica que ninguna llamada sale del hilo de UI.

**Números** (detalle en `engram/evidence/T-094_load.txt`, Intel i7-9750H, una corrida por celda):

| Caso | Ventana visible | Carga total | RSS pico |
|---|---|---|---|
| 12 MB / 40k pistas, antes | 2823 ms | 2823 ms | 237 MB |
| 12 MB / 40k pistas, después | 1314 ms | 3066 ms | 219 MB |
| 169 MB, antes | 12250 ms | 12250 ms | 1393 MB (8,3x) |
| 169 MB, después | 1262 ms | 11121 ms | 402 MB (2,4x) |

- `open_library` solo, 308 MB: RSS +2317 MB antes, +498 MB después (1,6x el XML). Cumple ≤ 3x.
- «Ventana visible» después es el costo de construir la ventana; antes incluía la carga entera y la UI no respondía.
- La carga total no mejora: con el XML de 169 MB parsear sigue costando lo mismo, solo que ahora no bloquea.
- Los fixtures los generé yo (los de la auditoría no estaban en el scratchpad): 12 MB, 169 MB y 308 MB.

**Archivos tocados:**
- ui.py (rangos aproximados, base 4922586, `git diff 4922586 -U0 -- ui.py` da los hunks exactos). Para el merge con T-095 (log y preview) los puntos de conflicto probables son:
  - ~84 (import)
  - ~227 (estado nuevo en `__init__`)
  - ~772 (`_repair_supported`)
  - ~814 (`_switch_source`)
  - ~1206-1270 (`_reload_after_path_change`, `_load_playlists`, `_cancel_library_load`, `_on_library_loaded`, `_on_library_failed`)
  - ~1362-1392 (`_show_not_installed`, `_show_loading`, `_show_status_card`)
  - ~2067 (`closeEvent`)
  - No toqué el log ni el preview.
- Resto: rekordbox_xml.py, traktor_db.py, library_load_worker.py, load_cancel.py, CLAUDE.md (2 líneas de arquitectura), tests/_window_boot.py, tests/test_t094_load.py, tests/test_library_load_t094.py.
- Seam de tests: BOOT define `load_async` (la carga asíncrona tal cual) y `settle(w)`. `_load_playlists_real` ahora espera a que termine, así los tests existentes no cambiaron.

**No verificado / caveats:**
- Traktor con un NML grande: solo verificado por test que COLLECTION no queda en memoria; no medí tiempo ni RSS.
- Discos de red reales: solo simulé la latencia con `sleep`.
- Windows: sin probar.
- `main.py` no cambió. El worker arranca dentro de `MainWindow.__init__` y la ventana se muestra al volver el constructor (milisegundos), en vez de diferir la carga con un timer. Si el PO quiere el orden literal «show y después cargar», es un `QTimer.singleShot(0, ...)`.
- `closeEvent` espera a los hilos retenidos hasta 2 s. Si el worker queda bloqueado en un `exists()` de red colgada, Qt puede abortar al cerrar. Es el mismo riesgo que ya aceptó T-088 para `PreviewWorker`.
- Una carga con path de Rekordbox vacío falla en el worker y muestra la tarjeta de siempre; verificado por test.
- Un XML con raíz distinta de `DJ_PLAYLISTS` y además malformado ahora da el error «no es un XML de Rekordbox» en vez de «no se pudo leer». Es un cambio de mensaje menor.
- `_sync_rb_actions` llama a `self._fixes_store.count()`, que lee un JSON local chico en el hilo de UI. No es red, pero técnicamente es I/O en ese hilo.
