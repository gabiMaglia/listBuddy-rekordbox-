# STATE — listBuddy · actualizado: 2026-08-01

**Sprint:** 0 — Alta del proyecto + producción
**Rama activa:** `main` @ `9ef4780` — **T-023/T-024 MERGEADOS y pusheados a origin/main por orden explícita del PO (2026-08-01), sin PR (`gh` sigue sin autenticar en la Mac).** 111 tests verdes sobre main. App verificada arrancando desde main.
**En curso:** Primera sesión en la Mac del PO → se atacaron los tickets "SOLO EN MAC". **T-023 y T-024 Done (QA Strong APROBADO)**: ambos confirmados como bugs REALES en vivo antes de codear, no hipótesis. T-023 — el NML real usa 3 volúmenes (`Macintosh HD` 3965, `MUSIC` 1763 externo, `NO NAME` 36) y el hardcode hacía del relocate un no-op silencioso para las 1763 de `MUSIC`; ahora el volumen se deriva vía `diskutil` + ruta. T-024 — `pgrep -ix Traktor` daba exit 1 con Traktor Pro 4 abierto (PID 26702), el guard nunca disparaba en macOS y Traktor pisaba las reparaciones al cerrar; ahora el patrón cubre Pro 3 y 4. Tests 90 → 111, verdes.
**Bloqueos:** T-026 Bloqueado (el PO va a sacar la cuenta de Apple Developer, 99 USD/año; se desbloquea con la aprobación de Apple). `gh auth login` pendiente para PRs.
**Próximo paso sugerido:**
1. **T-027 (NUEVO, prioridad alta, Niv S)** — falso positivo de "roto" en volúmenes externos en macOS: `_location_to_path` (traktor_db.py:160-177) no antepone `/Volumes/<VOL>`, así que TODA pista en disco externo aparece rota aunque esté sana. Verificado con archivo real y existente en `/Volumes/MUSIC/LISTAS2026/...`. Con el auto-resolver de T-003 encendido, reescribiría entradas sanas. Es el complemento de detección de T-023 (que arregla la escritura) — conviene cerrarlo antes de T-025.
2. T-025 (buildear/probar el .app real + icon.icns + que el bundle escriba sobre Rekordbox). Ojo con el punto que levantó QA: verificar que `diskutil` siga disponible desde el bundle firmado/sandboxeado.
3. T-026 cuando llegue la cuenta de Apple. Mientras tanto T-025 cierra con firma ad-hoc (`codesign --sign -`), válida solo en la Mac del PO.
4. B-1 (Windows): buildear el `.exe` real y correr el checklist de 8 pasos de engram/07_production_readiness.md — sigue sin hacerse.
5. Menor: T-022 parte 3 (tests de unicode en nombres de archivo).
**Preguntas abiertas al PO:** 0
