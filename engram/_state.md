# STATE — listBuddy · actualizado: 2026-10-16 15:10

**Sprint:** 3 — Pre-release 1.0.0 (correcciones de la auditoría T-086) → CERRADO: T-087..T-097 Done con QA formal; T-092/094/095/096/097 además con revisión de arquitectura (T-094, T-097) y verifier ciego.
**Rama activa:** `main` = `origin/main` @ 1dd79f1 (pusheado 2026-10-16 con autorización del PO) → target: tag v1.0.0. `release/1.0.0-rc2` ya mergeada (borrable).
**En curso:** nada. Tanda SEC del PO (2026-10-16): T-100 (SEC-11+SEC-16) Done con QA; T-101 Authenticode DESCARTADA por el PO (Windows irá sin firma; README documenta SmartScreen). Suite 767 passed. tests.yml corrió por primera vez en GitHub Actions tras el push (ver resultado con `gh run list`).
**Bloqueos (PO, fuera del repo):** (1) GitHub: environment `release` con regla de tag `v*`, los 5 secrets como environment secrets, ruleset de tags `v*` (creations/updates/deletions) — docs/RELEASE.md. (2) Apple: cert «Developer ID Application» (.p12) + API key de App Store Connect (Team 4GP6785MU4). (3) 5 datos legales `[A DEFINIR POR EL PO]` (el gate D-14 aborta el release hasta completarlos). (4) Python 3.14.8 local (hoy 3.14.7 → `ALLOW_OLD_PYTHON=1`). (5) Renombrar repo a `listbuddy`.
**Decisiones abiertas:** D-13 abogado · D-15 macOS mínimo 14 vs 15 · deuda D-a..D-f de T-097 (1.0.1) · nerv-arquitecto debe reescribir ADR-005 §1 (updates/deletions, sin caché).
**Deuda nueva:** D-29..D-33 (tests débiles detectados por QA/verifier, menores) · T-098 (TEC-20 instancia única, Windows) · T-099 (TEC-14 partir ui.py, 1.1).
**Sin probar:** XML real de Rekordbox 7, streaming real, Windows (lock con colorama, .ps1), workflow release.yml real (nunca corrió: primer tag), bundle con qrcode.
**Próximo paso sugerido:** PO configura GitHub + Apple → nerv-devops revisa Settings (recomendación del arquitecto) → completar datos legales → `git tag v1.0.0` → verificar borrador de Release, DMG en Mac limpia sin red → Publish.
**Preguntas abiertas al PO:** 5 (los bloqueos de arriba) + D-13/D-15.
