# Métricas — listBuddy

## §Costo (P-E.7)
- 2026-10-13 · `nerv-metrics.sh`: «sin sesiones medidas para 'REKORDBOX_EXTRACTOR' en ~/.nerv/metrics» → **el hook PreToolUse de métricas no está instalado en este proyecto**; no hay costo medido de la sesión (no se estima a mano).
- 2026-10-15 · `nerv-metrics.sh`: mismo resultado, «sin sesiones medidas» → hook sigue sin instalar.
- 2026-10-15 (cierre mini) · `nerv-metrics.sh`: «sin sesiones medidas» → hook sin instalar.

## §Proceso — Sprint 1 (reskin + menores, cerrado 2026-10-13)
| Métrica | Valor | Fuente |
|---|---|---|
| Tickets auditados por QA | 19 (T-061..T-079) | 03_backlog §Veredictos QA, engram/qa/ |
| Rechazos de QA | 2 (T-065 iter. 1, T-078 iter. 1) → **10,5 %** | engram/qa/T-065.md, backlog T-078 |
| Devoluciones pre-QA del Orquestador (no cuentan como QA) | 3 (T-061, T-063, T-065-plan D1) | 05_handoff_log |
| Cycle time por ticket | — | sin timestamps de inicio/fin por ticket |
| Días en bloqueo | T-026: bloqueado desde 2026-08-01 (cuenta Apple Developer) | 03_backlog |
| Edad del backlog | — | filas sin fecha de alta |

## §Proceso — Sprint 2 (release 1.0.0, cerrado 2026-10-15)
| Métrica | Valor | Fuente |
|---|---|---|
| Tickets auditados por nerv-qa | 6 (T-080..T-085, 2026-10-15) | engram/qa/T-080..T-085.md |
| Rechazos de QA | 0 → **0 %** (deuda registrada D-10..D-13; D-11 resuelta el mismo día) | 03_backlog §Veredictos QA |
| Rondas de arreglo en revisiones SDD (no son QA) | T-080: 2 tareas con 1 ronda + 1 ola final; T-081: 3 tareas con 1–2 rondas + 1 ola final | ledgers SDD (borrados al cerrar; resumen en 06_retro) |
| Cycle time por ticket | — | sin timestamps de inicio/fin por ticket |
| Días en bloqueo | T-026: bloqueado desde 2026-08-01 (cuenta Apple Developer) | 03_backlog |
| Edad del backlog | — | filas sin fecha de alta |

- 2026-10-15 (tarde, cierre sprint 3 parcial) · §Costo: `nerv-metrics.sh` → «sin sesiones medidas» (hook PreToolUse no instalado en este proyecto). Subagentes de la sesión (tokens reportados por el harness): auditorías 4 × ~230-300k; implementación 5 × ~110-145k; QA 6 × ~70-110k. §Proceso no cierra sprint: T-087..T-091 ciclo mismo día; rechazo QA 1/5 (T-087, 1 iteración).
