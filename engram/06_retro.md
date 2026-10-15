# Retro — listBuddy

> Entradas nuevas ARRIBA. Una por sesión, ≤8 líneas. La escribe el Orquestador en el
> cierre (P-10). Las lecciones de proceso que aplican a CUALQUIER proyecto se promueven
> a ~/.nerv/playbook.md; lo específico de este proyecto queda acá.

### 2026-10-13/15 — Sprint 2: release 1.0.0 (legal, XML oficial, reparar/exportar XML, onda)
**Bien:** la auditoría legal antes de lanzar cambió el producto a tiempo: se sacó pyrekordbox (clave embebida, EULA §2.2) y Rekordbox pasó al XML oficial (ADR-004). Planes T-080/T-081 ejecutados con un subagente por tarea + revisión por tarea + revisión final: la revisión atrapó 3 bugs reales (restore de Traktor podía pisar rekordbox.xml, `REKORDBOX.XML` en macOS pisaba el origen, desmarcado de playlists tras reparar). Las opciones de onda se mostraron renderizadas con audio real del PO y eligió en un mensaje. La investigación de mercado trajo 2 bugs de producto (rutas duplicadas, streaming).
**Mal:** el crash del PO al exportar a un disco desmontado venía de antes (excepthook armando UI en un QThread) y ninguna revisión lo vio; se encontró recién en uso real. Un test de limpieza de .tmp pasaba sin el arreglo (vacío). La onda (T-084) y streaming (T-085) se mergearon sin revisión independiente. Los scripts NERV se volvieron a buscar en `~/.claude/nerv-bin` (están en `~/Documents/NERV/bin`).
**Acción concreta:** QA formal de T-080..T-085 con `nerv-gate.sh`, y probar la app empaquetada con un XML real antes del tag v1.0.0.

### 2026-10-12/13 — Menores: T-067 (Key·BPM) y T-079 (SSL)
**Bien:** recon propio antes del handoff (campos de pyrekordbox con `dir()` + librería real en solo lectura) → el ticket llegó con datos exactos (BPM ×100, ScaleName en Camelot, INFO@KEY en Traktor) y CLAUDE.md corregido; 0 rechazos. Primer `nerv-gate.sh` oficial con proof of red. QA con artefactos `qa/<T-ID>.md` pedidos explícitamente. El 404 del chequeo de updates se diagnosticó con curl (repo sin releases), no se tomó por bug.
**Mal:** QA volvió a escribir «Done 2026-10-12» sin paréntesis y el backlog-check lo rechazó (segunda vez en la sesión).
**Acción concreta:** en el handoff a QA, indicar el formato literal de la celda: `Done (AAAA-MM-DD)`.

### 2026-10-11/12 — Sprint 1: reskin «Mezcla Cálida» (T-061..T-078)
**Bien:** opciones renderizadas en canvas (5 direcciones, Opus vs Fable lado a lado) → el PO eligió en un mensaje y mezcló A+F1 sin rehacer nada; las rondas de gusto siguientes (fuente, filas rotas) también salieron en una sola vuelta. Medir las capturas con PIL antes de QA atrapó 2 defectos que la suite no veía (Nº a 1.16:1 por usar un token de divisor como texto; badge ámbar sobre ámbar). El crash del PO (T-076) se reprodujo 6/6 con repro mínimo de PySide6 antes de tocar código. QA en worktree aislado en paralelo al implementador ahorró una vuelta.
**Mal:** nerv-desktop en modo subagent-driven devolvió el control con T-063 a medias (subagentes anidados cortados) → hubo que detenerlo y relanzar inline. Dos criterios de la spec venían mal desde el Orquestador («tri-estado» copiado de CLAUDE.md sin existir; «auto-resolver persistido»). T-063 quedó en «En revisión QA» sin QA lanzada hasta que lo noté horas después. Las herramientas NERV (`nerv-gate.sh`, `nerv-backlog-check.sh`, `nerv-metrics.sh`) existían en `~/Documents/NERV/bin` y se dieron por ausentes toda la sesión (se buscaron en `~/.claude/nerv-bin`/`bin`): el gate lo hizo el Orquestador a mano y 25 Done quedaron sin artefacto `qa/<T-ID>.md` (→ `qa/_debt.md`). La suite creció a 6–8 min y frenó cada ciclo hasta T-075. El auto-push lo bloqueó el clasificador de permisos; pusheó el PO.
**Sin probar:** Windows (todo el reskin) y el `.app` real.
**Acción concreta:** handoffs de implementación siempre INLINE; tras cada ronda, listar tickets «En revisión QA» sin QA lanzada; atacar la velocidad de la suite apenas pase ~3 min.

### 2026-08-01 — Primera sesión en la Mac: los "SOLO EN MAC" eran bugs reales
**Bien:** confirmar los dos bugs EN VIVO antes de handoff (NML real + `pgrep` con Traktor abierto) costó ~4 comandos y convirtió dos hipótesis en contratos con evidencia dura. nerv-desktop no gastó un token en re-derivar el diagnóstico y QA pudo enfocarse en lo que yo NO había mirado (fallback de `diskutil`, sandbox, falsos positivos del regex). El gate P-12.1 antes de QA salió PASS y costó ~0.
**Bien:** el ticket T-023 subestimaba el bug — decía "si renombrás el disco". La realidad era peor: 3 volúmenes, 1763 pistas en un externo. Mirar el dato real cambió el criterio de aceptación (derivar de la ruta, no del disco de arranque).
**Mal:** me apuré a titular el hallazgo de T-027 como "1763 falsos positivos" y tuve que corregirme: esas pistas están genuinamente rotas (el disco `MUSIC` montado hoy no tiene esas carpetas). El bug era real igual, pero la prueba limpia era otra — un archivo SANO en el externo. Medir antes de titular.
**Mal:** `gh` no está autenticado en la Mac → QA aprobó y el PR no se pudo abrir. Se descubrió al final, no al principio.
**Acción concreta:** al arrancar sesión en una máquina nueva del PO, verificar de una las herramientas del flujo (`gh auth status`, venv, tests) ANTES del primer handoff, no cuando ya hay trabajo aprobado esperando.

