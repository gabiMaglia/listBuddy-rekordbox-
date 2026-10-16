# T-105: verifier ciego (nivel X, P-11/P-12)

Juzgué la rama `feat/t105-export-cierre` en `87a17c3`, en un worktree detached aparte. Para comparar usé otro worktree detached de `main`.
Leí la fila T-105 de `engram/03_backlog.md`, el diff `main...feat/t105-export-cierre` y el código que toca (`worker.py`, `ui.py`, `preview_worker.py`, `audio_player.py`, `waveform_worker.py`, `audio_formats.py`, `library_load_worker.py`, `README.md`). No leí `engram/qa/T-105.md` ni el handoff de vuelta.
Hice las pruebas con `QT_QPA_PLATFORM=offscreen` y el venv del proyecto. Las de cierre arman una ventana real con `BOOT` (`tests/_window_boot.py`), apagan la app con `QTimer.singleShot(..., w.close)` + `app.exec()`, que es el mismo camino que `main.py`, y cada una corre en un proceso aparte. Revertí todas las mutaciones y `git status` quedó vacío.

## §Criterios

| # | Criterio | Estado | Cita / evidencia |
|---|---|---|---|
| 1 | 1.900 archivos: export con log ≤ 1,3× sin log; el log final tiene las mismas líneas | **CUMPLE** | Lotes en `worker.py:231-241` y flush antes de `finished_ok` en `worker.py:243-249`. La medí con la ventana real y `_start_export` → `idle`: 1.900 archivos de 64 KiB en 10 playlists, «sin log» = `w._log` no-op, 3 corridas. **Rama:** log 3,33 / 3,55 / 3,33 s contra sin log 3,41 / 3,03 / 2,98 s, o sea **0,98× / 1,17× / 1,12×** (media 1,09×). **main:** 5,93 / 6,35 / 5,92 contra 2,66 / 2,89 / 2,86, o sea ~2,1×. Comparé el texto final del `log_view` en main y en la rama con 400 pistas, 11 faltantes y la sección «Tracks no encontradas»: `diff` da idéntico (419 líneas). Mutación «flush siempre»: falla `test_log_lines_are_emitted_in_batches`. |
| 2 | `stat` bloqueado 5 s en PreviewWorker + cerrar → exit 0 sin «Destroyed while thread…» (test) | **CUMPLE (literal)** | `ui.py:2163` llama a `_exit_if_threads_hung` (`ui.py:2170-2193`), que sale con `os._exit(0)` (`:2193`) después de `settings.sync()` y `logging.shutdown()` (`:2191-2192`). Test: `tests/test_close_hung_t105.py:21-37`. Si muto `:2163` a `pass` fallan los 3 tests del archivo, y los 3 también fallan en main. **Pero cerrar no es robusto:** ver D1, D2, D4 y D5. |
| 3 | `.part` con fsync (mutación roja) | **CUMPLE** | `worker.py:170-171`: `flush()` + `os.fsync(fdst.fileno())` sobre el fd del `.part`, dentro del `with` y antes de `os.replace` (`:173`). Si `fsync` lanza, el `except BaseException` borra el `.part` y relanza (`:174-179`). La mutación `fsync → pass` deja en rojo `test_part_file_is_fsynced_before_it_replaces_the_final_name` (`tests/test_export_integrity.py:262-273`). |
| 4 | Hardlink en destino → no se pisa el inodo ajeno (test) | **CUMPLE** | `worker.py:254-270`: `lstat` y alterno si `S_ISLNK` o `st_nlink > 1`. Lo probé suelto: base vacía → base; base propia (nlink 1) → base; base hardlink y `(2)` symlink → `(3)`; con `(3)` directorio → `(4)`. Test `tests/test_export_integrity.py:276-288`. La mutación que saca `st_nlink <= 1` lo deja en rojo. |
| 5 | `.xyz` no entra a `setSource` (test) | **CUMPLE** | `audio_formats.py:11-19` con `suffix.lower()`, así que `.MP3` pasa y un archivo sin extensión se rechaza. La guarda está en `audio_player.py:54` y en `waveform_worker.py:109`. Tests en `tests/test_audio_whitelist_t105.py:9-53` (`xyz`, `m3u8`, `ffconcat`, `mov`, `txt`, sin extensión). La mutación `if False:` en `audio_player.py:54` los deja en rojo. |
| 6 | Suite exit 0 | **ME ABSTENGO** | No corrí la suite completa porque había otros agentes en paralelo. Los 8 archivos tocados o nuevos (`-n 0`) dan **84 passed**. |

Tests ajustados (`git diff main...HEAD -- tests/test_autoadvance.py tests/test_footer.py tests/test_export_crash.py`):
- No se debilitó ninguna aserción: los `assert` son idénticos. Solo se agrega `pump(300)` o una espera para la resolución asíncrona.
- `FakeWave` ahora deja de «correr» después de `wait()`. Es más fiel, no más laxo.
- Queda un comentario desactualizado en `tests/test_autoadvance.py:54` («sin pump»): ahora hay pump. No es un defecto.

## §Pase hostil

**(1) Lotes de log.**
- No se pierden líneas ni cambia el orden: el texto es idéntico al de main (criterio 1).
- Todos los `return` de `run()` pasan por `_finish` (`worker.py:317, 330, 345, 353, 398, 404, 440`). El último lote sale antes de `finished_ok` (`:244`).
- **Latencia:** el umbral de 100 ms solo se mira cuando llega una línea nueva (`worker.py:231-235`). No hay timer. Las líneas que entran en la ventana de 100 ms esperan a la próxima línea, aunque la copia siguiente tarde mucho. Medido con `_copy_stream` demorado 2 s en la 3.ª pista: «▶ Mix», «✓ 1» y «✓ 2» salen recién a los **2,03 s**, mientras `progress` ya marcaba 3/4 a los 0,02 s. Ver D6.
- Hay una pérdida posible sin cubrir: una excepción no capturada en `run()` (por ejemplo `get_content`) tira hasta 49 líneas del buffer. Antes ya se perdía `finished_ok` en ese caso. Lo anoto, pero no lo cuento como defecto.

**(2) Cierre.**
- Cómo se decide qué hilo se abandona: con una tupla cerrada vía `isinstance` (`ui.py:2168`). Todo lo demás, incluido un hilo desconocido, se trata como «escritor» y se espera **sin tope**, con la entrada del usuario excluida (`ui.py:2177-2186`).
- Hay **ExportWorker vivo** al cerrar: lo espera `_wait_export_block` (`ui.py:2144-2145`). Bien.
- Hay **relocate vivo**: se espera entero. Bien, por `test_close_hung_t105.py:58-76`.
- Hay **ambos a la vez**: no pasa, porque se bloquean entre sí (`ui.py:2273` y `:2639`). Salvo el hueco de D5.
- `os._exit(0)` corre después de `settings.sync()` y `logging.shutdown()`. No hay `atexit` en el código de producción (grep vacío).
- Encontré **cuatro** caminos que fallan (D1, D2, D4, D5). Dos de ellos dejan la app colgada para siempre al cerrar.

**(3) fsync.**
- Se hace sobre el fd correcto y en el orden correcto (criterio 3).
- Si `fsync` lanza en un FS que no lo soporta, esa pista sale como «Error copiando» y el `.part` se borra. **Me abstengo** de decir que algún FS que usen los usuarios lance acá: no tengo dónde anclarlo.
- `fsync` en macOS no es `F_FULLFSYNC` y el directorio no se sincroniza. El criterio tampoco lo pide.

**(4) E/S fuera del hilo de UI.**
- Lo cubre `tests/test_ui_io_off_thread_t105.py:28-117`, que espía `mkdir`, `exists` y `resolve_path`.
- «Último click gana» falla en un caso: el click sobre la pista que ya suena entra por el atajo de toggle (`ui.py:1965-1968`) y **no sube `_play_gen`** (`:1972`). Ver D3.
- Fila equivocada: `_row_for` (`ui.py:2058-2065`) solo se usa si la fila original murió. Ahí resalta la primera fila con la misma ruta. Es aceptable.

**(5) Hardlink.**
- `st_nlink > 1`, symlink, `(2)` ocupado y directorio ocupado: todos bien (criterio 4).
- En un FS sin hardlinks (FAT/exFAT) `st_nlink` es 1, así que el camino es el normal.
- Hay una carrera TOCTOU entre `lstat` y `write_text`: es teórica y local.
- El aviso «se escribió como …» sale antes de escribir el archivo, así que es falso si la escritura falla. Es menor.

**(6) Lista blanca contra README.**
- `README.md:37` dice: mp3, wav, aiff, mp4/m4a, flac, wma.
- La lista blanca (`audio_formats.py:11-13`) es un **superconjunto** de eso: suma aac, aif, ogg y opus. No coinciden exactamente, pero todo lo que el README promete se abre (`tests/test_audio_whitelist_t105.py:26-39`). No es un defecto.
- `.MP3` y `.mp4` pasan. Un archivo sin extensión se rechaza con aviso.
- La guarda es por extensión, no por contenido. **Me abstengo** sobre el sondeo de contenido de FFmpeg con un `.mp3` que en realidad es un m3u8: es código de terceros y no lo abrí.

## §Veredicto

**REFUTADO.** Los criterios 1-5 se cumplen tal como están escritos. Pero el objetivo central del ticket, «export y cierre robustos», no se cumple: el propio cambio introduce dos crashes al cerrar (D1 y D2) que en main no existían, porque ahí la E/S era sincrónica.

1. **D1 (datos): cerrar con la comprobación de destino pendiente arranca el export *después* de cerrar la ventana y el proceso aborta.**
   - Código: `ui.py:2287-2293` lanza `DestinationCheck`. Su `checked` llega en cola después de `closeEvent`, `_on_dest_checked` (`ui.py:2295-2321`) arranca `ExportWorker` y la app sale con ese hilo copiando.
   - Prueba: `DestinationCheck.run` demorado 0,5 s (un destino SMB/USB lento, el caso de TEC-31), `_start_export()` y `close()` en el mismo tick. Resultado: `exec` devuelve, `worker running: True`, `QThread: Destroyed while thread '' is still running`, **rc=250**.
   - Qué viola: TEC-24 (cerrar sin abortar) y D-16 (nunca abortar con una copia en vuelo).
   - Arreglo esperado: en `closeEvent`, invalidar el destino pendiente o no arrancar el export si la ventana ya cerró.
2. **D2: cerrar justo después de un click de reproducción → suena la pista con la ventana cerrada, arranca un WaveformWorker y el proceso aborta.**
   - Código: `ui.py:1972-1978`. El resolver termina y su `resolved` llega en cola después de `closeEvent`. `closeEvent` no invalida `_play_gen`, así que `_on_play_resolved` (`ui.py:1983-2002`) llama a `self._audio.play` y a `_start_waveform`.
   - Prueba: resolución inmediata, decoder de 1 s, click y `close()` en el mismo tick. Resultado: `played after close: [(…a.mp3, False)]`, `wave workers alive: [True]`, `Destroyed while thread … still running`, **rc=250**. Con resolución lenta (0,5 s) da lo mismo.
   - Qué viola: TEC-24 y TEC-15. Es una regresión del cambio asíncrono.
3. **D3: «último click gana» no vale si el último click es sobre la pista que ya suena.**
   - Código: `ui.py:1965-1968` hace toggle y `return` sin `self._play_gen += 1`, así que la resolución tardía del click anterior sigue siendo válida en `ui.py:1984`.
   - Prueba: A suena, click en B (resuelve lento), click en A. Resultado: `['play A.mp3', 'toggle A.mp3', 'play B.mp3']`, `playing_path=B.mp3`. Arranca B aunque el último gesto del usuario fue sobre A.
   - Qué viola: TEC-15 (el «último click gana» que dice el propio diff en `ui.py:1969-1970`).
4. **D4: la app puede quedar colgada para siempre al cerrar con un hilo de solo lectura que la lista considera «escritor».**
   - Código: `_READ_ONLY_THREADS` (`ui.py:2168`) deja afuera a `LibraryLoadWorker`, que solo lee (`library_load_worker.py:50-76`: `open_collection`/`open_library`/`FixStore.load`, sin escrituras). El comentario de `ui.py:2165-2167` dice que la «carga» escribe, y eso es falso.
   - Lo mismo pasa con `DestinationCheck` (un `mkdir` colgado en un SMB caído no deja nada a medias).
   - Los dos se esperan con `while not t.wait(50)` sin tope y con la entrada excluida (`ui.py:2183-2184`).
   - Prueba: `_load` colgado 40 s → `close()` sigue sin salir a los 20 s (**TIMEOUT**). Un `mkdir` colgado en el destino también da **TIMEOUT** a los 20 s.
   - Qué viola: TEC-24 (un `stat`/lectura colgada en un USB dormido es justo el escenario del ticket).
5. **D5: el botón Exportar queda muerto en silencio mientras dura la comprobación de destino, y esa ventana saltea la guarda de relocate.**
   - Botón muerto: `ui.py:2287-2288` hace `return` sin aviso si `_dest_check` no es `None`, y la UI no muestra nada mientras comprueba (sigue «en espera», estado `idle`). Prueba: destino colgado y después cambio a un destino bueno + click → `state idle worker None good exists False`. El usuario no puede exportar en toda la sesión y cerrar cuelga (D4).
   - Guarda de relocate: mientras `DestinationCheck` está pendiente, `self._worker` es `None`. La guarda de relocate (`ui.py:2639`) deja pasar y `_on_dest_checked` (`ui.py:2295-2321`) no vuelve a chequear `_relocate_worker` antes de arrancar el export (por lectura de código).
   - Qué viola: TEC-31 (sacar el bloqueo no puede dejar la acción sin respuesta) y la exclusión export/relocate de `ui.py:2273-2278`.
6. **D6 (menor): los lotes no cumplen «≤ 100 ms».**
   - Código: `worker.py:231-235` solo hace flush cuando llega una línea, y no hay timer.
   - Prueba: las líneas ya emitidas esperan toda la copia siguiente (2,03 s con una copia de 2 s). Con WAV grandes en un USB el log va una pista atrasado respecto del progreso.
   - Qué viola: TEC-22, «lotes (≤100 ms)».

Suposiciones marcadas:
- fsync en un FS sin soporte: me abstengo.
- Sondeo de contenido de FFmpeg: me abstengo.
- Criterio 6 (suite completa): me abstengo.

## Verificación 2

Juzgué `587aabb` en un worktree detached aparte, con las mismas sondas de la verificación 1 (ventana real con `BOOT`, `QT_QPA_PLATFORM=offscreen`, un proceso por sonda, tmp dentro del worktree y borrado al final).

| Defecto | Estado | Cita / evidencia |
|---|---|---|
| D1 export tras cerrar | **CORREGIDO** | `ui.py:2141` marca `_closing` y `ui.py:2311-2312` no arranca el export. Sonda con chequeo de 0,5 s y `close()`: `worker=None`, 0 archivos, rc=0. |
| D2 play tras cerrar | **CORREGIDO** | `ui.py:2142` y `ui.py:1987`. Sonda: `played after close: []`, ningún WaveformWorker, rc=0. |
| D3 último click | **CORREGIDO** | `ui.py:1969`. Sonda A→B lento→A: `['play A.mp3', 'toggle A.mp3']`, `playing_path=A.mp3`. |
| D4 cierre colgado | **CORREGIDO** | `ui.py:2174-2177` agrega `LibraryLoadWorker` y `DestinationCheck` a los hilos de solo lectura. Con la carga colgada 40 s y con el `mkdir` colgado: «salida directa», rc=0 a los 4 y 6 s. |
| D5 botón muerto / guarda de relocate | **CORREGIDO** | `ui.py:2298-2299` muestra «Verificando destino…». `ui.py:2313-2320` vuelve a mirar el relocate antes de exportar y `ui.py:2671-2676` frena el relocate mientras se chequea el destino. Queda un resto: con un destino que no responde nunca, el segundo click sigue sin efecto (`ui.py:2296-2297`), pero ahora con el estado a la vista. No lo cuento como defecto. |
| D6 latencia | **CORREGIDO** | `worker.py:248-252` vacía el lote entre bloques. Sonda con una copia de 2 s en 20 bloques: las líneas previas salen a los **0,13 s** (antes 2,03 s). |
| **V7 (nuevo)** relocate termina mientras se cierra | **SE REPRODUCE** | `closeEvent` espera el relocate (`ui.py:2157`). Su `finished_ok` llega en cola después del cierre, y `_on_relocate_finished` no mira `_closing`: con `ok` y `repaired>0` llama a `_reload_after_path_change()` (`ui.py:2858` → `ui.py:1250`), que arranca un `LibraryLoadWorker` nuevo con la ventana ya cerrada. Sonda `p_reloc_race.py`: `RELOAD called closing= True`, un worker de carga nuevo corriendo después de `exec`, `QThread: Destroyed while thread '' is still running`, **rc=250**. Viola TEC-24. Es la misma clase de defecto que D1/D2. |

Regresiones:
- Lotes, fsync, hardlink, lista blanca y cierre: `tests/test_export_integrity.py`, `tests/test_audio_whitelist_t105.py`, `tests/test_close_hung_t105.py`, `tests/test_close_races_t105.py`, `tests/test_ui_io_off_thread_t105.py`, `tests/test_autoadvance.py`, `tests/test_footer.py` y `tests/test_export_crash.py` dan **88 passed**. `tests/test_export_log_batch.py` da 2 passed.
- 1.900 archivos de 64 KiB: con log 2,89 / 2,99 s contra sin log 2,69 / 2,81 s, o sea **1,07× / 1,06×** (≤ 1,3×). Siguen siendo 1.900 archivos.
- La suite completa no la corrí: me abstengo.

**Veredicto: REFUTADO.** D1-D6 quedan corregidos, pero sigue un defecto de cierre: **V7**. Arreglo esperado: que `_on_relocate_finished` no recargue (ni abra modales) si `self._closing`.

## Verificación 3

Juzgué `05bf4a6` en un worktree detached aparte. Esta vez fue acotada a V7 y a los callbacks que llegan tarde durante el cierre.

| Caso | Estado | Cita / evidencia |
|---|---|---|
| V7: relocate que termina durante el cierre | **CORREGIDO** | `ui.py:2792` (`_on_relocate_finished` sale si `_closing`). Repetí `p_reloc_race.py`: `load worker after exec: None`, sin «Destroyed while thread», rc=0 (antes rc=250). |
| Restore que termina durante el cierre | **OK** | `ui.py:2978`. Restore falso de 3 s y `close()` a los 0,1 s: el cierre espera al restore (es un escritor, `ui.py:2196-2203`), el callback no hace nada (`side effects: []`), rc=0. |
| `_on_relocate_ask` durante el cierre | **OK, no se cuelga** | `ui.py:2766-2770`. Probé el peor orden: el worker pregunta *después* del `provide_answer(None)` de `closeEvent` (`ui.py:2166`). No se abre ningún modal (`dialogs: 0`), las respuestas son `[None, None]` y el proceso sale con rc=0. La respuesta llega por el `processEvents` del bucle de escritores en `_exit_if_threads_hung`. Tarda 6,2 s (4 s de `wait(4000)` en `ui.py:2167`, que no procesa eventos, más 2 s de la espera con tope de `_live_threads`). Es lento pero termina. No es un defecto. |
| `_on_finished` del export sin guarda | **No puede tocar widgets destruidos** | La ventana nunca se destruye mientras corre el event loop: no hay `WA_DeleteOnClose` (grep vacío en `ui.py`) y `main.py:42-44` mantiene `win` hasta `sys.exit(app.exec())`. Después de `exec` u `os._exit` ya no se despacha ningún slot. Además `_on_finished` (`ui.py:2380-2424`) solo toca widgets y un `QTimer.singleShot` de 8 s, que en un loop ya terminado no corre. No arranca hilos. |

Regresiones: `tests/test_close_races_t105.py` y `tests/test_close_hung_t105.py` con `-n 0` dan **18 passed**.

**Veredicto: CONFIRMADO.** V7 está corregido y no encontré otros caminos de cierre que fallen en lo que probé.
