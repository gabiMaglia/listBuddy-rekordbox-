# STATE — listBuddy · actualizado: 2026-10-19 15:30

**Sprint:** 4 cerrado (T-105..T-113 Done). **Sprint 5 = 1.1.0 «Buddy: listas propias» planificado y dado de alta** (`engram/roadmap_1.1.md`, `engram/03_backlog.md` §Sprint 5: T-114..T-117, T-119, T-120; T-098/T-099 siguen en §Pendiente con las decisiones anotadas). Sin implementación todavía.
**Rama activa:** `main` (local adelantada de `origin/main` por los commits de planificación; sin push hasta que el PO lo pida). Target inmediato: tag v1.0.0. Sin otras ramas ni worktrees. Repo `gabiMaglia/listbuddy`.
**En curso:** nada. Suite 909+ passed; CI Tests verde en macOS y Windows @ 277e566+.
**Decisiones tomadas (PO, sesión B 2026-10-19):** ADR-007 (split de `ui.py` en 6 capas, modelos Qt reutilizables) y ADR-008 (sin Mac App Store en 1.1) ACEPTADOS en `02_architecture.md`; las 11 decisiones de roadmap_1.1.md §3 ratificadas (layout C con filas de fuente apilables ≤ 9 y splitter; listas planas; `.nml` suelto; sin undo; segmented «Listas | Buddy»; mezclar fuentes OK; reescribir aserciones F8/F9 OK; peor tick < 50 ms; paridad por capturas; camino crítico a Buddy primero; T-120 file_access). Tabla Stack de 02_architecture corregida (decía PyQt6/pyrekordbox).
**Bloqueos (PO, fuera del repo):** (1) GitHub: environment `release` + ruleset de tags `v*` (docs/RELEASE.md). (2) Apple: cert «Developer ID Application» + API key de App Store Connect. (3) Polar: alta como MoR, producto USD 9 y pegar el enlace real (T-110). (4) Opcional: ticket a GitHub Support para quitar `refs/pull/1/head`.
**Decisiones abiertas:** D-13 abogado (solo relevante si en 1.2 se reabre la App Store) · T-098 alcance macOS (sumado como criterio 4 en roadmap, falta copiarlo a la fila).
**Sin probar:** build real de Windows (`build_windows.ps1`), release.yml real (primer tag), XML real de Rekordbox 7.
**Próximo paso sugerido:** (1.0) PO: cert Developer ID + API key → ensayo local de release_mac.sh → GitHub environment `release` + ruleset + secrets → Polar → `git tag v1.0.0` → verificar borrador y DMG en Mac limpia → Publish. (1.1) Arrancar T-099 F0 (barandas + codemod) con nerv-desktop en worktree propio; en paralelo T-098 y T-120 (independientes). Orden completo en roadmap_1.1.md §2.
**Preguntas abiertas al PO:** 3 (bloqueos 1-3). ¿Push de los commits de planificación a origin/main?

## CHECKPOINT 2026-10-19 (cerrado): la sesión B entregó plan/1.1.0, mergeado en main @ 0aacb8d; worktree y rama borrados. Tras el cierre de A, la sesión B (única viva) dio de alta Sprint 5 en el backlog y formalizó ADR-007/008 (commit siguiente a b6e239d).
