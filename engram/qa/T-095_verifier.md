# T-095 — Verificación ciega (nerv-verifier, nivel S)

Fecha: 2026-10-15 · Árbol juzgado: `release/1.0.0-rc2` @ 5c3d4fe (worktree aislado, rama integrada con T-093/T-094) · Diff de referencia: `git diff main...feat/t095-robustez`.
No se leyó `engram/qa/T-095.md` ni handoffs. Fuentes de criterios: `engram/03_backlog.md:73` (fila T-095), tabla de deuda `engram/03_backlog.md:158-165`, `engram/plans/T-095.md` §QUÉ 1-10.
Evidencia de ejecución: `pytest -n 0 tests/test_robustez_t095.py tests/test_thread_lifecycle.py` → 18 passed. Sondas hostiles en `/private/tmp/claude-501/-Users-gabrielsk-Desktop-REKORDBOX-EXTRACTOR/b4fcb7d1-4284-4b55-9f7a-dc9bfcfaff16/scratchpad/verifier_probe_T095.py` (corridas en el worktree con `run_isolated`, luego retiradas).

## §Criterios

| # | Criterio | Tipo | Veredicto | Cita |
|---|---|---|---|---|
| 1 | TEC-08 `_estimate_size` descuenta lo completo en destino con `_is_complete_copy` | Especificado (plan QUÉ 1) | Cumple | `worker.py:438-456` (salta si `_is_complete_copy(_planned_dest(...))`, l.450); nombres por `_planned_dest` l.420-424, el mismo que usa el loop l.306; test `tests/test_robustez_t095.py:23` |
| 2 | TEC-09 `setMaximumBlockCount(5000)` | Especificado (QUÉ 2) | Cumple | `ui.py:988`; test `tests/test_robustez_t095.py:38` |
| 3 | TEC-10 fallo de lectura: `_log.exception` + línea visible; no cachear vacío | Especificado (QUÉ 3) | Cumple | export: `worker.py:409-417`, `worker.py:199-200`, `worker.py:214`; preview: `ui.py:1715`, `ui.py:1742-1747`, `ui.py:2344`; tests `tests/test_robustez_t095.py:49`, `:61` |
| 4 | D-16 `closeEvent` espera la copia sin tope duro, cursor de espera + aviso | Especificado (QUÉ 4) | Cumple | `ui.py:2123-2124`, `ui.py:2177-2189` (`while not worker.wait(50)` l.2185, `setOverrideCursor`, texto «Esperando…»); test `tests/test_robustez_t095.py:80` (bloque de 7 s > viejo tope) |
| 5 | D-17 la vista previa muestra el nombre de carpeta real (`_unique_folder_names`) | Especificado (QUÉ 5) | **No cumple en un caso** (defecto 1) | `ui.py:1663-1673`, `ui.py:1625` vs `worker.py:213-222` |
| 6 | D-18 `_remove_orphan_parts` solo borra `.part` de archivos que este export escribe | Especificado (QUÉ 6) | Cumple | `worker.py:175-185`, `worker.py:271`, `worker.py:427-435`; test `tests/test_robustez_t095.py:132` |
| 7 | D-20/D-21(backlog) `WaveformWorker` sale al instante ante error del decoder y ante `cancel()` | Especificado (QUÉ 7) | Cumple | `waveform_worker.py:134-153` (`decoder.error.connect` l.142; timer de `_stop` l.146; `if not failed` l.150). Señal verificada en PySide6 6.12.0: `QAudioDecoder` expone `error` (comando `dir(QAudioDecoder)` → `['Error','error','errorString']`); tests `tests/test_robustez_t095.py:152`, `:167` |
| 8 | D-21/D-22(backlog) `playing_changed` solo emite cambios reales | Especificado (QUÉ 8) | **Cumple el caso pedido, introduce regresión** (defecto 2) | `audio_player.py:37-38`, `:48-60`, `:98-105` |
| 9 | D-22/D-23(backlog) `_pump_render_queue` tolera layout destruido | Especificado (QUÉ 9) | Cumple | `ui.py:1772-1775`; test `tests/test_robustez_t095.py:207` |
| 10 | TEC-18 re-chequeo de existencia al recuperar foco (>5 s, throttling) | Especificado (QUÉ 10) | Cumple | `ui.py:2143-2175`, `preview_worker.py:63-90`; tests `tests/test_robustez_t095.py:247`, `:259` |
| D1 | Regla CLAUDE.md: `ExportWorker` no toca widgets desde `run()` | Deducido | Cumple | `worker.py:199-200` emite `self.log` (señal), no widget |
| D2 | Regla CLAUDE.md: `total_songs` fijo antes del loop | Deducido | Cumple | `worker.py:216-219` (ordenar no cambia longitud: `db.py:22-24`) |
| D3 | Cada ítem con test (backlog col. criterios «1) Cada ítem con test») | Especificado (backlog l.73) | Cumple | 13 tests en `tests/test_robustez_t095.py` cubren los 10 ítems |

Criterios con cita: 13/13. Abstenciones: ninguna sobre criterios.

## §Pase hostil

1. **`.part` ajenos (D-18):** solo se borran nombres `<_planned_dest>.part` (`worker.py:427-435`); `descarga.part`/`otra.mp3.part` sobreviven (test l.132). Hallazgo lateral (no viola QUÉ 6, que define «propios» como los de esta corrida): un `.part` propio de una corrida anterior con otra numeración queda para siempre — sonda P5: `['1 - A - T1.mp3', '1 - A - T2.mp3.part', '2 - A - T2.mp3']`. Al PO como Deducido, no defecto.
2. **Archivo truncado en destino (TEC-08):** sonda P2: dest truncado a 400 KB → `_estimate_size` = 1 000 000 (cuenta el origen entero, correcto: el `.part` convive con el truncado hasta `os.replace`, `worker.py:161-166`); con 900 KB libres el export aborta con «Espacio insuficiente». No roto.
3. **Playlist ilegible cacheada vacía (TEC-10):** no se cachea (`ui.py:1746`); test l.61 verifica caché vacío. No roto. Ver defecto 1 para su interacción con D-17.
4. **Cierre con copia en curso (D-16):** espera sin tope con `processEvents(ExcludeUserInputEvents)` (`ui.py:2185-2186`); `_on_finished` (`ui.py:2284-2328`) no abre modales, así que no hay bloqueo reentrante. Riesgo residual (no defecto, el plan pide «sin tope»): `_part_names` (`worker.py:427`) y `_estimate_size` recorren todas las pistas con `resolve_path` sin mirar `isInterruptionRequested`, así que en un disco lento el cierre espera también esa pasada.
5. **Onda con archivo corrupto y cierre inmediato (D-20):** error síncrono dentro de `start()` cubierto por `failed` (`waveform_worker.py:136-140,150`); cancel cubierto por el timer (l.144-147). Tests l.152/l.167 verdes. No roto.
6. **Parpadeo de `playing_changed` (D-21):** el arranque y el cambio entre pistas buenas emiten `[True, False]` (test l.182). **Roto en el cambio hacia un archivo que no abre** → defecto 2.
7. **Homónimas en vista previa vs export real (D-17):** **roto** cuando una homónima anterior no se puede leer → defecto 1.
8. **Re-chequeo con disco desconectado (TEC-18):** sonda P4: 2 pistas OK, se borra la carpeta, foco tras >5 s → `_broken_total` 0 → 2. No roto. Observación: el re-render (`ui.py:2170-2175` → `_clear_preview_layout`) pierde scroll/expansión; sin criterio que lo prohíba.

## §Veredicto: REFUTADO

1. **D-17 — la vista previa muestra un nombre de carpeta que el export no crea.** `ui.py:1663-1673` calcula `_unique_folder_names` sobre TODAS las tarjetas marcadas, pero el export lo calcula solo sobre las playlists que devolvieron pistas (`worker.py:213-216` filtra `if songs:` y luego `worker.py:222`). Si una homónima anterior es ilegible (TEC-10) o devuelve 0 pistas pese a tener conteo > 0, la previa y el export divergen. Sonda P1 (Rota «Mix» ilegible + «Mix» legible): previa `['01 Mix', '02 Mix (2)']`, export crea `['Mix']`. Viola plan QUÉ 5 («muestra el nombre de carpeta real») y la deuda D-17 (`engram/03_backlog.md:159`).
2. **D-21 — regresión: tras un archivo que no abre, la UI no se entera de que vuelve a sonar.** `audio_player.py:100-101` suprime el `False` durante `play()` y `_last_playing` (l.102-103) queda en `True` aunque el reproductor terminó en `StoppedState`. `ui._on_audio_error` pone `_is_playing = False` (`ui.py:2061-2064`); al reproducir la pista siguiente el estado pasa a `Playing`, igual a `_last_playing`, y no se emite nada. Sonda P3 (AudioPlayer): rama `[True]` vs main `[True, False]` y luego main emite `True` y la rama no emite nada. Sonda P6 (ventana real): rama `_is_playing=False`, glifo `note` con `PlayingState`; con `main:audio_player.py` en el mismo árbol: `True`, `pause`. Viola plan QUÉ 8 (debe emitir los cambios reales) y la regla del backlog «Cada ítem con test» no cubre el camino de error (`tests/test_robustez_t095.py:182` solo prueba archivos válidos).

Suposiciones marcadas: ninguna afirmación de esta verificación queda sin cita o sin comando. El comportamiento de Rekordbox/Traktor real no se probó (solo dobles `rekordbox_xml.RbxPlaylist`/`RbxTrack`).

## Verificación 2 (2026-10-16)

Árbol juzgado: `release/1.0.0-rc2` @ 0a1ef77 (worktree aislado `scratchpad/ver-T-095b`, ya retirado). Fix bajo examen: `bfa3147` (V1/D-17) y `23c9dbf` (V2/D-21). No se leyó `engram/qa/T-095.md` ni handoffs.
Evidencia de ejecución: `pytest -n 0 tests/test_robustez_t095.py tests/test_thread_lifecycle.py` → 21 passed. Sondas (vía `run_isolated`, subproceso Qt) en `scratchpad/probes/v1.py`, `v2.py`, `perf.py`. Mutaciones revertidas (`git status` limpio al final).

### §Criterios

| # | Criterio | Veredicto | Cita |
|---|---|---|---|
| 1 | TEC-08 estimación descuenta lo completo en destino | Cumple | `worker.py:454-466` (`_is_complete_copy(_planned_dest(...))` l.466); test `tests/test_robustez_t095.py:23` |
| 2 | TEC-09 `setMaximumBlockCount(5000)` | Cumple | `ui.py:988`; test `tests/test_robustez_t095.py:38` |
| 3 | TEC-10 fallo de lectura logueado + visible, sin cachear vacío | Cumple | export `worker.py:198-200`, `worker.py:213-216`, `worker.py:425-433`; previa `ui.py:1741-1747`, `ui.py:2344`; tests `:49`, `:61` |
| 4 | D-16 cierre espera sin tope con cursor + aviso | Cumple | `ui.py:2177-2189` (`while not worker.wait(50)` l.2185, `setOverrideCursor` l.2183); test `:80` |
| 5 | D-17 previa muestra el nombre real de carpeta | **Cumple (V1 resuelto)** | Regla única: `worker.py:395-401` (`_folder_names_for_readable`, solo playlists con pistas) usada por el export `worker.py:222` y por la previa vía `worker.py:404-408` → `ui.py:1669-1674`, aplicada en `ui.py:1663-1667` y `ui.py:1621-1625`; test `tests/test_robustez_t095.py:130` (rojo con la mutación que hace consumir nombre a las vacías) |
| 6 | D-18 solo borra `.part` propios | Cumple | `worker.py:175-185`, `worker.py:271`, `worker.py:443`; test `:160` |
| 7 | D-20 `WaveformWorker` sale ante error del decoder / cancel | Cumple | `waveform_worker.py:136-150`; tests `:180`, `:195` |
| 8 | D-21 `playing_changed` solo cambios reales | **Cumple (V2 resuelto)** | `audio_player.py:98-104` (sin rebote al cambiar de pista) + `audio_player.py:106-112` (error resetea `_last_playing` y emite `False` solo si estaba en `True`); tests `:210`, `:233`, `:259` (los dos últimos rojos con la mutación `if self._last_playing:`→`if False:`) |
| 9 | D-22 `_pump_render_queue` tolera layout destruido | Cumple | `ui.py:1768-1775` (`isValid(self.preview_layout)`); test `:289` |
| 10 | TEC-18 re-chequeo al recuperar foco (>5 s, throttling) | Cumple | `ui.py:2143-2175` (`_RECHECK_EVERY_S` l.2143, throttle l.2154); tests `:329`, `:341` |
| D1 | `ExportWorker.run()` no toca widgets | Cumple | `worker.py:198-200` emite señal `log` |
| D2 | `total_songs` fijo antes del loop | Cumple | `worker.py:218-219`, calculado antes del chequeo de espacio y del loop |
| D3 | Cada ítem con test (backlog l.73) | Cumple | tests citados en cada fila |

Criterios con cita: 13/13. Abstenciones sobre criterios: ninguna.

### §Pase hostil

1. **V1 sonda original** («Mix» ilegible + «Mix» legible): títulos de previa `['01 Mix', '02 Mix']`, export crea `['Mix']`. La legible se nombra «Mix» en ambos. Resuelto.
2. **V1, dos ilegibles homónimas + una legible:** previa `['01 Mix', '02 Mix', '03 Mix']`, export `['Mix']`. La legible = «Mix». Resuelto.
3. **V1, playlist vacía (0 pistas) + homónima legible:** previa `['01 Mix', '02 Mix']`, export `['Mix']`. Resuelto (`worker.py:406` filtra `if songs`).
4. **V1, mezcla y casefold:** `[Mix, Rota Mix, mix]` → previa `03 mix (2)`, export `['Mix', 'mix (2)']`; `[Mix, vacía Mix, Mix, «Mix (2)»]` → previa `Mix`, `Mix (2)`, `Mix (2) (2)` = export. Al destildar/volver a tildar la primera (camino incremental `ui.py:1614-1635`) los nombres se recalculan bien (`02 mix` → `03 mix (2)`). Sin regresión.
5. **V2 sonda original** (válido → roto → válido): `playing_changed` `[True, False, True]`, `is_playing()` True; en ventana real el test `:259` da glifo `pause`. Resuelto.
6. **V2 variantes:** roto primero → válido: `[True]`. Roto → roto → válido: `[True, False, True]` (el segundo error no reemite, `_last_playing` ya False). Stop → roto → válido: `[True, False, True]` (el error no emite un `False` duplicado). Roto e inmediatamente válido sin bombear eventos: `[True]`, sin error (la fuente cambió antes). Válido → válido → válido: `[True]`, **sin parpadeo** True/False/True.
7. **V2 error síncrono dentro de `play()`:** en 4 corridas `errorOccurred` llegó siempre fuera de `play()` (`_switching` False al recibirlo). El código no depende de `_switching` en `_on_error` (`audio_player.py:106-112`), así que un error síncrono seguiría reseteando. Me abstengo de afirmar empíricamente que el backend FFmpeg nunca lo emite síncrono.
8. **V2 error en mitad de reproducción:** no logré provocarlo con un archivo real (truncar el wav mientras suena no produjo error, FFmpeg ya tenía el buffer). Con error inyectado (`_on_error(ResourceError)`) mientras el player sigue en `PlayingState`: `[True, False]`, y luego pausa/reanuda → `True`. Coherente. Me abstengo sobre el comportamiento real del backend en ese caso.
9. **Presupuesto T-089** (click 10 con 10×200 ≤ 1 s, `engram/03_backlog.md:68`): `_start_preview_worker` en el click 10 = 0,006 s (Rekordbox, `RbxPlaylist`) y 0,019 s (Traktor, `TraktorPlaylist`); `folder_names_by_playlist` sobre 10×200 = 0,3 ms / 6,2 ms. La lectura extra en el hilo de UI no rompe el presupuesto.
10. **Observaciones al PO (Deducidas, no defectos; ningún criterio las cubre):** (a) una playlist ilegible o vacía conserva en la previa su tarjeta con el nombre crudo (`ui.py:1625`, `ui.py:1667` `folders.get(..., g.name)`), así que el usuario ve dos tarjetas «Mix» aunque el export cree una sola carpeta; (b) `folder_names_by_playlist` llama `_get_songs_list` sin `on_error` (`worker.py:406`), que registra `_log.exception("Export: no se pudo leer…")` (`worker.py:430`) en cada toggle de la previa: ruido en el log con la etiqueta «Export» aunque nadie exporte; (c) las notas no contadas de la verificación 1 (`.part` huérfano de otra numeración, pre-loop no interrumpible, TEC-18 pierde scroll) siguen igual.

### §Veredicto: CONFIRMADO

Sin defectos. V1 (D-17) y V2 (D-21) resueltos con tests que discriminan (mutación de cada fix → rojo). Sin regresión en el cambio entre pistas válidas ni en el presupuesto de T-089. Suposiciones marcadas: ninguna afirmación sobre correctitud queda sin cita o sin comando; abstenciones solo sobre el comportamiento empírico del backend FFmpeg (error síncrono y error en mitad de reproducción, puntos 7-8), cubiertos por lectura de código.
