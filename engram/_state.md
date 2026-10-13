# STATE — listBuddy · actualizado: 2026-10-13

**Sprint:** 1 — Reskin «Mezcla Cálida» → CERRADO (mergeado a main 6328dfb, pusheado por el PO)
**Rama activa:** `main` @ a2f406f (+T-067 Key·BPM y T-079 SSL/certifi, QA OK; push pendiente del PO). `feat/reskin` y `feat/menores` locales, ya mergeadas.
**En curso:** nada. Reskin T-061..T-066 + T-068..T-078 Done con QA; PO probó la app en vivo: «anda bárbaro».
**Bloqueos:** T-026 (cuenta Apple Developer). `gh` sin autenticar (PRs).
**Sin probar:** Windows (todo el reskin: fuentes, íconos SVG, DPI, header compacto, QMessageBox) y el `.app` real.
**Próximo paso sugerido:**
1. T-025 — buildear el `.app` en la Mac: fuentes/íconos/`dialogs.py` dentro del bundle, tilde PNG (T-078), `diskutil`; decidir si el bundle se llama «List Buddy».
2. Regularizar QA de T-027 y T-029 (mergeados sin veredicto) y B-1 (Windows: `.exe` + checklist de 07_production_readiness.md).
3. Publicar el primer release en GitHub (el repo no tiene ninguno → el chequeo de updates da 404 y nunca avisa); va con T-025. Menor: «¿» faltante en «… de todos modos?».
**Preguntas abiertas al PO:** 0
