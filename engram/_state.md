# STATE — listBuddy · actualizado: 2026-10-19 21:40

**Release:** v1.0.0 publicado por la sesión A (borrador de Release creado, tag @ cebebdc, arm64 + x86_64 notarizados; 1.0.0 = legacy GPL con Ko-fi, T-122). main liberado para 1.1; antes de cada merge de código se avisa a la sesión A (rekordbox-extractor-4f).
**Sprint 5 (1.1.0 Buddy) · Ola 1** (Orquestador sesión B, agentes Opus; protocolo: gate → QA → verifier ciego en S/X):
- **T-120 Done** (capa `file_access`, mergeado aa68219, publicado). Por decisión del PO se separó: la guardia en runtime pasó a **T-124** (rama `feat/t120-file-access`, intento 3 rechazado: hilos sin atribuir y apagable sin rojo).
- **T-098** (una sola copia; worktree `../wt-t098`, rama `feat/t098-instancia-unica`): QA rechazó el intento 5 (disco lleno → «ya está abierto» falso). En curso la **última pasada** (addendum 5 del plan, sellado por el PO: aviso propio de falta de espacio, no abre). El PO pidió: «hacé una pasada más y avisame qué pasa» antes de decidir si se cierra el alcance.
- **T-099 F0** (barandas del split de ui.py; worktree `../wt-t099-f0`): QA rechazó el intento 4 (código en carpetas excluidas esquiva las barandas; step de CI después de instalar deps). En curso la última pasada; mismo criterio de informar al PO.
- **T-123** (tests inestables: `test_playlist_column` y el de 150 ms de T-106, ~1 de cada 2 suites completas rojas con agentes en paralelo): siguiente en la cola. **T-124**: pendiente.
**Agentes vivos (sesión B):** implementador T-098, implementador F0 (si se corta la sesión, retomarlos con SendMessage; si no existen, relanzar desde el artefacto `engram/qa/<T-ID>.md` de cada rama y el último addendum del plan).
**Decisiones abiertas al PO:** (1) T-098: ¿el lock 0444/0000/root sin dueño se borra solo con `os.unlink`? (recomendado sí). (2) Tras esta pasada: ¿cerrar el alcance de T-098 y F0 con lo exótico como deuda declarada?
**Proceso:** retornos al gate con campos `Status:`/`Files touched:`/`Risks:`/`How to test:` en inglés; celdas de veredicto «RECHAZADO» exactas (el gate cuenta intentos por igualdad); `NERV_TEST_CMD="python -m pytest -q -n 0 -p no:cacheprovider"`; mutaciones con `PYTHONDONTWRITEBYTECODE=1`; cada agente en su subcarpeta del scratchpad. Push: lo hace el PO (clasificador lo bloquea).
**Próximo paso:** al volver los dos implementadores → gate → QA → informar al PO el resultado → según su decisión, verifier y merge (avisando a la sesión A) → T-123 → Ola 2 (T-099 F1, F6, F7, T-114).

## CHECKPOINT 2026-10-19 (cerrado): la sesión B entregó plan/1.1.0, mergeado en main @ 0aacb8d; worktree y rama borrados. Tras el cierre de A, la sesión B (única viva) dio de alta Sprint 5 en el backlog y formalizó ADR-007/008 (commit siguiente a b6e239d).
