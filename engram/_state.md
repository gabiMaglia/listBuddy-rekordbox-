# STATE — listBuddy · actualizado: 2026-07-26

**Sprint:** 0 — Alta del proyecto + definición de sprint 1
**Rama activa:** chore/prod-hardening → target: main (sobre integration/relocate-all; NADA pusheado ni mergeado)
**En curso:** T-001 a T-009 Done (QA), confirmados funcionando. **T-010 (header custom) revertido 2026-07-26**: crasheaba la app entera al arrancar (`nativeEvent`/ctypes leyendo un MSG nativo de Windows — access violation, QA no lo agarró porque solo corrió `py_compile`, no lanzó la app). Aislado y arreglado por el Orquestador (commit `3daed1e`): vuelve al frame nativo de Windows. App verificada corriendo de nuevo + 46 tests pytest verdes tras el fix.
**Bloqueos:** ninguno.
**Próximo paso sugerido:** (1) decidir merge de `chore/prod-hardening` → main (ya sin T-010, o rehacerlo seguro más adelante vía `startSystemResize()`, ver D-06), (2) probar el .exe empaquetado real antes de distribuir (clave SQLCipher en escritura, sin verificar), (3) D-02/D-05/D-06 quedan como deuda, sin apuro.
**Preguntas abiertas al PO:** 0
