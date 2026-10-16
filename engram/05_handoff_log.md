# Handoff Log — listBuddy

> Entradas nuevas ARRIBA. Máx. 6 líneas por entrada. Al superar 30 entradas,
> el Orquestador mueve las más viejas a ~/.nerv/archive/listBuddy-handoffs-[fecha].md

### [2026-10-16 00:40] T-094 y T-097 RECHAZADAS por 2ª vez (solo tests débiles) → fixes del Orquestador → tope P-2
- T-094 D3: `test_traktor_cancellation_is_checked_while_scanning` (3000 entradas, cancela en la 2ª consulta; rojo con `ticks == 1`). T-097 D6: `_step_if_operands` parsea el `if:` real y exige la guarda como operando de `&&` sin `||`; paso del tarball con `name:` como ancla; rojo con `&&`→`||` y con `|| true`.
- Ambos tickets llegan al tope de 2 rechazos (P-2 → nerv-arquitecto + informar al PO). En los dos casos QA declaró el código correcto y objetó solo la fuerza de los tests. Se consulta al PO antes de gastar en arquitecto.
- Quien retoma: nerv-orquestador (espera decisión del PO).

### [2026-10-16 00:05] T-094 RECHAZADO → PO ratifica ≤ 1,5 s + fix D2 · T-097 fix mergeado → re-QA (X) de ambos
- T-094 D1: ventana 1,3 s vs < 1 s. PO decide en sesión: aceptar ~1,3 s (criterio ≤ 1,5 s, anotado en la fila). D2: `test_cancellation_is_checked_while_scanning` (`_CHUNK`=4096, cancela al 3º bloque, `_build_tree` parcheado para que solo `_scan` pueda cortar); rojo sin el chequeo de `_scan`, verde con él.
- T-097: nerv-desktop corrigió D1-D5 en `fix/t097-qa1` (5 commits, prueba de rojo de D4 con dry-run real) → mergeado en rc2, actionlint OK.
- Re-QA nivel X de T-094 y T-097 (2º intento). Después: nerv-verifier de los 5 Strong, suite completa, merge a main, push.
- Quien retoma: nerv-orquestador → nerv-qa.

### [2026-10-15 23:30] QA T-096 APROBADO (intento 2) · QA T-097 RECHAZADO → nerv-desktop (intento 2, X)
- T-097 S RECHAZADO con 5 defectos (secrets en PR del mismo repo, tarball duplicado entre patas, bug de expansión en Resumen, test que asserta texto fuente, cifra sin fuente). No es simple → handoff a nerv-desktop en worktree `fix/t097-qa1` desde `release/1.0.0-rc2` (release_mac.sh ya fusionado con T-096). Nivel X para la re-QA.
- Quien retoma: nerv-desktop → nerv-orquestador → nerv-qa.

### [2026-10-15 23:05] QA T-095 APROBADO · T-092 APROBADO (intento 2) · T-096 RECHAZADO → fix → re-QA (X)
- T-095 S APROBADO 10/10 (deudas D-29/D-30). T-092 X APROBADO 3/3. T-096 S RECHAZADO: D1 sin test para 3.14.10 en `version_ge` (mutación `sort -V`→`sort` sobrevive). Fix del Orquestador (simple, autorizado por el PO): caso `("3.14.10", {})` en la parametrización; rojo con la mutación, verde sin ella.
- Re-QA T-096 nivel X (2º intento). T-094 en QA. Falta T-097 y los nerv-verifier.
- Quien retoma: nerv-orquestador.

### [2026-10-15 22:40] QA T-092 RECHAZADO (1/2) → fix del Orquestador → re-QA (intento 2, X)
- Defectos: D1 `_open_update_link` sin test (mutación sobrevive) · D2 ruta personal en engram/qa/T-093.md rompe la suite en rc2. Ambos simples: el PO autorizó al Orquestador a resolver lo simple («si es simple hacelo vos»).
- Fix: `tests/test_update_link_barrier.py` (2 tests en subproceso; proof of red: con `url = self._update_url` falla, con `safe_release_url` pasa); rutas personales saneadas a `<HOME>` (`git grep` vacío, test verde).
- Re-QA T-092 en nivel X (2º intento, P-11): nerv-qa con pase hostil sobre el fix y el resto del ticket.
- Quien retoma: nerv-orquestador.

### [2026-10-15 22:20] nerv-orquestador → nerv-qa T-092 (S) + T-095 (S)
- Gate run 3: PASS en T-092/094/095/096/097 (nivel S, plan estampado con ratificación del PO, proof of red OK, suite verde). QA de a dos (lección retro: 5 en paralelo dieron flakiness), worktrees propios sobre `release/1.0.0-rc2`.
- T-092: revisar también el ajuste de integración del gate D-14 (`--dry-run` avisa, release aborta). T-095: revisar la resolución en worker.py (`_planned_dest` + `_long_path_warning`) y las «Diferencias con el encargo» del handoff.
- Siguen: T-094 + T-096, luego T-097; después nerv-verifier (P-12) por cada Strong.
- Quien retoma: nerv-orquestador.

### [2026-10-15 22:05] nerv-orquestador → nerv-qa T-093 (A)
- Gate PASS (A, 339 líneas, proof of red OK, suite verde). QA en worktree propio sobre `release/1.0.0-rc2`; diff `main...feat/t093-nombres` (7 archivos). Entregable `engram/qa/T-093.md` (§Plan · §GAP · §Casos · §Defectos).
- Pendiente: gate run 3 de T-092/094/095/096/097 (plan OK; handoffs con índice P-1) → QA Strong de a dos, luego nerv-verifier.
- Quien retoma: nerv-orquestador.

### [2026-10-15 21:45] Integración T-092..T-097 + gate P-12 + decisión del PO sobre planes
- Integración en `release/1.0.0-rc2` (merge en orden T-092→T-093→T-095→T-094→T-096→T-097; conflictos resueltos en worker.py, ui.py, release_mac.sh, build_windows.ps1, requirements, tests). Dos fixes de integración: gate D-14 avisa en `--dry-run` y aborta en el release real; ruta one-dir de T-092 conservada. Locks regenerados con qrcode. Suite 684 passed / 2 skipped.
- `nerv-gate.sh` por ticket (return handoffs en `engram/qa/handoffs/`): T-093 PASS (A, proof of red OK). T-092/094/095/096/097 nivel S computado → REJECTED PLAN_GATE_MISSING (estampa por sección). El Orquestador NO estampó por su cuenta; el PO revisó los 5 planes con sus desvíos y los aprobó uno por uno en sesión → estampa «ratificada por el PO» en QUÉ/CÓMO, gate re-corrido.
- Próximo paso: QA Strong (nerv-qa) de los 5 + QA Advisory de T-093, luego nerv-verifier (P-11/P-12) para los Strong; merge a main y push.
- Quien retoma: nerv-orquestador → nerv-qa.

### [2026-10-15 20:10] Retoma sesión (rekordbox-extractor-e7) — coordinación con la sesión anterior
- Hallazgo: la sesión anterior (`rekordbox-extractor-ad`) sigue viva con los 6 agentes nerv-desktop de T-092..T-097 commiteando en `feat/t09x` (no quedaron a medias). PO decide: dejarla terminar; esta sesión integra, QA y cierra. Se le pidió por mensaje cross-session no lanzar trabajo nuevo y quedar idle.
- Lista de pendientes del PO (TEC-05/06/08/09/10/12/16, D-16..D-26, TEC-21) mapeada 1:1 a T-092..T-096 ya aprobados: sin brainstorm nuevo. Altas: T-098 (TEC-20, Windows) y T-099 (TEC-14, 1.1).
- Próximo paso: al quedar idle la otra sesión → suite por rama → merge en orden T-092 → T-093 → T-095 → T-094 → T-096 → T-097 en `release/1.0.0-audit` → QA por ticket → main → push.
- Quien retoma: nerv-orquestador.

### [2026-10-15 19:30] CIERRE DE SESIÓN
- Hecho hoy: T-086 auditoría pre-release en 4 patas (Apple, seguridad, legal, técnica; informes en engram/audit/) → corte aprobado por el PO → T-087..T-091 implementados en worktrees paralelos, integrados en release/1.0.0-audit, QA formal (T-087 rechazada 1 vez por bit de ejecución, re-aprobada), mergeado a main (4922586). PySide6 6.12/FFmpeg 9.0.1, drop de fps resuelto, aborts, copia atómica, textos legales, release firmable. T-092..T-097 lanzados al cierre (ver _state).
- Próximo paso: revisar las 6 ramas T-092..T-097 (pueden estar incompletas), completar, integrar, QA, push. PO: cert Developer ID, datos legales, renombrar repo, liberar disco.
- Quien retoma: nerv-orquestador → nerv-desktop / nerv-qa.

### [2026-10-15 14:00] T-086 auditoría pre-release → 4 agentes en paralelo
- Pedido del PO: auditoría en 4 patas (Apple, seguridad, legal, técnica/rendimiento). Síntoma reportado: caída de fps al agregar muchas listas nuevas hasta que terminan de abrirse.
- Entregable: `engram/audit/T-086_{apple,seguridad,legal,tecnica}.md`, solo lectura, sin código.
- Quien retoma: nerv-orquestador consolida hallazgos con el PO.

### [2026-10-15 13:00] CIERRE DE SESIÓN (mini)
- Hecho hoy: QA formal de T-080..T-085 (3 nerv-qa en paralelo, 6 APROBADO, Done consolidado por nerv-qa, backlog-check OK); evidencia Cocoa de T-083 archivada; deuda D-10..D-13 registrada; D-11 resuelta (dedupe por archivo físico en el XML exportado, test con mutación). PO pusheó main y confirmó numeración «como ahora».
- Próximo paso: PO crea certificado Developer ID + perfil notarytool → build firmado/notarizado + D-10 → tag v1.0.0.
- Quien retoma: nerv-orquestador → nerv-desktop (T-025/T-026, D-10).

### [2026-10-15 18:00] CIERRE DE SESIÓN
- Hecho hoy: release 1.0.0 armado (Acerca de/licencias/aviso legal), Rekordbox solo por XML oficial (sin pyrekordbox, ADR-004), reparar enlaces del XML + exportar XML importable (T-081), fix crash al exportar a disco desconectado, onda nueva con animación, streaming/duplicados en XML, investigación de mercado (reports/, doc compartible). Todo mergeado a main local.
- Próximo paso: PO prueba con su XML real de Rekordbox 7 → push → tag v1.0.0 + release; QA formal (nerv-qa) de T-080..T-085.
- Quien retoma: nerv-orquestador → nerv-qa (T-080..T-085) y nerv-desktop (T-025/T-026).

### [2026-10-13] CIERRE (mini, P-5) · T-067 + T-079
- Hecho: columna Key·BPM (Rekordbox BPM/100 + Key.ScaleName, Traktor INFO@KEY/TEMPO@BPM; oculta bajo ~920 px) y chequeo de updates con CA de certifi (verificación SSL siempre activa). Gate oficial PASS con proof of red; QA con artefactos `engram/qa/T-067.md`, `T-079.md`; merge a main a2f406f. Push: lo hace el PO.
- Hallazgo: el repo público no tiene releases/tags → `/releases/latest` = 404; el aviso de «Nueva versión» no funcionará hasta publicar uno (T-025).
- Próximo paso: T-025 (`.app` + primer release). Quien retoma: nerv-orquestador → nerv-desktop.

### [2026-10-12] nerv-orquestador → nerv-qa T-079 (A) + T-067 (A)
- `nerv-gate.sh` (~/Documents/NERV/bin) PASS con NERV_TEST_CMD: files == diff (22), nivel A computado, handoff P-1 completo, **proof of red OK**, suite verde. Primer gate oficial del proyecto en esta máquina.
- Notas: `/releases/latest` da 404 porque el repo público no tiene releases ni tags (verificado con curl) → no es defecto de T-079; anotado para T-025. T-067 oculta la columna con fila < 560 px (ventana ≲ 920 px) para cumplir el criterio 4; con un solo dato muestra «9A · —» / «— · 128» (interpretación del implementador).
- Entrega: veredicto por ticket + **`engram/qa/T-079.md` y `engram/qa/T-067.md`** con §Plan · §GAP · §Casos · §Defectos (obligatorio, P-4).
- Archivos a leer: `engram/03_backlog.md` (T-067, T-079) · diff `main..HEAD` en `feat/menores` · `engram/evidence/T-067/*.png`, `engram/evidence/T-079_ssl_check.txt`.

### [2026-10-12] nerv-orquestador → nerv-desktop T-079 → T-067 · Niv A (ambos)
- PO: «encará los menores». Rama nueva `feat/menores` desde main (6328dfb + cierre a1a5937). Recon del Orquestador con datos reales en las filas del backlog (campos de pyrekordbox verificados con `dir()`; certifi no instalado).
- Entrega: T-079 primero (chico), después T-067. Advisory: criterios del backlog = plan. TDD, commits chicos, capturas en T-067. **Pedido explícito a QA después: `engram/qa/<T-ID>.md`** (lección de este cierre).
- Archivos a leer: `engram/03_backlog.md` (T-067, T-079) · `update_checker.py`, `requirements.txt`, `rb_exporter.spec` · `preview_worker.py`, `db.py`, `traktor_db.py`, `preview_card.py`, `ui.py` (`_make_row_widget`), `ui_components.py` (FileRow), `CLAUDE.md` · `~/.nerv/playbook.md` §Desktop.
- Se espera (retorno estructurado): estado · archivos tocados · riesgos · cómo probar · capturas.

### [2026-10-12] CIERRE DE SESIÓN (P-5)
- Hecho: reskin «Mezcla Cálida» completo (T-061..T-066, T-068..T-078: header/footer/playlists/vista previa/diálogos, Sora, relocate por playlist, crash Traktor→Rekordbox, tema 22× más rápido, suite 8 min → ~1 min) con QA en todos; merge a main 6328dfb, push hecho por el PO (el clasificador de permisos bloqueó el push del Orquestador).
- Próximo paso: T-025 (buildear y probar el `.app` con todo el reskin) y regularizar QA de T-027/T-029.
- Quien retoma: nerv-orquestador → nerv-desktop (T-025).

### [2026-10-12] nerv-orquestador → nerv-desktop T-078 · Niv A
- T-077 Done (QA, 7ff4167). QA halló que el tilde PNG puede impedir el arranque (temp no escribible) → T-078 antes del merge (decisión del Orquestador: no se mergea un fallo de arranque introducido en la rama).
- Entrega: T-078 (criterios del backlog = plan). Test primero, commit chico, suite completa. Dejar «En revisión QA».
- Archivos a leer: `engram/03_backlog.md` (T-078) · `styles.py` (`_tick_url`, `load_qss`, `apply_theme`) · `main.py`.

### [2026-10-12] nerv-orquestador → nerv-qa T-077 · Niv A
- Gate P-12.1 PASS (Orquestador): tree limpio, suite verde, ini intacto; captura de Sí/No revisada («No» por defecto en confirmación destructiva).
- Para la auditoría: `dialogs.py` nuevo reemplaza los helpers estándar de QMessageBox en `ui.py` y `app_logging.py` (verificar que no quede ninguno). El tilde del checkbox se genera como PNG en el temp del sistema desde `load_qss` → verificar que sea robusto (temp no escribible, bundle) y que no dependa de estado previo. Stubs de 4 tests adaptados a `ui.dialogs.*`: verificar que no se debilitó ninguna aserción.
- Archivos a leer: `engram/03_backlog.md` (T-077) · diff `61f5ca6..HEAD` · `engram/qa/T-077/*.png`.
- Se espera: veredicto con evidencia por criterio.

### [2026-10-12] nerv-orquestador → nerv-desktop T-077 · Niv A
- T-074/T-075/T-076/T-066 Done (QA, ff91170). PO: «hacé el ticket chico» antes del merge.
- Entrega: T-077 (Advisory: criterios del backlog = plan). TDD, commits chicos, capturas dark+light, suite completa. Dejar «En revisión QA».
- Archivos a leer: `engram/03_backlog.md` (T-077) · `ui.py` (QMessageBox, página de ajustes, diálogo de relocate), `qss/app.qss`, `icons.py` · `~/.nerv/playbook.md` §Desktop.
- Se espera (retorno estructurado): estado · archivos tocados · cómo probar · capturas.

### [2026-10-12] nerv-orquestador → nerv-qa T-076 (S) + T-074 (A) + T-075 (A) + T-066 (A)
- Gate P-12.1 PASS (Orquestador): tree limpio, suite completa verde en 1:48 con `-n 4` (antes 6–8 min), `.rbe_settings.ini` intacto, pytest-xdist 3.8.0 instalado.
- T-076: crash del PO al cambiar Traktor→Rekordbox; implementador lo reprodujo 6/6 y lo atribuye a `itemAt`+`setParent(None)` en `_clear_playlist_area` (repro mínimo PySide6 en evidencia). Verificar: el test falla sin el fix (mutación), la ráfaga de repro en evidencia, y búsqueda del mismo patrón en todo el proyecto. Salvedad declarada: stack no idéntico al del PO.
- T-074: cambio de PO (sin nota, filas 38 px). T-066: verificar capturas de cada modal/QMessageBox y el indicador del menú. Observación del Orquestador: QMessageBox muestra «Yes/No» en inglés (preexistente, viola la convención rioplatense de CLAUDE.md) → se abrirá ticket aparte, no es defecto de T-066.
- T-075: verificar que no se debilitó ni borró ningún test (diff de tests/), qué tests quedaron en proceso frío y por qué, y que el aislamiento de binding se mantiene.
- Archivos a leer: `engram/03_backlog.md` (T-074, T-075, T-076, T-066) · `engram/plans/T-061.md` (decisión del PO sobre la nota) · diff `0f8e82d..HEAD` · `engram/plans/design/evidence/T-076_*`, `T-074_*`, `T-066_*` · `CLAUDE.md` §Tests.
- Se espera: veredicto por ticket con evidencia, defectos con archivo:línea.

### [2026-10-12] nerv-orquestador → nerv-desktop T-075 → T-074 → T-066 · Niv A (los tres)
- T-065 Done (QA, 3dbbe2a). PO: la nota en segunda línea queda; «metele» a D-09 (→ T-075) y «dale» a T-066 + T-074 + indicador del auto-resolver (sumado a T-066).
- Entrega, en orden: T-075 (suite rápida, primero porque acelera lo demás) → T-074 → T-066. Advisory: los criterios del backlog son el plan. TDD donde haya lógica, commits chicos por ticket, capturas dark+light en T-074/T-066. Dejar los tres «En revisión QA».
- Archivos a leer: `engram/03_backlog.md` (T-075, T-074, T-066, D-09) · `tests/` (conftest, `_window_boot.py`, patrón de subproceso de T-033) · `preview_card.py` · `ui.py` (página de ajustes, menú Mantenimiento, diálogos) · `engram/plans/T-061.md` (tokens y reglas transversales) · `~/.nerv/playbook.md` §Desktop.
- Se espera (retorno estructurado): estado · archivos tocados · riesgos/caveats · cómo probar · capturas · cifras de T-075.

### [2026-10-12] nerv-orquestador → nerv-qa T-065 · Niv S · re-auditoría (iteración 1)
- Fix entregado (8aaae8e, 673eae8, 1035a85): FORMATO visible y alineado (también con scroll interno), artista alineado entre sana/rota; tests nuevos con rojo previo (`T-065_qa1_rojo.txt`). Cambio visual: en filas rotas la nota va bajo el título (fila de 48 px). Gate rápido del Orquestador: tree limpio, tests de preview verdes, ini intacto; suite completa corrida por el implementador.
- Entrega: re-auditar SOLO el defecto de `engram/qa/T-065.md` y la deuda de alineación, más no-regresión de lo ya verificado. Registrar veredicto.
- Archivos a leer: `engram/qa/T-065.md` · diff `8a9c6c3..HEAD` · capturas `T-065_after_*`.

### [2026-10-12] nerv-orquestador → nerv-desktop T-065 · Niv S · iteración 1 de 2 (rechazo QA)
- QA: T-072 APROBADO (Done); T-065 RECHAZADO (`engram/qa/T-065.md`): «FORMATO» invisible en la cabecera de columnas (`preview_card.py:111-118`, ancho 0 + stretch 0 + política Ignored) y sin test que afirme las 3 columnas.
- Entrega: (1) test que falle primero afirmando que las 3 etiquetas de la cabecera son visibles con ancho > 0 y alineadas con sus columnas de fila; fix. (2) Incluido a pedido del Orquestador (deuda no bloqueante de QA): el artista de las filas rotas debe alinear con el de las sanas (hoy x≈1218 vs x≈1410 en `T-065_after_dark_980_expanded.png`; la nota «· archivo no encontrado» + ícono no deben correr la columna) — test de geometría. Capturas regeneradas dark+light 980/820. Suite completa una vez al final.
- Archivos a leer: `engram/qa/T-065.md` · `preview_card.py`, `ui_components.py` (FileRow) · `engram/plans/T-061.md` (decisiones del PO de T-065, D6).
- Se espera (retorno estructurado): estado · archivos tocados · cómo probar · capturas.

### [2026-10-12] nerv-orquestador → nerv-qa T-065 + T-072 · Niv S
- T-073 Done (QA en worktree, a17b09f). Gate P-12.1 de T-065/T-072 PASS (Orquestador): tree limpio, suite completa verde, `.rbe_settings.ini` intacto. Agente implementador detenido.
- Para la auditoría: decisiones del PO sobre T-065 (D1 botonera POR CARPETA con scope de T-073 + global en menú; D2–D6) al final de `engram/plans/T-061.md`. Excepción P-18 aceptada para los tests de caracterización (cada uno con mutación). Declarado por el implementador: el guard de T-029 no reproduce el crash en PySide6 6.11.1/macOS (mejor esfuerzo). Observación del Orquestador: la cabecera de columnas de la tarjeta no muestra «FORMATO» (D6 lo pide).
- Archivos a leer: `engram/plans/T-061.md` (§T-065, CÓMO — T-065, decisiones del PO) · `engram/03_backlog.md` (T-065, T-072) · diff `bc254d8..2740a5e` · `engram/plans/design/evidence/T-065_*`, `T-072_*`.
- Se espera: veredicto por ticket con evidencia por criterio, defectos con archivo:línea.

### [2026-10-12 18:30] nerv-orquestador → nerv-desktop T-073 (S) → T-065+T-072 (S) · CÓMO T-073 + ajuste CÓMO T-065 + implementación
- PO decidió D1 de T-065 distinto a lo propuesto: botonera POR CARPETA (alcance = esa playlist) + global en el menú. Requiere relocate con scope → T-073 nuevo (escribe sobre la librería del usuario). D2–D6 sí; T1–T11 y excepción P-18 aprobadas.
- Entrega, en orden: (1) CÓMO de T-073 con writing-plans en `engram/plans/T-073.md` (## QUÉ: «No requerido (Strong)»), estampado; (2) ajustar `## CÓMO — T-065` a D1 y re-estampar; (3) implementar T-073; (4) implementar T-065+T-072. Volver al Orquestador después de (2) SOLO si el plan de T-073 necesita una decisión del PO; si no, seguir.
- Archivos a leer: `engram/plans/T-061.md` (§T-065, CÓMO — T-065, decisiones del PO al final) · `engram/03_backlog.md` (T-065, T-072, T-073) · `engram/02_architecture.md` (ADR-001, ADR-002) · `relocate_core.py`, `traktor_relocate.py`, `rekordbox_relocate.py`, `ui.py` (`_start_relocate`) · `~/.nerv/playbook.md` §Desktop.
- Se espera (retorno estructurado): estado · archivos tocados · riesgos/caveats · cómo probar · capturas.

### [2026-10-12 17:45] nerv-orquestador → nerv-desktop T-065 (+T-072) · Niv S · fase CÓMO (P-19.2)
- T-064 Done (QA, 7509152). PO: «dale» a T-065. Se pliega T-072 (auto-avance perdido durante el re-render de tema) porque vive en el mismo código (`_clear_preview_layout`, `_play_order`, cola de render).
- Entrega: SOLO el CÓMO de T-065 (+ tarea para T-072) con `superpowers:writing-plans`, como `## CÓMO — T-065` al final de `engram/plans/T-061.md`, estampado. Sin código. Respetar: estilo D de filas rotas (T-071, ya implementado en `row_blocks.py`/`FileRow`), sin regresión de T-029 ni de T-070 (re-encolado al cambiar tema, 185 ms). Decisiones para el PO como D1..Dn; técnicas como T1..Tn.
- Archivos a leer: `engram/plans/T-061.md` (QUÉ §Estructura → Vista previa, §T-065, §Correcciones ronda 1, decisiones previas) · `engram/03_backlog.md` (T-065, T-072, T-029) · `engram/plans/T-070.md` · `engram/plans/design/T-061-mezcla-calida.dc.html` (main) · `ui.py` (`_build_right_col`, `_queue_group`, `_make_row_widget`, `_clear_preview_layout`, `_on_track_finished`), `ui_components.py` (FileRow), `row_blocks.py`, `preview_worker.py` · `~/.nerv/playbook.md` §Desktop.
- Se espera (retorno estructurado): estado · archivos tocados · riesgos/caveats · decisiones para el PO.

### [2026-10-12 17:10] nerv-orquestador → nerv-qa T-064 · Niv S
- Gate P-12.1 PASS (Orquestador): tree limpio, suite verde (311), `.rbe_settings.ini` intacto, captura 980 dark revisada (numeración de dos estilos, filas planas, buscador, «vacía»). Suite tarda ~5–6 min por subprocesos de Qt → deuda D-09, no defecto de T-064.
- Archivos a leer: `engram/plans/T-061.md` (§T-064, CÓMO — T-064, decisiones del PO de T-064 al final) · `engram/03_backlog.md` (T-064) · diff `fdd26ff..HEAD` · `engram/plans/design/evidence/T-064_*`.
- Se espera: veredicto con evidencia por criterio, defectos con archivo:línea.

### [2026-10-12 15:40] nerv-orquestador → nerv-desktop T-064 · Niv S · fase implementación
- CÓMO estampado (6a5a9e3). PO: D1–D4 sí; D5 = carpetas sin checkbox (spec/CLAUDE.md corregidos). T1–T8 aprobadas; excepción P-18 para 3 tests de caracterización.
- Entrega: Tasks 0–5 del CÓMO de T-064 en `feat/reskin`, ejecución INLINE, TDD, commits chicos, evidencia dark+light. Dejar T-064 «En revisión QA».
- Archivos a leer: `engram/plans/T-061.md` (§T-064, CÓMO — T-064, decisiones del PO al final) · `engram/03_backlog.md` (T-064) · `~/.nerv/playbook.md` §Desktop.
- Se espera (retorno estructurado): estado · archivos tocados · riesgos/caveats · cómo probar · capturas.

### [2026-10-12 15:00] nerv-orquestador → nerv-desktop T-064 · Niv S · fase CÓMO (P-19.2)
- T-063/T-068 Done (QA, 7d2498d). PO revisó la app en vivo y decidió la numeración (opción 3).
- Entrega: SOLO el CÓMO de T-064 con `superpowers:writing-plans`, como `## CÓMO — T-064` al final de `engram/plans/T-061.md`, estampado. Sin código. Decisiones para el PO como D1..Dn, técnicas como T1..Tn.
- Archivos a leer: `engram/plans/T-061.md` (QUÉ §Estructura → Columna izquierda, §T-064, decisiones del PO incl. la de T-064) · `engram/03_backlog.md` (T-064) · `engram/plans/design/T-061-mezcla-calida.dc.html` (aside) · `ui.py` (`_build_left_col`, `_build_playlists_header`, `_build_playlist_scroll`, `_load_playlists`, `_update_order_numbers`), `ui_components.py` (PlaylistCard, PlaylistGroup) · `~/.nerv/playbook.md` §Desktop.
- Se espera (retorno estructurado): estado · archivos tocados · riesgos/caveats · decisiones para el PO.

### [2026-10-12 14:20] nerv-orquestador → nerv-qa T-063 (S) + T-068 (S)
- Pendiente desde el 2026-10-11: T-063/T-068 quedaron «En revisión QA» y se frenaron para la prueba manual del PO (OK del PO: «el resto está perfecto»; sus pulidos → T-069/T-071, ya Done). Gate P-12.1 del Orquestador PASS al entregar (cc24364..481de4e) y suite verde hoy.
- Ojo: el código posterior (T-069/T-070/T-071) tocó `footer.py`, `ui.py` y QSS → auditar los criterios de T-063 contra el HEAD actual, no solo contra 481de4e. T-068: excepción P-18 aceptada por el Orquestador (no-vacuidad por mutación, 8 rojos en `evidence/T-068_mutacion.txt`).
- Archivos a leer: `engram/plans/T-061.md` (§T-063, CÓMO — T-063, decisiones del PO) · `engram/03_backlog.md` (T-063, T-068) · diff `d39570a..481de4e` + estado actual · `engram/plans/design/evidence/T-063_*`, `T-068_mutacion.txt`.
- Se espera: veredicto por ticket con evidencia por criterio.

### [2026-10-12 13:30] nerv-orquestador → nerv-qa T-069 (A) + T-070 (S) + T-071 (A)
- Gate P-12.1 PASS (Orquestador) para los tres: tree limpio, suite verde, `.rbe_settings.ini` md5 intacto, sin referencias a Fraunces. Capturas revisadas (header Sora, píldora de rotos, bloques D en housepost/techDeFondo).
- Para la auditoría: T-070 — PO aceptó 185 ms (registrado en `engram/plans/T-070.md`); el implementador NO mutó el guard → hacer la mutación; verificar el riesgo declarado de auto-avance de pista durante el re-render (≈cientos de ms). T-071 — no existe diálogo «Acerca de» (no aplica); commits sin rojo aislado (red-first declarado).
- Archivos a leer: `engram/03_backlog.md` (T-069, T-070, T-071) · `engram/plans/T-070.md` · `engram/plans/T-061.md` §Correcciones del PO — ronda 1 · diff `743c125..HEAD` · `engram/plans/design/evidence/T-069_*`, `T-070_*`, `T-071_*`.
- Se espera: veredicto por ticket con evidencia por criterio, defectos con archivo:línea.

### [2026-10-12 12:10] nerv-orquestador → nerv-desktop T-071 · Niv A
- T-069/T-070 entregados (gate PASS: tree limpio, suite verde, ini intacto; T-070 4130 → 185 ms, aceptación del PO pendiente). QA de T-069/T-070/T-071 se corre junta al final para no auditar con la rama en movimiento.
- Entrega: T-071 (Advisory: criterios del backlog = plan): Fraunces → Sora; filas rotas en bloque agrupado (opción D); marca visible «List Buddy». Migrar `engram/plans/design/capture.py` a ini temporal (caveat de T-070).
- Archivos a leer: `engram/03_backlog.md` (T-071) · `engram/plans/T-061.md` §Correcciones del PO — ronda 1 · `engram/plans/design/` (canvas no accesible: la spec escrita es la fuente) · `fonts/README.md`, `styles.py`, `qss/app.qss`, `ui.py`, `ui_components.py`, `rb_exporter.spec` · `~/.nerv/playbook.md` §Desktop.
- Se espera (retorno estructurado): estado · archivos tocados · riesgos/caveats · cómo probar · capturas.

### [2026-10-12 10:00] nerv-orquestador → nerv-desktop T-069 (Niv A) + T-070 (Niv S)
- PO probó la app en vivo (T-063): picker OK, «el resto perfecto». Pidió pulidos chicos (T-069) y reportó lentitud al cambiar de tema en macOS (T-070). Fuente de marca/títulos y estilo de filas rotas → opciones renderizadas en paralelo (Orquestador), NO tocar Fraunces ni el estilo de filas rotas en este handoff.
- Entrega: T-069 (Advisory: criterios = plan) y T-070 (Strong: CÓMO con writing-plans estampado en `engram/plans/T-070.md` antes de corregir; la investigación/medición previa con systematic-debugging SÍ se hace antes del plan).
- Archivos a leer: `engram/03_backlog.md` (T-069, T-070) · `footer.py`, `ui_components.py` (MaintenanceButton), `qss/app.qss`, `ui.py` (`_apply_theme`, `_retint_icons`), `styles.py` · `~/.nerv/playbook.md` §Desktop.
- Se espera (retorno estructurado): estado · archivos tocados · riesgos/caveats · cómo probar · capturas · cifras de T-070.

### [2026-10-11 23:40] nerv-orquestador → nerv-desktop T-063 · Niv S · relanzamiento Tasks 2–8
- Ejecución anterior PARCIAL (cortada por el sistema; delegaba en subagentes anidados y devolvía antes de terminar). Hecho y verificado por el Orquestador: re-estampado D4 (044a68c, ebf7af3), Task 0 (58166fc), Task 1/T-068 (2024d26; mutación 8 rojos en `evidence/T-068_mutacion.txt`; excepción P-18 aplicada). Suite verde, tree limpio. Agente anterior detenido.
- Entrega: Tasks 2–8 del CÓMO de T-063, ejecución INLINE (sin subagentes anidados, sin monitores), sin devolver el control hasta T-063 + T-068 en «En revisión QA» o un bloqueo concreto.
- Archivos a leer: `engram/plans/T-061.md` (§T-063, CÓMO — T-063 desde Task 2, decisiones del PO al final) · `engram/03_backlog.md` (T-063, T-068) · `~/.nerv/playbook.md` §Desktop.
- Se espera (retorno estructurado): estado · archivos tocados · riesgos/caveats · cómo probar · rutas de capturas.

### [2026-10-11 22:50] nerv-orquestador → nerv-desktop T-063 (+T-068) · Niv S · fase implementación
- CÓMO estampado (9a2999d). PO: D1/D2/D3/D5/D6 sí; D4 sí con cambio (0 playlists → «Exportar playlists»). T1–T8 aprobadas. Excepción P-18 aceptada para T-068 (no-vacuidad por mutación, 8 rojos).
- Entrega: ajustar el CÓMO por D4 y re-estampar; después Tasks 0–8 en `feat/reskin`, TDD, commits chicos, evidencia a 820 px dark+light, verificación manual de la onda con audio real si el test offscreen no corre. Dejar T-063 y T-068 «En revisión QA».
- Archivos a leer: `engram/plans/T-061.md` (§T-063, CÓMO — T-063, decisiones del PO al final) · `engram/03_backlog.md` (T-063, T-068) · `~/.nerv/playbook.md` §Desktop.
- Se espera (retorno estructurado): estado · archivos tocados · riesgos/caveats · cómo probar · rutas de capturas.

### [2026-10-11 22:20] nerv-orquestador → nerv-desktop T-063 (+T-068) · Niv S · fase CÓMO (P-19.2)
- T-062 Done (QA Strong, 7521dac). PO pidió seguir con T-063 (footer de A). Se pliega T-068 (test de `_set_relocate_state("idle")` en `_on_relocate_finished`, mutación viva de QA T-062).
- Entrega: SOLO el CÓMO de T-063 (+ tarea para T-068) con `superpowers:writing-plans`, como `## CÓMO — T-063` al final de `engram/plans/T-061.md`, estampado. Sin código. Decisiones para el PO como D1..Dn.
- Archivos a leer: `engram/plans/T-061.md` (QUÉ §Estructura/Footer, §T-063, decisiones del PO de T-061/T-062) · `engram/03_backlog.md` (T-063, T-068) · `engram/plans/design/T-061-mezcla-calida.dc.html` (footer) · `ui.py` (rack head, `_build_seek_row`, `_build_dest_section`, `_build_progress_section`, `_build_export_widget`), `audio_player.py`, `spectro_worker.py`, `ui_components.py` (SeekBar) · `~/.nerv/playbook.md` §Desktop.
- Se espera (retorno estructurado): estado · archivos tocados · riesgos/caveats · decisiones para el PO.

### [2026-10-11 21:45] nerv-orquestador → nerv-qa T-062 · Niv S
- Gate P-12.1 PASS (Orquestador): tree limpio, diff 032b1aa..HEAD == declarados, suite verde, `.rbe_settings.ini` intacto. Capturas 820 px revisadas.
- Notas del Orquestador para la auditoría: el badge «30 rotos» de las capturas está FORZADO por `capture_t062.py` (`_set_broken_total(30)`) → el criterio del conteo real se valida por tests, no por la foto. La barra «Ver/Ayuda» es preexistente (QMenuBar en offscreen). No bloqueante (→ T-066): la acción checkable «Resolver automáticamente…» no muestra indicador cuando está apagada.
- Archivos a leer: `engram/plans/T-061.md` (§T-062 + decisiones del PO de T-062) · `engram/03_backlog.md` (T-062, D-08) · diff `032b1aa..HEAD` · `engram/plans/design/evidence/T-062_*`.
- Se espera: veredicto con evidencia por criterio, defectos con archivo:línea.

### [2026-10-11 20:55] nerv-orquestador → nerv-desktop T-062 · Niv S · fase implementación
- CÓMO estampado (ddcf551). PO: D1/D2/D3/D5 sí, **D4 NO** (auto-resolver no se persiste; Gherkin corregido). T1–T4 aprobadas por el Orquestador.
- Entrega: primero ajustar el CÓMO quitando lo de D4 y re-estampar; después ejecutar Tasks 0–7 en `feat/reskin`, TDD, commits chicos, evidencia a 820 px dark+light. Dejar T-062 «En revisión QA».
- Archivos a leer: `engram/plans/T-061.md` (§T-062, CÓMO — T-062, decisiones del PO al final) · `engram/03_backlog.md` (T-062, D-08) · `~/.nerv/playbook.md` §Desktop.
- Se espera (retorno estructurado): estado · archivos tocados · riesgos/caveats · cómo probar · rutas de capturas.

### [2026-10-11 20:30] nerv-orquestador → nerv-desktop T-062 · Niv S · fase CÓMO (P-19.2)
- T-061 Done (QA Strong, f2bb26c). PO pidió seguir con T-062 (header de A).
- Entrega: SOLO el CÓMO de T-062 con `superpowers:writing-plans`, como `## CÓMO — T-062` al final de `engram/plans/T-061.md`, estampado. Sin código. Incluir captura a 820 px de ancho (criterio de §T-062) y cierre de D-08.
- Archivos a leer: `engram/plans/T-061.md` (QUÉ §Estructura/Header, §T-062, CÓMO de T-061 como referencia de convenciones) · `engram/03_backlog.md` (T-062, D-08) · `engram/plans/design/T-061-mezcla-calida.dc.html` (header) · `ui.py` (`_build_header`, `_build_rack_head`, `_build_source_switcher`, `_build_relocate_row`) · `~/.nerv/playbook.md` §Desktop.
- Se espera (retorno estructurado): estado · archivos tocados · riesgos/caveats · decisiones que necesiten OK del PO.

### [2026-10-11 20:05] nerv-orquestador → nerv-qa T-061 · Niv S
- Gate determinista P-12.1 PASS (lo corrió el Orquestador): tree limpio, diff == declarados, suite verde. Iteración 1 devuelta por el Orquestador (Nº sin marcar 1.16:1 por `row_line` como texto; badge Exportar 1.00:1 por WA_TranslucentBackground; hueco de test) → corregida en 7ecf448 y re-medida con PIL: 6.96/7.01 y 9.10/6.10.
- Entrega: auditoría Strong contra §T-061 de `engram/plans/T-061.md` (criterios Gherkin + decisiones del PO D1–D5, sin build).
- Archivos a leer: `engram/plans/T-061.md` · `engram/03_backlog.md` (T-061) · diff `e1d9274..HEAD` en `feat/reskin` · `engram/plans/design/evidence/T-061_*`.
- Se espera: veredicto APROBADO/RECHAZADO con evidencia por criterio · defectos con archivo:línea.

### [2026-10-11 19:20] nerv-orquestador → nerv-desktop T-061 · Niv S · fase implementación
- CÓMO estampado (4c45ab4). PO aprobó D1–D5 y vetó el build (Task 6 Step 6 → test estático del spec; build real en T-025). Ejecución: subagent-driven.
- Entrega: ejecutar Tasks 0–6 del CÓMO de T-061 en `feat/reskin`, TDD (rojo primero), commits chicos, capturas antes/después en dark y light. Dejar T-061 «En revisión QA», NO «Done».
- Archivos a leer: `engram/plans/T-061.md` (QUÉ + CÓMO + decisiones del PO al final) · `engram/03_backlog.md` (T-061) · `~/.nerv/playbook.md` §Desktop.
- Se espera (retorno estructurado): estado · archivos tocados · riesgos/caveats · cómo probar · rutas de las capturas.

### [2026-10-11 18:56] nerv-orquestador → nerv-desktop T-061 · Niv S · fase CÓMO (P-19.2)
- Entrega: SOLO el plan CÓMO de T-061 con `superpowers:writing-plans`, escrito en `engram/plans/T-061.md` (sección `## CÓMO — T-061`) y estampado (aprobado por · rol · fecha). **Sin código.** El paso de elección de ejecución vuelve al Orquestador (P-9).
- Contexto: reskin «Mezcla Cálida» elegido por el PO sobre canvas renderizado (header+footer de A, cuerpo de F1, paleta cálida). Contraste de la paleta ya verificado por el Orquestador: mín. 6.24 dark / 5.24 light.
- Archivos a leer: `engram/03_backlog.md` (T-061) · `engram/plans/T-061.md` (QUÉ + §T-061) · `engram/plans/design/T-061-mezcla-calida.dc.html` · `styles.py`, `qss/dark.qss`, `qss/light.qss`, `ui.py`, `ui_components.py`, `rb_exporter.spec` · `~/.nerv/playbook.md` §Desktop.
- Se espera (retorno estructurado): estado · archivos tocados · riesgos/caveats · cómo probar.

### 2026-08-01 CIERRE (P-5) · nerv-qa → nerv-orquestador T-023 + T-024 · APROBADOS
- QA Strong APROBÓ ambos. T-023: `_boot_volume_name()` (traktor_db.py:181-225) deriva el volumen vía `diskutil info -plist /`, cacheado con `lru_cache` (1 invocación por proceso, no por pista) y con fallback si falla; `VOLUMEID` se sincroniza solo dentro de la ENTRY reparada (traktor_relocate.py:281-297). T-024: `_DARWIN_PROCESS_PATTERN` (traktor_relocate.py:96) verificado en vivo con el patrón exacto del código → PID 26702, exit 0; `-x` es full-match, sin falso positivo con `crashpad_handler`.
- Gate determinista P-12.1: PASS (declarados == `git diff --name-only`, tree limpio, 111/111 tests). Corrido por el Orquestador ANTES de gastar tokens de QA.
- Rama `feature/T-023-traktor-volume` pusheada a origin (4 commits). **PR NO abierto: `gh` sin autenticar en la Mac (P-7) → avisado al PO.** Merge a main pendiente de orden explícita del PO (P-8.4).
- Derivado: **T-027** dado de alta (falso positivo de "roto" en volúmenes externos, macOS). Lo levantó nerv-desktop durante T-023 y lo verifiqué yo con un archivo real y sano en `/Volumes/MUSIC`. NO se contó como defecto de T-023/T-024 (fuera de alcance).
- T-026 → Bloqueado (el PO decidió sacar la cuenta de Apple Developer).

### 2026-08-01 nerv-orquestador → nerv-desktop T-023 + T-024 · Niv S (ambos)
- Sesión de arranque en la Mac del PO (los "SOLO EN MAC" por fin son ejecutables). Ambos bugs CONFIRMADOS en vivo por el Orquestador antes del handoff, con evidencia dura en el backlog: T-023 → el NML real tiene 3 volúmenes (`Macintosh HD` 3965, `MUSIC` 1763 externo, `NO NAME` 36), el hardcode rompe 1763 pistas en silencio; T-024 → `pgrep -ix Traktor` da exit 1 con Traktor Pro 4 abierto (PID 26702), el guard nunca dispara en macOS.
- Entrega: rama `feature/T-023-traktor-volume` (ya creada desde main @fdbd42f), ambos tickets en la misma rama por ser el mismo módulo y ambos precondición de T-025. Commits separados por ticket (P-8.6).
- Archivos a leer: `engram/03_backlog.md` (T-023, T-024 — criterios ya actualizados con la evidencia), `engram/02_architecture.md` (ADR-001, sección encoder/VOLUME), `traktor_db.py` (`path_to_location`), `traktor_relocate.py` (`is_traktor_running`), `relocate_core.py`. NML real de referencia: `~/Documents/Native Instruments/Traktor 4.4.1/collection.nml` (SOLO LECTURA — es la colección viva del PO, jamás escribir sobre ella; para pruebas de escritura, copiar a tmp).
- Se espera (retorno estructurado P-1): estado · archivos tocados · riesgos/caveats · cómo probar. Obligatorio el round-trip contra los 3 volúmenes del NML real y la verificación en vivo de T-024 (no solo tests).
- Bloqueado aparte: T-026 (notarización) — el PO va a sacar la cuenta de Apple Developer. T-025 seguirá con firma ad-hoc.

### 2026-07-26 nerv-orquestador (hotfix directo, sin sub-agente) · T-010 revertido
- PO reportó "no logro levantar la app". Bisección con `python -c` aisló la causa: `MainWindow.nativeEvent()` (T-010) hacía `ctypes.wintypes.MSG.from_address(int(message))` sobre un puntero nativo — access violation al primer `show()`, mata el proceso entero sin excepción Python atrapable ni log.
- Arreglado directamente (no delegado, por urgencia): removidos `nativeEvent`/`_hit_test_border`/`FramelessWindowHint`/botones min-max-cerrar propios; vuelve al frame nativo de Windows. Commit `3daed1e` sobre `chore/prod-hardening`. Verificado: app abre y queda viva, 46 tests siguen verdes.
- D-06 registrada para rehacerlo seguro más adelante (candidato: `startSystemResize()`). Backlog: T-010 pasa de Done a Revertido.

### 2026-07-24 nerv-desktop → nerv-orquestador T-009 + T-010 · Niv S / A
- Retorno T-009: rama feature/relocate-rekordbox (sobre fix/relocate-export-concurrency, trae todo T-002 a T-008), commit f259ecf. rekordbox_relocate.py nuevo, reusa matching de traktor_relocate.py. Validado con NML... digo, con master.db real SOLO LECTURA (329/1043 rotos detectados) + escritura sintética contra DB de prueba (backup+retención N=5, USN incrementando, rollback ok, ANLZ con try/except).
- Retorno T-010: rama feature/custom-titlebar (desde main directo, NO tiene el relocate todavía), commit e84c3b5. Frameless Windows-only + resize nativo vía WM_NCHITTEST. No verificado interactivamente (agente no interactivo); caveat de DPI scaling sin confirmar.
- Pendiente del Orquestador: mergear ambas ramas (relocate-rekordbox + custom-titlebar) en una sola para QA, luego review de production-readiness.

### 2026-07-24 nerv-desktop → nerv-orquestador T-007 + T-008 · Niv S / A
- Retorno: rama fix/relocate-export-concurrency (desde feature/relocate-traktor), 2 commits. T-007: guard simétrico export↔relocate, botón Cancelar, progreso indeterminado + interrupción cada 250 archivos durante el walk. T-008: _no_exportados.txt por playlist con fallas, log de UI intacto.
- Caveat: si el relocate está bloqueado esperando el modal de desambiguación, Cancelar no responde hasta resolver el modal (preexistente, no tocado). El .txt de T-008 no se escribe si la exportación de esa playlist se cancela o hay disco lleno a mitad (deliberado, fuera de scope).
- Pendiente: Orquestador corre la app para verificar visualmente antes de mergear.

### 2026-07-24 nerv-orquestador → nerv-desktop T-009 (worktree aislado) · Niv S
- Entrega: implementar F-08 (relocate Rekordbox) según ADR-002 aceptado. Rama feature/relocate-rekordbox → main. Corrido en worktree separado porque T-007/T-008 sigue en curso sobre el mismo working directory.
- Archivos a leer: engram/02_architecture.md (ADR-002 completo), engram/03_backlog.md (T-009), CLAUDE.md (esquema DjmdContent/DjmdPlaylist), traktor_relocate.py + ui_components.py (RelocateDialog) + ui.py (checkbox T-003) como referencia a reusar, no duplicar.
- Se espera: estado · archivos tocados · riesgos/caveats · cómo probar (solo lectura contra master.db real si hace falta validar, sin escribir sin permiso explícito del PO).

### 2026-07-24 nerv-orquestador → nerv-desktop T-010 (worktree aislado) · Niv A
- Entrega: header/barra de título custom (frameless + drag-to-move + botones propios + resize funcionando). Rama feature/custom-titlebar → main.
- Archivos a leer: engram/03_backlog.md (T-010), ui.py (MainWindow, setup de ventana), styles.py/qss (paleta y tokens de diseño existentes para mantener consistencia visual).
- Se espera: estado · archivos tocados · riesgos/caveats (especialmente resize en modo frameless) · cómo probar.

### 2026-07-24 nerv-orquestador → nerv-desktop T-007 + T-008 · Niv S / A
- Entrega: T-007 (guard simétrico export↔relocate + botón cancelar + progreso/interrupción durante indexación) y T-008 (txt de errores por carpeta de playlist al exportar). Rama fix/relocate-export-concurrency → main. Dos commits separados, uno por ticket.
- Archivos a leer: engram/03_backlog.md (T-007, T-008), ui.py (_start_export:1736, _start_relocate, _cancel_export:1770), traktor_relocate.py (build_basename_index, RelocateWorker.run), worker.py (ExportWorker.run, missing_tracks).
- Se espera (retorno estructurado): estado · archivos tocados · riesgos/caveats · cómo probar cada uno (T-007: arrancar relocate y export en simultáneo debe bloquear con aviso; T-008: forzar un track "no encontrado" y confirmar el .txt en la carpeta correcta).

### 2026-07-24 nerv-arquitecto → nerv-orquestador T-006 · Niv S (X/Adversarial corrido)
- Retorno: ADR-002 escrito en engram/02_architecture.md (Propuesto). Usa update_content_path() de pyrekordbox (ya confirmado que actualiza DB+ANLZ), backup completo de master.db (N=5), transacción única con commit(autoinc=True) para USN, sin sync COLLECTION↔PLAYLISTS (Rekordbox liga por Content.ID, no por path).
- Puntos a decidir por el PO antes de T-007: retención N=5 (vs 10 de Traktor) por peso del .db; ANLZ NO transaccional (riesgo cosmético aceptado en vez de respaldar miles de archivos analizados).
- Nada se escribió contra el master.db real — solo inspección de código fuente de pyrekordbox.

### 2026-07-24 nerv-orquestador → nerv-arquitecto T-006 · Niv S
- Entrega: ADR-002 (relocate para Rekordbox 6, F-08) en engram/02_architecture.md, rama docs/adr-002-relocate-rekordbox → main. Fase 2 tras validar Traktor en real con el PO.
- Ya investigado (no re-descubrir): pyrekordbox 0.4.4 tiene `Rekordbox6Database.update_content_path(content, path, save=True, check_path=True, commit=True)` — actualiza `DjmdContent.FolderPath`/`OrgFolderPath`/`FileNameL` Y los archivos ANLZ (waveform/beatgrid, tag PPTH) vía `read_anlz_files`. También existe `set_local_usn()` sin uso claro documentado — el ADR tiene que resolver si hace falta llamarlo tras el update para no romper sync con Rekordbox Cloud.
- Archivos a leer: engram/01_requirements.md (F-08), engram/03_backlog.md (T-006), engram/02_architecture.md (ADR-001 completo, como referencia de formato — no copiar decisiones de NML, la DB es distinta), CLAUDE.md del repo (sección Rekordbox — esquema DjmdContent/DjmdPlaylist, R-01).
- Se espera (retorno estructurado): estado · archivos tocados (ADR-002 en 02_architecture.md) · riesgos/caveats (en particular USN y backup de SQLCipher) · cómo el PO valida antes de implementación.

### 2026-07-24 nerv-orquestador → nerv-desktop T-005 · Niv A
- Entrega: mergear fix/volume-blind-path-windows (T-004, commit cf05573) dentro de feature/relocate-traktor, y aplicar el mismo patrón de fix a find_broken_entries en traktor_relocate.py:129 (firma vieja de 2 args, tiene que pasar a 3 con volume).
- Archivos a leer: engram/03_backlog.md (T-005), traktor_db.py en main (post-fix, para copiar el patrón exacto), traktor_relocate.py:129 en feature/relocate-traktor.
- Se espera (retorno estructurado): estado · archivos tocados · riesgos/caveats · confirmación de que el NML real del PO ya no cuenta como rotos los 97/200 que T-004 resolvió, corriendo find_broken_entries.

### 2026-07-24 nerv-orquestador → nerv-desktop T-004 · Niv A (bug urgente)
- Entrega: fix de `_location_to_path()` en traktor_db.py — ignora VOLUME, confirmado contra NML real del PO (VOLUME="I:" resuelve mal en Windows). Rama nueva `fix/volume-blind-path-windows` → main.
- Archivos a leer: engram/03_backlog.md (T-004, criterios), traktor_db.py (líneas 136-218: decoders + encoder ya correcto de referencia), traktor_relocate.py:129, traktor_db.py:300.
- Se espera (retorno estructurado): estado · archivos tocados · riesgos/caveats · cómo probar (idealmente contra un path real tipo `I:\Music\...` del PO, confirmando `Path.exists()` da True tras el fix).

### 2026-07-24 nerv-desktop → nerv-orquestador T-003 · Niv S
- Retorno: implementado (traktor_relocate.py: RelocateWorker.auto_resolve; ui.py: checkbox relocate_auto_chk default OFF). Sin tests automatizados (no hay suite en el repo para este módulo); validación manual descripta en el retorno completo.
- No pudo persistir en engram vía mem_save (no disponible en su sesión) — decisión ya estaba documentada en el Addendum del ADR-001 igual.
- Pendiente: Orquestador corre la app para confirmar visualmente el checkbox antes de que el PO lo use sobre su colección real de 2090 links rotos.

### 2026-07-24 nerv-orquestador → nerv-desktop T-003 · Niv S
- Entrega: checkbox opt-in de auto-resolución para relocate Traktor, según Addendum ADR-001 (2026-07-24) en engram/02_architecture.md. Rama feature/relocate-traktor → main (misma rama que T-002, aún no mergeada).
- Archivos a leer: engram/02_architecture.md (Addendum), engram/03_backlog.md (T-003), traktor_relocate.py (RelocateWorker.run, find_candidates), ui.py (_start_relocate, _on_relocate_ask).
- Se espera (retorno estructurado): estado · archivos tocados · riesgos/caveats · cómo probar (con NML sintético con >1 candidato, checkbox ON y OFF).

### 2026-07-23 18:20 nerv-desktop → nerv-orquestador T-002 · Niv S
- Retorno: implementado en commit 4c59c8d (traktor_db.py, traktor_relocate.py nuevo, ui.py, ui_components.py, qss). Probado con NML sintético (asserts OK), no con Traktor real (no instalado acá).
- Deuda técnica registrada: D-01 (VOLUME ignorado en decoders existentes, riesgo en Windows multi-drive), D-02 (rama macOS del encoder sin verificar).
- Pendiente: Orquestador corre la app para verificar visualmente el modal/botón antes de pasar a nerv-qa.

### 2026-07-23 17:45 nerv-orquestador → nerv-desktop T-002 · Niv S
- Entrega: implementar F-07 (relocate Traktor) según ADR-001 sobre rama `feature/relocate-traktor` → `main`.
- Archivos a leer: `engram/02_architecture.md` (ADR-001 completo), `engram/03_backlog.md` (T-002), `engram/01_requirements.md` (R-01/R-02/R-03, F-07), `traktor_db.py`, `ui.py`, `ui_components.py`, `worker.py`.
- Se espera (retorno estructurado): estado · archivos tocados · riesgos/caveats · cómo probar (incluir caso con NML de Windows real, dado el caveat de ADR-001 sobre VOLUME/DIR por plataforma).

### 2026-07-23 17:10 nerv-orquestador → nerv-arquitecto T-001 · Niv S
- Entrega: ADR-001 (estrategia de backup + escritura atómica del NML + criterio de matching exacto/fuzzy + sincronización COLLECTION↔PLAYLISTS) sobre rama `docs/adr-001-relocate-traktor` → `main`. Sin implementación de código todavía.
- Archivos a leer: `engram/01_requirements.md` (F-07, pregunta #1), `engram/02_architecture.md` (Notas), `engram/03_backlog.md` (T-001), `traktor_db.py`.
- Se espera (retorno estructurado): estado · archivos tocados (ADR en 02_architecture.md) · riesgos/caveats · cómo probar/validar el ADR.

### 2026-07-23 16:51 orquestador→(ninguno aún)
- Entrega: alta del proyecto en el registry, engram creado, app verificada corriendo (venv creado, deps instaladas, ventana abre y lee 35 playlists de Rekordbox correctamente).
- Se espera: definir si T-001 pasa directo a nerv-desktop o requiere ADR de nerv-arquitecto antes (backup/escritura atómica del NML).
- Pendientes: respuesta del PO a la pregunta abierta #1 en 01_requirements.md.
