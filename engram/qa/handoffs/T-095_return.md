# T-095 — return handoff (nerv-desktop, 2026-10-15, transcripto tal cual)

> Índice P-1 (agregado por nerv-orquestador para nerv-gate; el texto de abajo es el original sin cambios):
> status: ver primer párrafo (listo para QA, sin merge ni push) · files touched (del diff real main..rama): audio_player.py, engram/plans/T-095.md, preview_worker.py, tests/test_robustez_t095.py, tests/test_thread_lifecycle.py, ui.py, waveform_worker.py, worker.py · risks: ver «No verificado» / «Riesgos» / «Diferencias» del texto · how to test: suite completa (`pytest -q`) más los tests nuevos y la evidencia que nombra el texto.

T-095: los 10 ítems están hechos y la suite completa da exit 0 (`pytest -q`, `-n 4`). No hice merge ni push.

**Rama:** `feat/t095-robustez`, desde main, en el worktree agent-abde5c9cffe1174ff. Un commit por ítem, con el Co-Authored-By de Fable 5.1.
**Plan:** `engram/plans/T-095.md`, con «Aprobado por el PO: 2026-10-15». No encontré la fila T-095 en `03_backlog.md`; trabajé con el texto del encargo.
**Commits:** plan, TEC-08, TEC-09, TEC-10, D-16, D-17, D-18, D-20 (waveform), D-21 (player), D-22, TEC-18, y un ajuste final.
**Tests:** nuevos en `tests/test_robustez_t095.py` (13), todos en subproceso. Los de D-16, D-18, D-20 y D-22 los vi rojos antes del código, y el de D-21 también. Los otros seis fallaban solo por el atributo o la clase que todavía no existía.
**Archivos fuera de ui.py:**
- `worker.py`: estimación de espacio con la regla «Ya existe», `.part` acotados, aviso de playlist ilegible, orden de pistas una sola vez.
- `waveform_worker.py`, `audio_player.py`, `preview_worker.py` (nuevo `ExistenceRecheckWorker`).
- `tests/test_thread_lifecycle.py`: sumé `playlist` al `FakeCard`, porque ahora ui.py lee `card.playlist.Name` al nombrar carpetas.

**ui.py, zonas tocadas** (por función, los rangos cambian con T-094):
- Imports (`logging`, `time`, `shiboken6.isValid`, `QEvent`/`QEventLoop`, `ExistenceRecheckWorker`, `_unique_folder_names`) y `__init__` (`_last_exists_check`, `_recheck_worker`).
- Creación de `log_view`: `setMaximumBlockCount(5000)`.
- `_sync_preview_cards`, `_start_preview_worker`, `_extract_preview_data` (solo el `except`) y helpers nuevos `_name_groups_like_folders` / `_folder_names_of`.
- `_pump_render_queue` (guarda con `isValid`), `_on_preview_done`.
- `closeEvent` + `_wait_export_block`, y `event()` + `_recheck_existence_on_focus` + `_on_recheck_done`.
- `_report_unreadable_playlist` junto a `_log`.
- No toqué `_load_playlists*`, `rekordbox_xml.py`, `sanitize` ni `_safe_filename`.

**Diferencias con el encargo:**
- D-20: `QAudioDecoder` no tiene `errorOccurred`, la señal se llama `error` (confirmado en Context7 y con `dir()`). Se emite dentro de `start()`, antes de `loop.exec()`, así que el código usa una bandera `failed`. Sumé un `QTimer` de 100 ms que corta el decode si `cancel()` se llama. Con un archivo corrupto el worker termina en menos de 2 s, antes quedaba 90 s.
- D-18: filtré por nombre (`<destino>.part` de las pistas del export) y no con prefijo nuevo, para no romper los tests T-088 existentes.
- D-16: `closeEvent` espera sin tope (cursor de espera y «Esperando que termine la copia…» en `output_status`). Si el disco está colgado de verdad, la app no cierra hasta que el usuario lo desconecte.
- TEC-10: el aviso de la vista previa va a `log_view` y a `output_status` (con estilo warn), porque el log está oculto fuera del export. Es una decisión mía de UX, revisala.
- D-21 (player): ignoro el `Stopped` que aparece mientras se cambia de pista.
- TEC-18: se comprueban todas las rutas dibujadas, no solo las filas visibles. Si algo cambió, se reconstruye la vista previa, así que se pierde la posición de scroll.
- La numeración D-xx del encargo difiere del backlog: mi D-20 es la D-21 del backlog (onda), mi D-21 es la D-22 (flicker), y mi D-22 no figura en la tabla.

**No verificado:**
- Windows (los tests corrieron solo en macOS; un disco USB real colgado no se probó).
- El test de D-16 tarda unos 8 s en total, por el bloque simulado de 7 s.
- El efecto visual del texto de `output_status` y del cursor de espera.
