# STATE — listBuddy · actualizado: 2026-10-15 19:30

**Sprint:** 3 — Pre-release 1.0.0 (auditoría T-086 → correcciones)
**Rama activa:** `main` (35+ commits sin pushear: T-086 auditoría + T-087..T-091 Done con QA) → target: release v1.0.0
**En curso (6 agentes nerv-desktop lanzados al cierre, pueden haber quedado a medias — revisar `git log` de cada rama y `engram/plans/T-09x.md`):**
T-092 misc (`feat/t092-misc`) · T-093 nombres (`feat/t093-nombres`) · T-094 carga en worker + iterparse (`feat/t094-carga-worker`) · T-095 robustez export/preview (`feat/t095-robustez`) · T-096 cadena de suministro (`feat/t096-supply-chain`) · T-097 CI arm64+Intel (`feat/t097-ci-builds`). Ninguna mergeada ni con QA.
**Orden de merge sugerido:** T-092 → T-093 → T-095 → T-094 → T-096 → T-097 (T-094 y T-095 tocan ui.py; T-093 y T-095 tocan worker.py). Integrar en `release/1.0.0-audit` o rama nueva, suite, QA formal (una QA por ticket, otra consolida Done).
**Bloqueos (PO):** cert «Developer ID Application» + `notarytool store-credentials listbuddy` (Team ID 4GP6785MU4) · 5 datos del aviso legal `[A DEFINIR POR EL PO]` · renombrar repo a `listbuddy` · disco con <1 GB libre (liberar ≥3 GB antes de buildear).
**Decisiones abiertas:** D-15 mínimo macOS 14 vs 15 (12 módulos de PySide6 6.12 con minos 26; probar en 14.x). D-13 abogado (checklist en `engram/audit/T-086_legal.md`).
**Resumen de auditorías:** `engram/audit/T-086_consolidado.md` + 4 informes; deuda D-14..D-28 en el backlog.
**Próximo paso sugerido:** verificar estado de las 6 ramas → terminar lo incompleto → integrar + QA → push → con el cert del PO: build firmado real, decidir D-15, prueba con XML real de Rekordbox 7 → tag v1.0.0.
**Preguntas abiertas al PO:** 3 (Apple, datos legales, D-15)
