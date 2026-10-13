# STATE — listBuddy · actualizado: 2026-10-12

**Sprint:** 1 — Reskin «Mezcla Cálida» → CERRADO (mergeado a main 6328dfb, pusheado por el PO)
**Rama activa:** `main` (= origin/main @ 6328dfb). `feat/reskin` local, ya mergeada (sin push).
**En curso:** nada. Reskin T-061..T-066 + T-068..T-078 Done con QA; PO probó la app en vivo: «anda bárbaro».
**Bloqueos:** T-026 (cuenta Apple Developer). `gh` sin autenticar (PRs).
**Sin probar:** Windows (todo el reskin: fuentes, íconos SVG, DPI, header compacto, QMessageBox) y el `.app` real.
**Próximo paso sugerido:**
1. T-025 — buildear el `.app` en la Mac: fuentes/íconos/`dialogs.py` dentro del bundle, tilde PNG (T-078), `diskutil`; decidir si el bundle se llama «List Buddy».
2. Regularizar QA de T-027 y T-029 (mergeados sin veredicto) y B-1 (Windows: `.exe` + checklist de 07_production_readiness.md).
3. Menores: T-067 (Key·BPM), chequeo SSL de actualizaciones (CERTIFICATE_VERIFY_FAILED), «¿» faltante en «… de todos modos?».
**Preguntas abiertas al PO:** 0
