# KICKOFF 1.1.0 — cómo arrancar la implementación (pensado para ejecutar con Opus)

> Escrito por el Orquestador el 2026-10-19 al cerrar la sesión B. Todo lo que hay que decidir ya está
> decidido (`roadmap_1.1.md` §3, ADR-007/008 en `02_architecture.md`). La próxima sesión NO re-planifica:
> abre `/nerv-init`, elige listBuddy, y lanza la Ola 1 tal cual está acá. Modelo sugerido para los
> implementadores: **Opus** (`model: "opus"` en el `Agent`); QA y verifier pueden ser Opus también.

## 0. Precondiciones (verificar en 1 minuto)

```bash
cd "$(git rev-parse --show-toplevel)"   # raíz del checkout principal
git status -sb                     # main limpio, = origin/main (si va «ahead», el PO pushea)
git log --oneline -1               # ≥ 89e7017 (alta Sprint 5)
source .venv/bin/activate && python -m pytest -q 2>&1 | tail -2   # exit 0 (~45 s)
df -h . | tail -1                  # > 5 GB libres (los worktrees y builds llenan el disco)
```

Si el PO ya taggeó v1.0.0, mejor; si no, 1.1 puede avanzar igual: nada de la Ola 1 toca el release.

## 1. Ola 1 — tres tickets independientes, archivos disjuntos, en paralelo

| Ticket | Niv | Agente | Worktree | Archivos que toca | Plan |
|---|---|---|---|---|---|
| T-099 **F0 solamente** | S | nerv-desktop | `../wt-t099-f0` rama `feat/t099-f0-barandas` | `tests/test_module_size.py`, `tests/test_import_layers.py`, `tests/test_type_hints.py`, `scripts/t099_rewrite_tests.py`, `scripts/t099_renames.toml`, `scripts/t099_bench.py` (todos nuevos). NO toca `ui.py` | `engram/plans/1.1/T-099.md` §3 F0 + §4 Gherkin F0 |
| T-098 | B | nerv-desktop | `../wt-t098` rama `feat/t098-instancia-unica` | `main.py` o `startup_guard.py`, `app_paths.py`, `app_logging.py`, tests nuevos | Gherkin del backlog (4 criterios) |
| T-120 | B | nerv-desktop | `../wt-t120` rama `feat/t120-file-access` | `file_access.py` (nuevo), puntos de lectura en `rekordbox_xml.py`/`traktor_db.py`/`library_load_worker.py` y de escritura en `worker.py`/`rekordbox_xml.py` (`write_playlists_xml`)/`traktor_relocate.py`, test AST nuevo | `engram/plans/1.1/T-102.md` §3 F1-a + Gherkin del backlog |

Crear los worktrees desde `main`:

```bash
git worktree add -b feat/t099-f0-barandas ../wt-t099-f0 main
git worktree add -b feat/t098-instancia-unica ../wt-t098 main
git worktree add -b feat/t120-file-access ../wt-t120 main
```

### Prompt para cada `Agent` (subagent_type `nerv-desktop`, `model: "opus"`, inline, uno por ticket)

```
Handoff P-1 (NERV, ~/.claude/nerv-protocols.md). Proyecto listBuddy.
Ticket: <T-ID> · Nivel <A/S/B> · Rama <rama> · Worktree <ruta absoluta>. Trabajás SOLO ahí.
Leé, en este orden y nada más: CLAUDE.md; engram/03_backlog.md fila <T-ID> (criterios Gherkin);
<plan indicado en la tabla>; engram/02_architecture.md §ADR-007 (y §ADR-008 para T-120);
~/.nerv/playbook.md §nerv-desktop.
Reglas: TDD (rojo antes que verde, pegá la salida del rojo); tests Qt en intérprete aparte según
CLAUDE.md §Tests; sin tocar archivos fuera de tu lista; sin push; commits chicos con AB#<T-ID>.
Al terminar: suite completa a archivo (`python -m pytest -q > /tmp/<T-ID>.log; echo $?`) y
retorno estructurado: estado · archivos tocados · riesgos/caveats · cómo probar · salida del rojo
y del verde. Limpiá sondas y archivos temporales (df al final).
```

### Al retorno de cada uno (Orquestador)

1. `~/Documents/NERV/bin/nerv-gate.sh` sobre la rama (P-12): PASS obligatorio; el gate recomputa el nivel.
2. Handoff a `nerv-qa` (puede ser Opus) pidiendo **explícitamente** `engram/qa/<T-ID>.md` y celda `Done (AAAA-MM-DD)`.
   Para T-099 F0 además `nerv-verifier` ciego (nivel S) tras QA.
3. Merge a `main` con `--no-ff`, suite en `main`, `echo $?` antes de cualquier push (retro 2026-10-19).
4. `~/Documents/NERV/bin/nerv-backlog-check.sh .` OK antes de cerrar.

## 2. Ola 2 — camino crítico a Buddy (secuencial, cada fase un PR)

Después de F0 mergeada: T-099 **F1** → **F6** → **F7** (cada una con el mismo prompt, cambiando «F0» por la
fase y leyendo `T-099.md` §3 y §4 de esa fase). F6 es la de mayor riesgo entre los movimientos puros:
pedir verifier ciego. Con F7 en main: **T-114** (nivel A, sin Qt, puede ir en paralelo con F8).
Después **F8** (árbol virtualizado, umbral < 50 ms, codemod de aserciones auditado por QA) y **F9 solo
el modelo** (`track_list_model.py` + `track_delegate.py`, sin migrar la previa todavía).

## 3. Ola 3 — Buddy visible

**T-115** (nivel S; mockup elegido: `buddy-disenos.html` pestaña C «fuentes apilables») → **T-116** →
**T-117**. Antes de T-115, renderizar capturas del layout real con el `capture.py` de
`engram/plans/design/` y mostrarlas al PO (como en el reskin): una vuelta de gusto barata.

## 4. Cierre de 1.1

T-099 F2-F5 y F9-vista (sin prerrequisitos de usuario, bajo riesgo), T-119 (nerv-devops; necesita que
el PO pushee un tag `v1.1.0-rc1`). Después: CHANGELOG, bump de versión, `scripts/release_mac.sh`, tag.

## 5. Cosas que NO hay que volver a discutir

- Layout, carpetas, export Traktor, undo, navegación, mezcla de fuentes, codemod, umbral, paridad, orden,
  App Store: cerradas en `roadmap_1.1.md` §3 (PO, 2026-10-19).
- Rekordbox solo por XML (ADR-004). Nunca `master.db`.
- Los números de ADR siguientes: **ADR-009** es el próximo libre (reservarlo en el handoff si se lanzan
  dos arquitectos en paralelo).
