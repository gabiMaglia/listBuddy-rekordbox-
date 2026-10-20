# Deuda de artefactos de QA (P-4 / P-21.2)

> Tickets en Done SIN `engram/qa/<T-ID>.md`. El veredicto de nerv-qa EXISTE, pero quedó solo como
> fila con fecha en `engram/03_backlog.md` §«Veredictos QA» (más el detalle en `05_handoff_log.md`).
> Motivo: los handoffs a nerv-qa no pidieron el artefacto (lección del playbook 2026-09-27 no
> aplicada por el Orquestador). Detectado por `nerv-backlog-check.sh` en el cierre del 2026-10-12.
> No se generan artefactos retroactivos: sería inventar §Casos/§GAP que nadie escribió.
> Regla desde ahora: todo handoff a nerv-qa pide `engram/qa/<T-ID>.md` explícito.

| Ticket | Dónde está el veredicto | Motivo |
|---|---|---|
| T-001 | 03_backlog §Veredictos QA (2026-07-24) | anterior a la regla del artefacto |
| T-002 | ídem (2026-07-24) | anterior a la regla del artefacto |
| T-003 | ídem (2026-07-24) | anterior a la regla del artefacto |
| T-004 | ídem (2026-07-24) | anterior a la regla del artefacto |
| T-005 | ídem (2026-07-24) | anterior a la regla del artefacto |
| T-006 | ídem (2026-07-24) | anterior a la regla del artefacto |
| T-007 | ídem | anterior a la regla del artefacto |
| T-008 | ídem | anterior a la regla del artefacto |
| T-009 | ídem | anterior a la regla del artefacto |
| T-014 | ídem | anterior a la regla del artefacto |
| T-023 | ídem (2026-08-01) | handoff no pidió artefacto |
| T-024 | ídem (2026-08-01) | handoff no pidió artefacto |
| T-028 | ídem (2026-08-01) | handoff no pidió artefacto |
| T-061 | ídem (2026-10-11) + 05_handoff_log | handoff no pidió artefacto |
| T-064 | ídem (2026-10-12) | handoff no pidió artefacto |
| T-066 | ídem (2026-10-12) | handoff no pidió artefacto |
| T-069 | ídem (2026-10-12) | handoff no pidió artefacto |
| T-070 | ídem (2026-10-12) + engram/plans/T-070.md | handoff no pidió artefacto |
| T-071 | ídem (2026-10-12) | handoff no pidió artefacto |
| T-072 | ídem (2026-10-12) + engram/qa/T-065.md (auditado junto) | auditado en el artefacto de T-065 |
| T-073 | ídem (2026-10-12), QA en worktree | handoff pidió NO escribir engram/ (árbol en uso) |
| T-074 | ídem (2026-10-12) + engram/qa/T-076.md (lote) | auditado en lote con T-076 |
| T-075 | ídem (2026-10-12) + engram/qa/T-076.md (lote) | auditado en lote con T-076 |
| T-077 | ídem (2026-10-12); capturas en engram/qa/T-077/ | handoff no pidió artefacto .md |
| T-078 | ídem (2026-10-12, iteración 1) | handoff no pidió artefacto |
| T-101 | 03_backlog (Done 2026-10-16) | solo doc (README) + test estático, decisión explícita del PO de no firmar Windows; el Orquestador lo hizo sin nerv-qa por economía (P-E); cubierto por `test_readme_explains_unsigned_windows_build_and_smartscreen` |
| T-112 | 03_backlog (Done 2026-10-16) + PR #1 | solo fixtures de tests y entorno UTF-8 de subprocesos, sin cambios funcionales; verificado por los dos jobs de CI (macOS 900+ y windows-latest 490 verdes); el Orquestador lo mergeó sin nerv-qa por economía (P-E) |
| T-111 | 03_backlog (Done 2026-10-19) | la captura purgada de `main` sigue alcanzable en GitHub vía `refs/pull/1/head` (PR #1); solo la quita GitHub Support. Pendiente del PO: abrir el ticket de soporte o aceptar el residuo (riesgo bajo, LEG-25) |
| T-111 | 03_backlog (Done 2026-10-19) | sin nerv-qa: trabajo del Orquestador (encabezados SPDX con test `tests/test_spdx_headers_t111.py` 32/32; purga verificada con `git log --all` = 0 local y en origin/main); nivel A, verificado por la suite y CI |
| T-104 | 03_backlog (Done 2026-10-16) | sin nerv-qa: es la re-auditoría misma (3 informes en engram/audit/T-104_*.md, nerv-security + legal + técnica); su «QA» fueron las 8 correcciones derivadas (T-105..T-112), cada una con QA o deuda propia |
| fix/windows-ci-ola1 (T-099/T-098) | 03_backlog §Veredictos (2026-10-20) + merge 418aae4 | solo tests (5 archivos, +14/-9): encoding utf-8 en subprocess de tests de barandas, normalización de \r\n en el test de consola cp1252 y 2 casos de T-098 con copia viva marcados posix; el Orquestador revisó el diff (ninguna aserción borrada, mismas cantidades) y lo mergeó sin nerv-qa ni nerv-gate por economía (P-E), como T-112; la verificación es el run de CI de Windows siguiente |
