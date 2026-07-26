# Handoff Log — listBuddy

> Entradas nuevas ARRIBA. Máx. 6 líneas por entrada. Al superar 30 entradas,
> el Orquestador mueve las más viejas a ~/.nerv/archive/listBuddy-handoffs-[fecha].md

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
