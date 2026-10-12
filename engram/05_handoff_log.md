# Handoff Log — listBuddy

> Entradas nuevas ARRIBA. Máx. 6 líneas por entrada. Al superar 30 entradas,
> el Orquestador mueve las más viejas a ~/.nerv/archive/listBuddy-handoffs-[fecha].md

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
