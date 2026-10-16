# T-104(d) — Re-auditoría técnica y de rendimiento pre-release 1.0.0

Autor: nerv-desktop · Fecha: 2026-10-16 · Árbol: `main` @ fc61e59 (= d9c9f8f + commit de alta de T-104, solo docs; worktree descartable, ya borrado). Solo lectura de producción: ningún archivo de código ni el backlog se tocó. Mutaciones de prueba hechas únicamente en el worktree y revertidas.

Entorno de medición: macOS 14 (Darwin 23.6), **Intel** i7-9750H, CPython 3.14.8 (expat 2.9.0), PySide6 6.12.0, plataforma Qt **offscreen** salvo que se diga lo contrario. Load average de la máquina **6–15** durante toda la sesión (3 auditores más corriendo): los números absolutos de CPU/pared son pesimistas y ruidosos; las comparaciones dentro de una misma corrida y los ratios son lo confiable. Fixtures sintéticos: los de T-086 (`fx30x200` 30×200 pistas; `fx2x2000`; `fx200x200` 200×200 = 40k pistas / 15 MB sin cues; `fx200x200_real` 40k pistas con 48 hijos por pista / 148 MB) más dos nuevos: `fx800` (800 playlists × 20 pistas) y un NML de Traktor de 193 MB (40k ENTRY con 40 CUE_V2 cada una, 200 playlists × 200). Scripts de medición en `<SCRATCH>/m/` (fuera del repo): `win.py`, `tog.py`, `all.py`, `exp*.py`, `rob*.py`, `reload.py`, `nmlbench.py`, `gen_nml.py`.

> Incidente de medición a declarar: los tres primeros `exp*.py` (export) se lanzaron sin `QT_QPA_PLATFORM=offscreen` y abrieron una ventana Cocoa real unos 80 s cada uno en el escritorio del PO. Esas corridas se descartaron salvo para decir que en Cocoa real el efecto de TEC-22 es peor (86 s vs 40 s). Además las sondas de aborto (TEC-24) dejaron un reporte de crash de macOS (`Problem Reporter`) pendiente; es esperado y no corresponde a la app del PO.

---

## 1. Resumen ejecutivo

1. De los 21 hallazgos de T-086: **18 cerrados, 1 parcial (TEC-14), 2 abiertos (TEC-15, TEC-20)**; todos los cerrados con cita de fix y test; las mutaciones que probé (sin retener el `PreviewWorker`, `closeEvent` sin esperar hilos, `_wait_export_block` sin esperar, «Ya existe» solo por `exists()`) ponen rojo el test correspondiente.
2. **Rendimiento de la tilde: resuelto.** Click 10 con 10×200 pistas: 113 ms de CPU de UI (T-086: 4.779 ms; el harness mete ≈100 ms de piso), constante por click; 2.000 pistas: 282 ms (T-086: 8.290 ms). Carga de XML: ventana visible en 1,4 s con 148 MB (T-086: 7,9 s sin ventana), RSS pico 420 MB (T-086: 1.153 MB).
3. **Nuevo, el más relevante: el log del export frena todo (TEC-22, Media-Alta).** Una línea de log por archivo hace que exportar 1.900 pistas tarde 12,8 s en vez de 2,5 s y que un re-export donde todo es «Ya existe» tarde 8,8 s en vez de 0,8 s (5-10×); con 5.690 archivos 40 s vs 8 s del worker solo. Agrupar el log por lote en la ventana lo devuelve a 3,0 s / 1,0 s. Se extrapola a minutos en un re-export de 40k pistas.
4. **Nuevo (TEC-23, Media): «Marcar todas» no escala.** 100 playlists = 8,2 s, 200 = 12,2 s (20.762 widgets), 800 = 105 s de UI con 463 huecos >100 ms; y la carga de 800 playlists bloquea la UI 2,6 s de un tirón (las tarjetas del árbol no se crean por lotes).
5. **Nuevo (TEC-24, Media): un solo `stat` colgado >2 s (USB que despierta, SMB caído) hace que cerrar la app termine en SIGABRT** (reproducido, exit -6): `closeEvent` espera 2 s y sale con el `PreviewWorker` vivo. Los datos no se corrompen, pero macOS muestra «se cerró inesperadamente».
6. Deuda estructural: `ui.py` creció a 2.965 líneas (+211 desde T-086), `MainWindow` 141 métodos / 93 atributos de instancia; el ciclo `ui_components`↔`preview_card` y los imports de capa invertidos siguen. T-099 ya está en 1.1; no bloquea el release pero cada ticket nuevo lo engorda.
7. Tests: no hay test de tiempo de ventana ni de carga de 40k pistas, ni test de «resultado ya encolado al cancelar» (M1), ni CI en Windows; D-29..D-34 siguen abiertas (todas Baja).
8. Empaquetado: el bundle de referencia en `dist/` es **anterior** a T-094..T-103 (15/10 16:54, 135 MB, `LSMinimumSystemVersion` 14.0, aún con QtQml/QtVirtualKeyboard); no se puede validar tamaño/minos/arranque de HEAD sin reconstruir (no autorizado hoy). Evidencia de T-096 dice 122 MB.
9. Veredicto técnico: **nada bloquea el tag desde la pata técnica**; recomendaría resolver TEC-22 (S) y TEC-24 (S) antes de 1.0.0 y dejar TEC-23 con un aviso/tope, o en 1.0.1.

---

## 2. Tabla T-086: cerrado / parcial / abierto

Cita = código en HEAD (archivo:línea de este árbol) y test que lo ata. «Verif.» = lo que yo comprobé hoy.

| ID | Estado | Fix (cita) | Test | Verif. hoy / residuo |
|---|---|---|---|---|
| TEC-01 filas por tilde | **CERRADO** (síntoma); escala de tarjetas → TEC-23 | T-089: filas perezosas con ventana (`preview_card.py:231-310`, `_ensure_window`), `_sync_preview_cards` reutiliza tarjetas (`ui.py:1618-1640`) | `tests/test_preview_lazy_t089.py` (10 tests: ≤15 filas, tarjeta primera se conserva, destildar renumera) | `tog.py` 10 clicks: CPU UI 217/144/102/…/113 ms (T-086: 697…4.779), 96 widgets nuevos por click (T-086: 1.235), maxgap 16-70 ms (T-086: 84-409). 2.000 pistas: 282 ms y 209 ms |
| TEC-02 `PreviewWorker` destruido en vuelo | **CERRADO** para el caso reproducido (stat de 50 ms); residuo → TEC-24 | `ui.py:1559-1568` (`_cancel_preview_worker` retiene con `_retain_thread`), `ui.py:1570-1578`; `PreviewWorker.done` ya no pisa `QThread.finished` (`preview_worker.py:100-103`) | `tests/test_thread_lifecycle.py:32,67` | Probé la mutación «no retener»: rojo. `rob.py clicks` (3 clics con stat 50 ms + cierre): exit 0 (T-086: 134) |
| TEC-03 cierre con update en vuelo | **CERRADO** para el caso reproducido; residuo → TEC-24 | `update_checker.py:141-150` (hilo daemon, no QThread); `ui.py:2110-2147` (espera con tope de hilos vivos) | `tests/test_thread_lifecycle.py:78,102`, `tests/test_robustez_t095.py:80` | `t7_quit_update` (urlopen de 3 s, cierre a 300 ms): `app.exec()` 0, exit 0 (T-086: 134). Mutación «closeEvent sin esperar `_live_threads`»: 2 tests rojos. Mutación «`_wait_export_block` sin esperar»: rojo |
| TEC-04 copia truncada tomada como «Ya existe» | **CERRADO** | `worker.py:154-172` (`_copy_atomic` a `.part` + `os.replace`, modo `xb`), `worker.py:411-421` (`_is_complete_copy` compara tamaño) | `tests/test_export_integrity.py` (incl. `test_existing_file_with_a_different_size_is_recopied_but_equal_size_is_skipped`) | Mutación `_is_complete_copy`→`exists()`: rojo. Sin `fsync` del archivo copiado (ver TEC-28, Baja) |
| TEC-05 XML en hilo de UI | **CERRADO** | T-094: `library_load_worker.py`, expat sin DOM (`rekordbox_xml.py:288-398`), carga lanzada tras `show()`; ADR-006 | `tests/test_library_load_t094.py` (9), `tests/test_t094_load.py` (18), `test_t094_arq*.py` | Ver §4: ventana visible 1,44 s con 148 MB (cota 1,5 s, poco margen), 3,0 s hasta 200 tarjetas con 15 MB, RSS pico 420 MB (2,8×). Reload ×4 sin fuga (456→529 MB, se estabiliza) |
| TEC-06 NFC/NFD en relocate | **CERRADO** | `relocate_core.py:323` (`unicodedata.normalize("NFC", name).casefold()`) en índice y lookup | `tests/test_relocate_core.py:312-` (`test_disk_nfd_xml_nfc_is_found_exactly`) | Por QA T-093 (4 mutaciones); no repetí |
| TEC-07 homónimas / `..` / reservados | **CERRADO** | `worker.py:375-392` (`_unique_folder_names`, comparación `casefold`), `rekordbox_export.py:27-45` (`sanitize`: `..`, vacío, CON/NUL/COM1…, puntos/espacios finales) | `tests/test_export_integrity.py`, `tests/test_robustez_t095.py:104,130` | Preview y export usan la misma función (`folder_names_by_playlist`, `worker.py:404`) |
| TEC-08 `_estimate_size` | **CERRADO** | `worker.py:454-472` descuenta lo ya completo | `tests/test_robustez_t095.py:23` | D-29 sigue abierta: ninguna aserción de que un truncado se cuenta (mutación sobrevive según QA) |
| TEC-09 log sin tope | **CERRADO** (tope) pero ver TEC-22 | `ui.py:989` `setMaximumBlockCount(5000)` | `tests/test_robustez_t095.py:38` | El tope existe; el costo por línea sigue (TEC-22) |
| TEC-10 fallos silenciosos | **CERRADO** | `worker.py:425-433` (`_get_songs_list` loguea y avisa), `ui.py:1680-1760` (`_extract_preview_data`: no cachea el vacío, avisa) | `tests/test_robustez_t095.py:49,61` | Efecto lateral: una playlist ilegible loguea con traceback en cada tilde (`folder_names_by_playlist` la relee, `worker.py:404-408`): ruido de log, Baja |
| TEC-11 `build_windows.ps1` | **CERRADO** (lectura; Windows no verificado) | `scripts/build_windows.ps1:50-62` (one-dir correcto), `--require-hashes`, PyInstaller 6.20.0 pineado, `$ErrorActionPreference="Stop"` | `tests/test_release_scripts.py:118` | Sin Windows: no corrí el script |
| TEC-12 Qt sin uso | **CERRADO** por evidencia, no re-verificado en build fresco | `rb_exporter.spec:50-65` (`excludes` + filtro `_UNUSED_QT` de binarios/datas), `scripts/check_bundle.sh:12-16` | `tests/test_packaging_manifest.py:78` | Evidencia T-096: 135→122 MB (−13,4 MiB; QtPdf ya no viaja en PySide 6.12). Yo no pude reconstruir: el `dist/` de referencia es previo (ver TEC-27) |
| TEC-13 `release_mac.sh` | **CERRADO** | sin `--deep` al firmar (solo `codesign --verify --deep`, `release_mac.sh:217`), `trap` de limpieza (`:80`), aviso con `DEVELOPER_ID` sin `NOTARY_PROFILE` (`:82-84`), versión única desde `ui.py` (`rb_exporter.spec:19`) | `tests/test_release_scripts.py:182-` | Notarización real sigue pendiente del PO (D-28) |
| TEC-14 god-object `ui.py` | **PARCIAL** | Extraídos: `library_load_worker.py`, `load_cancel.py`, `playlist_filter.py`, `row_blocks.py`, `startup_guard.py`, `dialogs.py`, `preview_card.py` | — | `ui.py` 2.754→**2.965** líneas, `MainWindow` 141 métodos y 93 atributos de instancia, `__init__` 170 líneas (`ui.py:220`). Ciclo `ui_components`→`preview_card` (import diferido) y `ui_components`/`preview_card`/`footer` importando workers siguen (§3.3). T-099 en 1.1 |
| TEC-15 audio/`_row_for` en hilo de UI | **ABIERTO** | — | — | `ui.py:1967-1970` hace `Path.exists`/`resolve_path` en el hilo de UI al reproducir; `ui.py:2041-2043` `findChildren(FileRow)` en cada fin de pista (ahora acotado por filas perezosas) |
| TEC-16 `qrcode` | **CERRADO** | `requirements.in:10` `qrcode==8.2` (con hashes en `requirements.txt:105`), `ui.py:188-209` | `tests/test_donation_qr.py` | `import qrcode` ok en el venv |
| TEC-17 `exists()` de reparaciones | **CERRADO** | `rekordbox_xml.py:197` corre en el worker (`library_load_worker.py:73-75`) | `tests/test_library_load_t094.py:128` | Verifier T-094 interceptó `Path.exists`: 0 llamadas de pistas en el hilo de UI |
| TEC-18 cache de existencia | **CERRADO** | `ExistenceRecheckWorker` (`preview_worker.py:68-87`), re-chequeo al recuperar foco con throttle 5 s (`ui.py:2154-2172`) | `tests/test_robustez_t095.py:329,341` | Residuo: si cambia algo, `_on_recheck_done` reconstruye TODA la vista previa (`ui.py:2174-2181`): con muchas tarjetas marcadas cae en TEC-23 |
| TEC-19 `/X/` en POSIX | **CERRADO** | `rekordbox_export.py:79-85` | `tests/test_resolve_path.py` | — |
| TEC-20 instancia única | **ABIERTO** | — (T-098, solo Windows) | — | `grep QLockFile\|SingleInstance` en `main.py`, `app_logging.py`, `app_paths.py`: vacío. No verificable sin Windows |
| TEC-21 nombre >255 | **CERRADO** (macOS); Windows no verificado | `worker.py:39-47,60-135` (`_MAX_STEM = 200` en bytes UTF-8, corte por grafemas), `_long_path_warning` (`:51-57`) | `tests/test_export_integrity.py:210-` | El límite real de APFS/NTFS (UTF-16) no se probó en Windows; 200 bytes UTF-8 cubre ambos por construcción |

---

## 3. Hallazgos nuevos (TEC-22 en adelante)

Severidad: Alta = pérdida de datos o crash en uso normal; Media = degradación visible en uso plausible o crash en borde; Baja = deuda. Esfuerzo: S ≤ 0,5 día · M ≈ 1 día · L ≈ 2-3 días.

| ID | Sev | archivo:línea | Descripción | Evidencia reproducible | Acción | Esf. |
|---|---|---|---|---|---|---|
| **TEC-22** | **Media-Alta** | `ui.py:2262` (`worker.log.connect(self._log)`), `ui.py:2345-2346` (`_log` → `appendPlainText` por señal); `worker.py` emite 1-2 `log` por archivo (`:248`, `:276-330`) | El log del export es una señal encolada y un `appendPlainText` (con repintado del `QPlainTextEdit`) **por archivo**. La UI no da abasto y, por la contención del GIL entre el hilo de UI y el worker, **el propio worker va 5-10× más lento**. No es la barra de progreso: `_on_progress` desconectada no cambia nada; desconectar `_log` sí. | `exp6.py` (10 playlists de `fx30x200` = 1.900 archivos, offscreen, load 6): copia 12,8 s con log vs **2,5 s** sin `_log` vs 2,3 s sin log ni progreso; re-export con todo «Ya existe» 8,8 s vs **0,8 s**. `exp7.py` con el log agrupado en lotes de 100 ms (mismo texto): 3,0 s y **1,0 s**. `expw.py` (30 playlists = 5.690 archivos, worker solo): 8,1 s; en la ventana 38-40 s (86 s en Cocoa real, 79 s la segunda). | En `ExportWorker`, acumular líneas y emitir un `log(str)` con varias líneas cada ~100 ms o 50 líneas (o un `QTimer` en `MainWindow` que vacía un buffer con un único `appendPlainText("\n".join(...))`); throttle del progreso a ≤20 Hz. Test: export de N archivos tiny con tope de tiempo relativo al worker solo. | S |
| **TEC-23** | **Media** | `ui.py:2205-2210` (`_set_all`), `ui.py:1618-1640` (`_sync_preview_cards` lanza todas las tarjetas nuevas), `ui.py:1772` (`_pump_render_queue` una tarjeta por tick), `ui.py:1323` (`_populate_playlists` sin lotes), `ui.py:2174-2181` (`_on_recheck_done` reconstruye todo) | El costo de la vista previa es lineal en **tarjetas** (≈60-130 ms y ≈100 widgets por tarjeta aunque tenga 12 filas). «Marcar todas» con una librería grande deja la UI inutilizable; destildar es barato. La carga con 800 playlists crea las 800 tarjetas del árbol en un solo paso. | `all.py` (offscreen, load 7-12): marcar **100** playlists = 8,2 s de CPU UI (maxgap 688 ms, 20 huecos >100 ms), **200** = 12,2 s (20.762 widgets, RSS 613 MB, maxgap 1.023 ms), **800 (fx800, 20 pistas c/u)** = **105 s**, 463 huecos >100 ms, 25.329 widgets. Destildar 800: 2,0 s. `win.py fx800`: ventana en 1,36 s pero **hueco de 2.575 ms** al poblar 800 tarjetas (con 200: 424-534 ms). | (a) mínimo viable 1.0: confirmación o tope al marcar >N (p. ej. 50) y poblar el árbol por lotes con `QTimer(0)`; (b) 1.1: tarjetas diferidas (solo cabecera hasta estar en pantalla) o `QListView` + delegate como proponía T-086 §3.4-A (T-099). | S (a) / L (b) |
| **TEC-24** | **Media** | `ui.py:2144-2147` (`thread.wait(2000)` y luego `super().closeEvent`), `preview_worker.py:123-130` (`_check` hace `stat` sin tope), `ui.py:2120-2124` (waveform `wait(1500)`) | Si un `stat` del `PreviewWorker` (o un `QAudioDecoder.start`) está bloqueado en el kernel más de 2 s —volumen de red caído, USB que despierta— `closeEvent` agota la espera y la app sigue su salida con un `QThread` vivo: Qt aborta (`QThread: Destroyed while thread is still running`, SIGABRT). Sin pérdida de datos, pero macOS muestra el diálogo de «se cerró inesperadamente». T-088 solo cubrió stats de 50 ms. | `rob_hang.py closepreview` (un `_check` que duerme 6 s, tilde y cerrar): `close ms 2010`, «SURVIVED», luego `QThread: Destroyed while thread '' is still running`, **exit -6**. Los tests actuales usan stats de 50 ms (`test_thread_lifecycle.py:102`). | Hacer los chequeos de existencia con un `threading.Thread` daemon (patrón ya usado en `update_checker.py:141`) o, si tras la espera algún hilo sigue vivo, terminar el proceso con `os._exit(0)` después de `settings.sync()`; test con stat de 4 s y exit 0. | S |
| TEC-25 | Baja | `ui.py:381` (carga arrancada en el constructor), sin test | La cota «ventana visible ≤ 1,5 s con 40k pistas» (ratificada por el PO) no tiene test y el margen es 4-8 %: hoy 1,44 s con 148 MB bajo load 12; el verifier T-094 midió 1,465 s. En Windows/HDD o una máquina más lenta se pasa. | `win.py fx200x200_real`: ventana 1.419-1.441 ms. `grep perf_counter tests/test_library_load_t094.py`: solo `dt < 0.4` con un lector falso lento, nunca un XML grande. | Test de humo con XML sintético de 40k pistas (generado en `tmp_path`) que mida construir+`show()` con tope holgado (p. ej. 3 s) para detectar regresiones gruesas; evaluar diferir la carga al primer paint (deuda 4 del arquitecto en `engram/plans/T-094.md`). | S |
| TEC-26 | Baja | `ui.py:1403` (tarjeta «Cargando librería…»), `traktor_db.py:395-430` | La carga larga no tiene progreso ni botón de cancelar: solo Ctrl+R o cerrar. Un NML de 193 MB tarda 15 s (iterparse) y un XML de 148 MB 10 s. La UI responde, pero el usuario no sabe si se colgó. | `nmlbench.py`: Traktor 193 MB / 40k ENTRY: **15.155 ms**, RSS 17→76 MB (memoria bien, tiempo alto). `bench_parse.py` Rekordbox 148 MB: 10.088 ms (T-094: 10,4 s; no mejoró ni empeoró, solo salió del hilo de UI). | Barra indeterminada o «N MB leídos» desde el callback `should_cancel` (ya se consulta cada 2.048 eventos / por bloque) y un botón «Cancelar». | S |
| TEC-27 | Baja | `dist/` (ignorado por git), `engram/qa/T-103.md` | El «bundle de referencia» en `dist/` es del 15/10 16:54, antes de T-094..T-103: `LSMinimumSystemVersion` 14.0, todavía con `QtQml*`/`QtVirtualKeyboardQml`, 135 MB; conviven además builds viejos de junio (`listBuddy-1.0.dmg`, `List Buddy`, 66 MB). Cualquier prueba manual del PO sobre ese `.app` no representa HEAD. | `PlistBuddy -c "Print :LSMinimumSystemVersion" "dist/List Buddy.app/Contents/Info.plist"` → 14.0; `find "dist/List Buddy.app" -iname '*QtQml*'` → 4 resultados; `du -sh` 135M. | Reconstruir una vez antes del tag (lo hace `release_mac.sh`) y borrar los artefactos viejos; ejecutar `check_bundle.sh` y `minos-check` sobre el resultado. | S |
| TEC-28 | Baja | `worker.py:154-172` | La copia no hace `fsync` del `.part` antes del `os.replace`; con USB sin expulsar, un corte de energía puede dejar un archivo del tamaño correcto con contenido incompleto que el siguiente export da por bueno (la comparación es solo por tamaño, `worker.py:411-421`). No se pierde nada que no se perdería igual al desenchufar sin expulsar; es defensa en profundidad. | Por lectura; no reproducible sin cortar la energía. | `os.fsync(fdst.fileno())` antes del cierre (costo medible en USB lento: decidir con medición) o documentar «expulsá el disco». | S |
| TEC-29 | Baja | `.github/workflows/tests.yml:17-21`, `.github/workflows/release.yml:39` | La suite corre solo en `macos-15` (arm64); el producto se distribuye también para Windows y no hay job de Windows. Las pruebas de `os.replace`, rutas `/C/…`, `sanitize` de reservados y `build_windows.ps1` dependen de revisiones manuales (T-059 se hizo en otra máquina). | `ls .github/workflows` + lectura de `tests.yml`. | Job `windows-latest` con la suite o, al menos, los tests no-Qt (`-k "not qt"`), cuando el PO decida publicar Windows. Las versiones de las actions (`checkout@v7`, `setup-python@v7`) no las pude verificar: no hay red a registros hoy. | M |
| TEC-30 | Baja | `CLAUDE.md:68`, tabla «Arquitectura» de `CLAUDE.md`, `engram/` | Deriva de documentación: «Python 3.14.3» (el venv y el CI usan 3.14.8) y la tabla de arquitectura no lista `preview_card.py`, `library_load_worker.py`, `load_cancel.py`, `playlist_filter.py`, `row_blocks.py`, `startup_guard.py`, `dialogs.py`, `icons.py`, `branding.py`, `app_logging.py`, `update_checker.py`. `engram/09_codemap.md` (P-22) no existe. | `ls engram/09_codemap.md` → no existe; `python -c "import sys"` → 3.14.8. | Regenerar con `/nerv-create-codemap` y corregir la tabla. | S |
| TEC-31 | Baja | `ui.py:2326`, `ui.py:2237-2240` (`Path(output).mkdir` en `_start_export`), `ui.py:1967` | Más E/S de disco en el hilo de UI sobre rutas que pueden ser de red: `mkdir` del destino al exportar, `output_path.exists()` al terminar, `exists()` al reproducir (ya en TEC-15). Con un volumen de red caído se congela la ventana (beachball). No medido con red real. | Por lectura. | Agruparlas con TEC-15: validar el destino en un hilo corto o con `QTimer` y mostrar «comprobando…». | S |

### 3.1 Notas por hallazgo (sin repetir la tabla)

- **TEC-22, por qué no basta el tope de 5.000 bloques.** El costo está en cada `appendPlainText` (re-layout/repintado del viewport del `QPlainTextEdit`: 4,4 ms por repintado en el contador de eventos de `exp4.py`, ≈1.100 repintados para 5.690 archivos), no en el crecimiento del documento; y la lentitud del worker viene de que el hilo de UI satura el GIL con slots encolados (la suma de tiempos dentro de `_log`/`_on_progress` es solo ≈3 s de los 38 s, medida con `perf_counter` dentro de los slots). Con archivos reales de 8 MB la copia domina (≈50-100 ms por archivo) y el efecto casi no se ve: el caso que duele es el **re-export incremental** (todo «Ya existe»), justo el caso que T-095 optimizó en `_estimate_size`.
- **TEC-23 y T-089.** El criterio de T-089 (click 10 ≤ 1 s) se cumple con holgura, pero se midió 1 tilde a la vez. El camino «Marcar todas»/recarga con todo marcado/`_on_recheck_done` crea N tarjetas de golpe; cada tarjeta sigue costando decenas de ms aunque solo construya 12 filas (QSS + 4-6 widgets de cabecera + efecto de fade).
- **TEC-24.** El fix de T-088 retiene el hilo y espera 2 s; es correcto para I/O lenta, no para I/O colgada. Es el mismo límite que D-16 aceptó para el export (allí se decidió esperar sin tope con cursor de espera, `ui.py:2189-2194`: ahora el cierre del export puede quedar colgado indefinidamente si el disco muere, con `processEvents(ExcludeUserInputEvents)`; decisión del PO ya registrada, solo la recuerdo).

### 3.2 Lo que revisé y está bien (QA no necesita volver)

- Cancelaciones de carga: 15 Ctrl+R seguidos, cambio de fuente en vuelo y cierre a 0,2/2/6 s (verifier T-094, y `rob.py closeload` hoy con 148 MB: `close ms 27`, exit 0). Tests de recarga encadenada, cambio de ruta y de fuente en vuelo existen (`tests/test_library_load_t094.py:79,92,104`), a diferencia de lo que decía la deuda de la primera ronda.
- Memoria: 4 recargas seguidas de 148 MB: RSS actual 456→508→526→529 MB (se estabiliza; sin fuga). Tarjetas de preview 800: 609 MB.
- Traktor: `iterparse` + `clear()` de ENTRY y COLLECTION mantiene 76 MB de RSS con un NML de 193 MB.
- Export: escritura a `.part` + `os.replace`, limpieza de `.part` huérfanos solo con nombre propio, ENOSPC con mensaje, cancelación entre bloques de 1 MiB, mkdir fallido con aviso.
- Onda: decode con tope de 20 min y de 90 s, `errorOccurred` corta (test en `test_robustez_t095.py:180`), caché FIFO de 32, resultados por tuplas livianas (≈24k ventanas por 20 min).
- Audio/hilos: ningún worker toca widgets; `QThread` solo por señales; el `excepthook` reencola el diálogo al hilo de UI.
- Spec/excludes/UPX: `upx=False` en todo (`rb_exporter.spec`), sin pyrekordbox/sqlcipher/sqlalchemy, `check_bundle.sh` vigila Qt sin uso.

### 3.3 Imports y capas (análisis AST de HEAD)

- Sin ciclos a nivel módulo. Fan-out de `ui.py`: 23 módulos propios (T-086: menos); es el reflejo de TEC-14.
- Excepciones a la regla `main → ui → worker/db → rekordbox_export`, igual que en T-086: `rekordbox_export` importa `rekordbox_xml` de forma diferida; `ui_components` importa `preview_card` de forma diferida (ciclo roto a mano) y, junto con `preview_card` y `footer`, importa módulos de la capa worker (`preview_worker` por el DTO `TrackRow`, `waveform_worker`). Mover `TrackRow`/`GroupData` a un módulo sin Qt los elimina (parte de T-099).
- `startup_guard.py` (T-103) es una hoja sin imports del proyecto: bien.

---

## 4. Mediciones: antes (T-086) vs ahora

Condiciones: «antes» = informe T-086 (Intel, Cocoa real, load ≈4); «ahora» = esta sesión (Intel, **offscreen**, load 6-15). Offscreen no pinta en pantalla, así que los CPU de UI de «ahora» son un **piso**; el harness de clicks mete ≈100 ms de espera por click (T-086 ≈150).

| Qué | Antes (T-086) | Ahora | Herramienta |
|---|---|---|---|
| Click n=10, 10 playlists × 200 pistas, CPU UI | 4.779 ms (suma 10 clicks 27,9 s) | **113 ms** (suma 10 clicks ≈1,4 s); click 1 = 217 ms | `tog.py fx30x200 10 150` |
| Widgets nuevos por click | ≈1.235 | 96 | idem |
| Peor hueco del event loop por click | 84-409 ms | 16-70 ms | idem |
| 1 click, playlist de 2.000 pistas | 8.290 ms, 138 huecos >16 ms | 282 ms (2º click 209 ms) | `tog.py fx2x2000 2 150` |
| `open_library` 148 MB (40k pistas con cues), solo parseo | 7.874 ms, RSS 15→1.153 MB | 10.088 ms (load 12-13), RSS 18→**316 MB** | `bench_parse.py` |
| `open_library` 15 MB (40k sin cues) | 1.017 ms, RSS 15→142 MB | 1.865 ms (load 13; CPU 1.720 ms), RSS 18→146 MB | idem |
| Ventana visible, 148 MB | bloqueada 7,9 s (sin ventana) | **1.419-1.441 ms**; 200 tarjetas a los 10,1 s; RSS pico 420 MB (2,8× el XML); maxgap 534 ms | `win.py` |
| Ventana visible, 15 MB | 2,2-2,9 s con 200 playlists | 1.441 ms; tarjetas a los 3,0 s; maxgap 424 ms | idem |
| Ventana visible, 800 playlists (nuevo) | — | 1.361 ms; tarjetas a los 4,06 s; **hueco de 2.575 ms** | `win.py fx800` |
| Recarga ×4 de 148 MB (RSS actual) | — | 456 → 508 → 526 → 529 MB | `reload.py` |
| Traktor NML 193 MB, 40k ENTRY (nuevo) | — | 15.155 ms, RSS 17→76 MB | `nmlbench.py` |
| Export 1.900 archivos tiny (10 pl), con log por archivo | — | copia 12,8 s; re-export «Ya existe» 8,8 s | `exp5.py` |
| Idem sin señal `log` | — | 2,5 s / 0,8 s | `exp6.py VAR=NOLOG` |
| Idem con log en lotes de 100 ms | — | 3,0 s / 1,0 s | `exp7.py VAR=BATCH` |
| Export 5.690 archivos (30 pl) | — | worker solo 8,1 s; en ventana 38-40 s offscreen (86 s Cocoa real) | `expw.py`, `exp3.py` |
| Marcar 100 / 200 / 800 playlists de golpe | — | 8,2 s / 12,2 s / 105 s | `all.py` |
| Cierre con `stat` colgado 6 s | — | cierre 2.010 ms y SIGABRT (exit -6) | `rob_hang.py` |
| Cierre con carga de 148 MB en vuelo | — | 27 ms, exit 0 | `rob.py closeload` |
| Tamaño del bundle de referencia | 140 MB | 135 MB (`dist/`, **previo a T-096**); T-096 declara 122 MB tras el fix | `du -sh` / `engram/evidence/T-096_bundle.txt` |
| Tiempo de import de `ui`+Qt+numpy en proceso | ≈1,16 s hasta `main()` en el `.app` | 0,71-0,93 s (script, no `.app`) | `win.py` |

---

## 5. Qué no se pudo verificar

- **Windows en general** (rutas largas, `os.replace` con antivirus, doble instancia TEC-20, `build_windows.ps1` en ejecución, límite de nombre en UTF-16, `CurrentByteIndex` >2 GiB con el expat de Windows —deuda 8 del arquitecto—): solo lectura de código.
- **El bundle de HEAD**: no se corrió PyInstaller (instrucción del PO). Tamaño post-T-096 (122 MB), `minos` 14.4, arranque medido del `.app` y arranque con XML grande dentro del bundle quedan sin medir; el `.app` de `dist/` es previo.
- **Cocoa real con la UI visible** salvo las dos corridas accidentales del export (que confirman que TEC-22 es peor en pantalla). Los CPU de UI de los clicks y de «Marcar todas» son pisos offscreen; en pantalla real serán mayores.
- **Apple Silicon**: toda la medición es Intel.
- **Discos de red/USB reales**: la latencia se simuló con `sleep` dentro de `PreviewWorker._check`; un `stat` realmente colgado en el kernel (SMB caído) no se probó, solo su equivalente de 6 s.
- **Suite completa**: no se corrió (el PO tiene la app abierta). Corrí en serie solo los archivos de las mutaciones (`test_thread_lifecycle`, `test_robustez_t095`, `test_library_load_t094`, `test_export_integrity`, `test_export_crash`); los «776 passed» son los que reporta `engram/_state.md`.
- **Las versiones de las GitHub Actions** (`checkout@v7`, `setup-python@v7`): no hay forma de comprobarlas sin red a los registros.
- **XML reales de Rekordbox**: los fixtures son sintéticos (48 hijos por pista); los exports reales varían. Las medidas de tiempo bajo load 6-15 pueden inflarse ≈1,5-2× respecto de una máquina ociosa (T-086 se midió a load ≈4).
- Deudas D-29..D-34 (todas Baja): confirmadas abiertas en `engram/03_backlog.md`; solo D-29 y la ausencia de M1 las contrasté con el código/tests hoy.

---

## 6. Cómo reproducir

`PY=<REPO>/.venv/bin/python`, `W=<worktree detached de main>`, `F=<carpeta con el fixture>`; todos con `QT_QPA_PLATFORM=offscreen`:

- Tilde: `$PY tog.py $F/fx30x200 10 150` · 2.000 pistas: `$PY tog.py $F/fx2x2000 2 150`
- Carga: `$PY win.py $F/fx200x200_real x $W` · `$PY bench_parse.py $F/fx200x200_real/rekordbox.xml` · `$PY reload.py $F/fx200x200_real $W`
- Marcar todas: `$PY all.py $F/fx200x200 $W 200` · `$PY all.py <absolute>/fx800 $W 800`
- Traktor: `$PY gen_nml.py nml/collection.nml && $PY nmlbench.py nml/collection.nml $W`
- TEC-22: `VAR=NOLOG $PY exp6.py $F/fx30x200 $W 10` (y sin `VAR`, y `VAR=BATCH $PY exp7.py …`); worker solo: `$PY expw.py $F/fx30x200 $W 30`
- TEC-24: `$PY rob_hang.py $F/fx30x200 closepreview $W` (esperado hoy: exit -6)
- Robustez: `$PY rob.py $F/fx30x200 clicks $W`, `… closeload` (con `fx200x200_real`), `$PY t7_quit_update.py`
- Mutaciones: editar la línea indicada en el worktree, `pytest -q -n 0 -x <archivo>`, `git checkout <archivo>`.
