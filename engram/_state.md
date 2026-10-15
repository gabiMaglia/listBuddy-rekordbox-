# STATE — listBuddy · actualizado: 2026-10-15 13:00

**Sprint:** 2 — Release 1.0.0 → CERRADO (T-080..T-085 Done con QA formal 2026-10-15; D-11 resuelta)
**Rama activa:** `main` (2 commits adelante de origin: veredictos QA + fix D-11) → target: release v1.0.0
**En curso:** nada.
**Bloqueos:** T-026: el PO tiene cuenta Apple Developer; falta certificado «Developer ID Application», contraseña de app y `notarytool store-credentials` (pasos dados al PO). `gh` sin autenticar.
**Deuda abierta:** D-10 (verificar el `.app` del build de release: sin pyrekordbox, settings fuera del bundle) · D-12 (menores) · D-13 (revisión jurídica del DISCLAIMER antes de cobrar).
**Sin probar:** XML real de Rekordbox 7 (reparar, exportar, importar en Rekordbox), pistas de streaming reales, menús de Rekordbox en español, Windows.
**Próximo paso sugerido:** PO completa Apple → `DEVELOPER_ID=… NOTARY_PROFILE=listbuddy scripts/release_mac.sh` + cerrar D-10 sobre ese `.app` → push → tag v1.0.0 + release en GitHub.
**Preguntas abiertas al PO:** 0
