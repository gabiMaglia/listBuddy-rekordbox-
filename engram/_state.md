# STATE — listBuddy · actualizado: 2026-10-19 11:20

**Sprint:** 4 — Re-auditoría T-104 (Nivel 0 + Nivel 1) → CERRADO: T-105, T-106, T-107, T-108, T-109, T-110, T-111, T-112 Done (QA formal; T-105/T-106/T-108 además con verifier ciego, nivel S).
**Rama activa:** `main` = `origin/main` @ 4051929 (historia reescrita el 2026-10-19: captura de rekordbox purgada; backup `~/Desktop/listBuddy-pre-purge-2026-10-19.bundle`, borrable cuando el PO lo confirme) → target: tag v1.0.0. Sin otras ramas locales ni remotas.
**En curso:** nada. Suite 909+ passed; CI Tests verde en macOS y Windows (job `windows-latest` nuevo).
**Bloqueos (PO, fuera del repo):** (1) GitHub: environment `release` + ruleset de tags `v*` (docs/RELEASE.md). (2) Apple: cert «Developer ID Application» + API key de App Store Connect. (3) Polar: alta como MoR, producto USD 9 y pegar el enlace real (T-110). (4) Opcional: ticket a GitHub Support para quitar `refs/pull/1/head` (historia vieja con la captura, riesgo bajo).
**Decisiones abiertas:** D-13 abogado · T-102 Mac App Store (1.1) · T-098 instancia única Windows · T-099 partir ui.py / virtualizar la lista (1.1) · pata Windows en release.yml + attestation (deuda T-108).
**Sin probar:** build real de Windows (`build_windows.ps1` nunca corrió en Windows; solo el job de tests), release.yml real (primer tag), XML real de Rekordbox 7.
**Próximo paso sugerido:** PO configura GitHub + Apple + Polar → `git tag v1.0.0` → verificar borrador de Release y DMG en Mac limpia → Publish. En paralelo, primer build manual de Windows con el .ps1.
**Preguntas abiertas al PO:** 3 (bloqueos 1-3) + D-13.
