# T-099 F0 — Verificación ciega (nerv-verifier, P-11/P-12)

Fecha: 2026-10-19 · Rama `feat/t099-f0-barandas` @ 22703dd · Base `main` @ cb74abd
Leído: CLAUDE.md, `03_backlog.md` fila T-099, `engram/plans/T-099.md`, `engram/plans/1.1/T-099.md` §2/§3 F0/§4 F0,
`git diff main...HEAD -- tests/ scripts/`. No se leyó `engram/qa/T-099-F0.md` ni el handoff log.

## Veredicto: REFUTADO

El Gherkin F0 se cumple (ver tabla) y los tests nuevos discriminan (11/11 mutantes muertos). Se refuta porque el
pase hostil encontró formas de pasar en verde que contradicen texto explícito del plan F0 y de ADR-007 D5/D1
(defectos 1-3, severidad media). Ninguno rompe producción: F0 no toca código de producción
(`git diff main...HEAD --stat -- '*.py' ':!tests' ':!scripts'` vacío).

## Gherkin F0

| # | Escenario | Resultado | Evidencia |
|---|---|---|---|
| 1 | Los 3 tests pasan en main sin cambios; allowlist = 3264/1028/158 | Pasa con desvío: allowlist = 3183/1028/157 | `tests/test_module_size.py:19-25`; `wc -l ui.py` = 3183; AST y conteo por grep de `    def ` en `MainWindow` (ui.py:155-3183) = 157 ambos. El desvío está declarado en `engram/plans/T-099.md:12` y es el único valor compatible con la regla del propio plan (§3 F0: falla si el registrado > real). Supuesto marcado: no consta que el PO ratificara la corrección (el párrafo precede al sello, que es del plan original). |
| 2 | 1.001 líneas / 41 métodos fuera de allowlist fallan nombrando archivo y conteo | Cumple | `test_module_size.py:103-116`; mutantes M2 (`zz_big.py: 1001 líneas (máximo 1000)`) y M3 (`db.py::Gorda: 41 métodos (máximo 40)`) |
| 3 | `ui_components` con import de `ui` → falla | Cumple | `test_import_layers.py:225-230`; mutante M4: `import prohibido: ui_components (L4) → ui (L5)` + ciclo |
| 4 | `--check` sobre main sin renombres → diff vacío | Cumple | `python scripts/t099_rewrite_tests.py --check` → `OK: 79 archivos de tests de main, 0 renombres, diff vacío`, exit 0 |
| 5 | Bench imprime click 10 y peor hueco de 800, pegados en el PR | Imprime: sí. Pegado en PR: abstención (no hay PR) | `python scripts/t099_bench.py --repeat 1` → `click10_wall_ms=89 click10_ui_cpu_ms=47 … pop800_worst_gap_ms=88` (load1 5.64, x86_64, offscreen) |

## Mutaciones (`-n 0` sobre `test_module_size.py test_import_layers.py test_type_hints.py`; restauradas con `git checkout`)

Muertas (EXIT=1): M1 ui.py +1 línea · M2 módulo nuevo de 1.001 · M3 clase de 41 en db.py · M4 `import ui` diferido en
ui_components · M5 ciclo L0 db↔row_blocks dentro de funciones · M6 parámetro sin tipo en db.py · M7 `PySide6.QtWidgets`
en preview_worker (L2) · M8 `PySide6.QtCore` bajo `TYPE_CHECKING` en playlist_filter (L0) · M9
`importlib.import_module("ui")` en worker · M10 footer (L4) → thread_keeper (L3) · M11 main → db.

Vivas (EXIT=0) → defectos abajo: H2 trinquete subido junto con el crecimiento · H3 mixin de 40 métodos ·
H4 módulo sacado de TYPED_MODULES + parámetro sin tipo · H5 `from relocate_core import *` en footer (L4) ·
H6 subpaquete `ctl/` de 1.200 líneas que importa `ui`. Además, clase con 40 `def` + 45 `m = lambda self: …`
→ `all_errors` = `[]`. `--check` sale 0 con `tests/data/t094_roundtrip_in.xml` y `pytest.ini` modificados.

## Defectos

1. **Media — el trinquete no se ancla a la base.** `tests/test_module_size.py:19-25,141-144` compara la medición
   contra constantes del mismo archivo: subir `"ui.py": 3183→3184` y agregar una línea a ui.py pasa en verde (H2).
   Contradice plan §3 F0 («un valor de la allowlist solo puede bajar», `engram/plans/1.1/T-099.md:265`). Mismo
   problema en `ALLOWED_EDGES/QT/CYCLES` (`test_import_layers.py:63-79`) y en `TYPED_MODULES`
   (`test_type_hints.py:6` dice «nunca se achica»; H4 lo achica sin falla).
2. **Media — `--check` no cubre todo lo que cambia un test (D5).** `scripts/t099_rewrite_tests.py:122-123` filtra
   solo `tests/**.py`: cambiar un fixture (`tests/data/*.xml`) o `pytest.ini` (p. ej. `--deselect`) da
   `diff vacío`, exit 0. D5 (`engram/plans/1.1/T-099.md:166-170`) exige que el diff de los tests sea exactamente
   la salida del codemod.
3. **Media — D5 inalcanzable desde F1 tal como está.** Una vez que las barandas estén en main, bajar el trinquete
   (obligatorio por el propio test) modifica `tests/test_module_size.py` / `test_import_layers.py` y `--check`
   falla: con `ui_components.py` 1028→990 y `--base HEAD` → `✗ 1 de 83 archivos de tests difieren`. No hay un
   mecanismo (exención con verificación de monotonía) que distinga «bajar trinquete» de «cambiar aserción»;
   QA tendría que triar a mano justo lo que D5 quería automatizar. Arreglar 1 y 3 juntos: `--check` (o el test)
   compara los valores de allowlist con `git show <base>:tests/...` y solo acepta bajas/eliminaciones.
4. **Baja — D1 «L4 importa L1 solo tipos de datos» no se verifica.** `test_import_layers.py:52` permite L4→L1
   entero; H5 (`from relocate_core import *` en footer) pasa. Hoy no hay ningún L4→L1 (grep vacío), así que
   cuesta poco fijarlo ahora.
5. **Baja — evasiones del conteo de tamaño/capa.** Solo se mide `ROOT.glob("*.py")` (`test_module_size.py:85`,
   `test_import_layers.py:213`): un subpaquete escapa a tamaño, capas y type hints (H6). Métodos como
   atributos lambda no cuentan (`test_module_size.py:41`). Un mixin de ≤40 métodos pasa (H3) aunque ADR-007
   lo descarta (§2 «Alternativas descartadas»).
6. **Baja — bordes del codemod** (`scripts/t099_rewrite_tests.py:68-111`): (a) nombres por texto sin punto no se
   reescriben: `setattr/getattr/hasattr/patch.object(w, "_x")` quedan iguales; hoy hay uno en tests de ventana,
   `tests/test_header.py:114` `assert not hasattr(w, '_sun_btn')`, aserción negativa que se volvería vacía si
   ese atributo se renombra sin el mapa. (b) dentro de f-strings `{w . _x}` con espacios no se reescribe, en
   código sí (inconsistente con `test_t099_rewrite_tests.py:48-50`). (c) un `new` con `()` en un destino de
   asignación/`del` produce código inválido (`w._tree.entries() = []`) y `load_renames` lo acepta.
   (d) `import m._x` se reescribe a `import m._c.x`. (e) entrada no tokenizable → `TokenError` sin capturar.
   (f) `--check` lee el working tree, no `HEAD`, y compara contra `main` móvil (no merge-base).

## Supuestos marcados / abstenciones

- Capas no definidas en ADR-007 D1 elegidas por la implementación: `app_logging` = L4 y `file_access` = L0
  (`tests/test_import_layers.py:23,37-39`); el propio comentario pide ratificación del arquitecto.
- Allowlist 3183/157 vs Gherkin 3264/158: ver fila 1.
- Baseline del bench «pegada en el PR»: no hay PR; abstengo.
- `test_the_versioned_rename_map_loads` (`test_t099_rewrite_tests.py:74-77`) es vacuo con el mapa vacío actual
  (solo prueba que parsea).

## Suite

`python -m pytest -q` (xdist -n 4) → exit **0** (salida en el scratchpad del verificador, `suite.exit` = 0).
Worktree restaurado: `git status --short` vacío antes de este commit.
