# STATE — listBuddy · actualizado: 2026-07-27 (noche)

**Sprint:** 0 — Alta del proyecto + producción
**Rama activa:** main (todo mergeado y pusheado a origin/main, commit 450c902)
**En curso:** Auditoría de production-readiness (engram/07_production_readiness.md) ejecutada casi por completo en Windows: T-017 (refactor D-05, base compartida `relocate_core.py`), T-018 (confirmación previa a escribir + backup a prueba de disco lleno + re-chequeos de seguridad + mensajes de error legibles), T-019 (botón restaurar backup), T-020 (cancelación/progreso en detección de rotos), T-021 (chequeo de actualización), D-08 (layout de botones), y T-022 (aliasing en el índice inverso de Traktor — confirmado como bug real y arreglado). Todo verificado en vivo con clicks reales por el Orquestador, no solo tests. 90 tests pytest OK.
**Bloqueos:** ninguno.
**Próximo paso sugerido:**
1. Pendiente menor: T-022 parte 3 (tests de unicode en nombres de archivo — prioridad baja).
2. **⚠️ CUANDO EL PO HAGA PULL EN SU MAC: hay 4 tickets marcados "SOLO EN MAC" (T-023 a T-026)** que no se pueden resolver ni verificar desde Windows — arrancar por ahí. Resumen: T-023 (volumen hardcodeado "Macintosh HD" en el encoder de Traktor), T-024 (detección de proceso Traktor probablemente no matchea "Traktor Pro 3"), T-025 (buildear y probar el .app real — incluye el icon.icns nunca abierto en Mac, y el punto B-1 más importante: probar que el bundle escribe bien sobre Rekordbox), T-026 (firma + notarización).
3. B-1 (Windows): buildear el `.exe` real con PyInstaller y correr el checklist de 8 pasos de engram/07_production_readiness.md — nadie lo hizo todavía, sigue siendo el único ítem que puede invalidar todo lo demás.
**Preguntas abiertas al PO:** 0
