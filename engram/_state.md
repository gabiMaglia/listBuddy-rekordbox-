# STATE — listBuddy · actualizado: 2026-07-26

**Sprint:** 0 — Alta del proyecto + definición de sprint 1
**Rama activa:** main (mergeado y PUSHEADO a origin/main, commit ea6f99c — autorizado explícitamente por el PO)
**En curso:** T-001 a T-016 Done/verificados. Header custom rehecho de forma segura (T-016, `startSystemResize`, sin ctypes) y verificado en vivo. Pase de diseño T-015 (botones cerrar en preview, lista compacta, pause button color) + ícono recoloreado (T-014) + fix de elide en nombres largos de playlist, todo verificado en vivo por el Orquestador. 46 tests pytest OK, compila todo.
**Bloqueos:** ninguno.
**Próximo paso sugerido:** Auditoría completa hecha — engram/07_production_readiness.md. Arrancando fixes de Windows (T-017 a T-022, ver 03_backlog.md). **⚠️ CUANDO EL PO HAGA PULL EN SU MAC: hay 4 tickets marcados "SOLO EN MAC" (T-023 a T-026) que no se pueden resolver ni verificar desde Windows — arrancar por ahí.** Resumen: T-023 (volumen hardcodeado "Macintosh HD" en el encoder de Traktor), T-024 (detección de proceso Traktor probablemente no matchea "Traktor Pro 3"), T-025 (buildear y probar el .app real, incluye el icon.icns nunca abierto en Mac), T-026 (firma + notarización).
**Preguntas abiertas al PO:** 0
