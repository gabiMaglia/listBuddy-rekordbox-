# STATE — listBuddy · actualizado: 2026-10-15 18:00

**Sprint:** 2 — Release 1.0.0 (legal, Rekordbox por XML oficial, reparar/exportar XML, onda) → CERRADO en main local
**Rama activa:** `main` (27 commits sin pushear a origin/main) → target: release v1.0.0
**En curso:** nada. T-080..T-085 En revisión QA (revisiones SDD por tarea + final hechas; sin veredicto nerv-qa).
**Bloqueos:** T-026 (cuenta Apple Developer para notarizar). `gh` sin autenticar.
**Sin probar:** XML real de Rekordbox 7 (reparar, exportar, importar en Rekordbox), pistas de streaming reales, menús de Rekordbox en español, Windows.
**Próximo paso sugerido:** PO prueba el flujo con su XML real → push de main → tag v1.0.0 + release con `scripts/release_mac.sh` (notarizado cuando haya cuenta).
**Preguntas abiertas al PO:** 1 — numeración exportada `1 -` (ancho justo) vs `001` como la vista previa.
