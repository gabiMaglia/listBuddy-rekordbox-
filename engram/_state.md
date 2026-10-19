# STATE — listBuddy · actualizado: 2026-10-19 11:20

**Sprint:** 4 — Re-auditoría T-104 (Nivel 0 + Nivel 1) → CERRADO: T-105, T-106, T-107, T-108, T-109, T-110, T-111, T-112 Done (QA formal; T-105/T-106/T-108 además con verifier ciego, nivel S).
**Rama activa:** `main` = `origin/main` @ 4051929 (historia reescrita el 2026-10-19: captura de rekordbox purgada; backup `~/Desktop/listBuddy-pre-purge-2026-10-19.bundle`, borrable cuando el PO lo confirme) → target: tag v1.0.0. Sin otras ramas locales ni remotas. Repo renombrado a `gabiMaglia/listbuddy` (2026-10-19).
**En curso:** T-113 (nerv-desktop, quitar Ko-fi + qrcode; luego QA y merge; sesión A). Suite 909+ passed; CI Tests verde en macOS y Windows (job `windows-latest` nuevo).
**Bloqueos (PO, fuera del repo):** (1) GitHub: environment `release` + ruleset de tags `v*` (docs/RELEASE.md). (2) Apple: cert «Developer ID Application» + API key de App Store Connect. (3) Polar: alta como MoR, producto USD 9 y pegar el enlace real (T-110). (4) Opcional: ticket a GitHub Support para quitar `refs/pull/1/head` (historia vieja con la captura, riesgo bajo).
**Decisiones abiertas:** D-13 abogado · T-102 Mac App Store (1.1) · T-098 instancia única Windows · T-099 partir ui.py / virtualizar la lista (1.1) · pata Windows en release.yml + attestation (deuda T-108).
**Sin probar:** build real de Windows (`build_windows.ps1` nunca corrió en Windows; solo el job de tests), release.yml real (primer tag), XML real de Rekordbox 7.
**Próximo paso sugerido:** PO configura GitHub + Apple + Polar → `git tag v1.0.0` → verificar borrador de Release y DMG en Mac limpia → Publish. En paralelo, primer build manual de Windows con el .ps1.
**Preguntas abiertas al PO:** 3 (bloqueos 1-3) + D-13.

## CHECKPOINT 2026-10-19 12:05 — dos sesiones en paralelo
- **Sesión A (esta):** termina T-113 en `main` (QA + merge) y acompaña al PO en el release 1.0.0. Toca `main`, `engram/03_backlog.md`, `engram/qa/`, `_state.md`.
- **Sesión B (nueva, planificación 1.1.0):** rama `plan/1.1.0` en worktree propio (`git worktree add -b plan/1.1.0 <ruta> main`). Solo escribe `engram/roadmap_1.1.md` (nuevo) y `engram/plans/1.1/*.md`; NO toca código, `03_backlog.md`, `_state.md`, ni `main`. Las filas del backlog las mergea la sesión A desde el roadmap al cerrar. Sin push: la rama se revisa local.
- **Insumos para 1.1 ya anotados:** T-098 (TEC-20 instancia única, Windows) · T-099 (TEC-14 partir `ui.py` ~3.000 líneas; virtualizar la lista de playlists: el poblado y «Marcar todas» con 800 playlists quedaron en < 150 ms solo porque el PO ratificó ese umbral) · T-102 (Mac App Store: evaluar, implica sandbox y quitar enlaces externos) · deuda T-108 (pata Windows en `release.yml` + artifact attestation; firma Authenticode descartada en T-101) · deuda T-106 (panel vacío sin estado durante un poblado largo; sin Cancelar en el poblado; `_clear_playlist_area` O(n²)) · D-13 abogado · `engram/qa/_debt.md` (31 filas) · `engram/06_retro.md` · `engram/research/` (mercado y precios).

