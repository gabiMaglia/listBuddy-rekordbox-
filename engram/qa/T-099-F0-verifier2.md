# T-099 F0 · Verificación ciega 2 (nerv-verifier, P-11/P-12, nivel S) · 2026-10-19

**Veredicto: REFUTADO.** El Gherkin de F0 se cumple (5/5) y ADR-007 D1/D5 + Addendum 1 están bien
reflejados, pero el pase hostil pasa en verde (pytest **y** `--check`) dos cosas que las barandas dicen frenar.

Leído: `CLAUDE.md`; `engram/03_backlog.md:91`; `engram/plans/T-099.md`; `engram/plans/1.1/T-099.md` §2, §3 F0, §4 F0;
`engram/02_architecture.md:224-280` y `:383-397` (Addendum 1 y nota); `git diff main...HEAD -- tests/ scripts/ .github/`.
No leí `engram/qa/` ni handoffs.

## Entornos
- Worktree `feat/t099-f0-barandas` @ ff50fcd.
- Clon CI: `git clone` + `checkout --detach origin/feat/t099-f0-barandas` + `branch -D main` (solo `origin/main`),
  y además merge de `origin/main` (simula el merge commit de la PR, a934540). Los 5 archivos de F0: verde; `--check`:
  `OK: 83 archivos de la base 3a7cdc918b (main), 0 renombres, diff vacío`.
- Clon F1: `origin/main` movido al merge de F0 (c661910), rama con `ui.py` 3264→3261 y JSON bajado a 3261:
  tests verdes y `--check` `OK: 91 archivos … diff vacío` (control positivo de D5).

## Gherkin F0
1. Allowlist exacta `ui.py`=3264, `ui_components.py`=1028, `ui.py::MainWindow`=158 (`tests/baselines/t099_ratchets.json:2-8`);
   medida independiente con `git show origin/main:ui.py | wc -l` = 3264, `ui_components.py` = 1028, AST `MainWindow` = 158.
   Coincide con la nota del Addendum 1 (`02_architecture.md:392-397`). Sin cambios de producción en el diff. OK.
2. 1.001 líneas / 41 métodos: `tests/test_module_size.py:148-161`; mutación H03 (clase de 41 en `row_blocks.py`) falla. OK.
3. `ui_components` importa `ui`: `tests/test_import_layers.py:237-242`. OK.
4. `--check` sobre main sin renombres: diff vacío (arriba). OK.
5. Bench: `python scripts/t099_bench.py --repeat 1` (offscreen, load 3.8, x86_64): `click10_ui_cpu_ms=56`,
   `pop800_worst_gap_ms=96`, exit 0. «Pegados en el PR»: no hay PR → **abstención**.

## Matriz hostil (exit pytest de los 5 tests F0 / exit `--check`)
Estado F0 (clon CI): crecer `ui.py` 1/0 · crecer + subir JSON 1/1 · clase de 41 1/0 · subpaquete `ctl/` de 1.001 1/0 ·
`db` importa `ui` 1/0 · ciclo L2 `worker`↔`preview_worker` 1/0 · parámetro sin tipo en `db` 1/0 · import prohibido +
allowlist subida 1/1 · `typed_modules` achicado 1/1 · QtCore en L0 1/0 · QtWidgets en worker 1/0 · módulo sin capa 1/0 ·
`MAX_LINES=5000` + vaciar JSON 1/0 · `MAX_METHODS=400` 1/0 · reclasificar `ui_components` a L5 1/1 ·
**paquete `build/` de 1.501 líneas que importa `ui` 0/0** (D-4).
Estado F1 (`--check`): cambiar una aserción 0/1 · fixture `tests/data` 0/1 · `pytest.ini --deselect` 0/1 · `LAYERS` 1/1 ·
`MAX_LINES` 1/1 · `tests/sub/conftest.py` nuevo 0/1 · subir `ui_components.py` 1/1 · achicar `typed_modules` 1/1 ·
editar `_t099_ratchets.py` 0/1 · `pytestmark = slow` 0/1 · borrar test 4/1 · renombre privado legítimo 0/0 (control) ·
**test nuevo que neutraliza la baranda 0/0** (D-2) · **renombre semántico `isChecked`→`isEnabled` 0/0** (D-3, 9 archivos) ·
**`--check` editado para devolver 0 0/0** (D-5) · `--deselect` en `.github/workflows/tests.yml` −/0 (D-6).

## Defectos

### Bloquean
- **D-1 (media) · `tests/test_module_size.py:53-68`.** La herencia solo se resuelve para `from mod import C` y `import mod`
  + `mod.C`. Quedan sin sumar: import relativo (`from .mixins import Mix`), `from pkg import mod` + `mod.Mix` y bases
  dinámicas. Además, una función de módulo asignada en el cuerpo de la clase (`f = _f`) no cuenta (`:31-40` solo
  cuenta `def` y lambdas). Probado: `{'ctl/mixins.py::Mix': 40, 'a.py::W': 1, 'ctl/rel.py::W': 1, 'c.py::W': 1}` (W
  hereda de Mix o liga `_f`). Viola la promesa del docstring (`:5-7`: «partir en herencia no esquiva el límite») y
  ADR-007 (los mixins están descartados explícitamente). Es el bypass que aparece por accidente al crear subpaquetes.
- **D-2 (media) · `scripts/t099_rewrite_tests.py:25-26,240-243`.** Los archivos nuevos de `tests/` (salvo conftest y
  config) están exentos de `--check`, y desde un test nuevo se puede parchear el módulo de la baranda. Con
  `tests/test_aaa_helper.py` que reemplaza `test_module_size.root_sources` por una versión que trunca `ui.py` al techo,
  `ui.py` crece de 3261 a 3264 por encima del trinquete y aun así pytest pasa (56 passed) y `--check` da `OK … diff vacío`.
  Sin el helper falla `test_the_allowlists_hold_exactly_the_measured_offenders`. Así se pasa en verde lo que D5 y el
  criterio 1 dicen frenar. Arreglo sugerido: que las barandas corran en su propio proceso o en un paso de CI
  (`python -I` sobre `_t099_measure`) y no dependan de objetos globales que puede tocar otro módulo de test.

### Deuda
- **D-3 (media) · `scripts/t099_rewrite_tests.py:78-81`.** `old` solo tiene que ser un identificador. El plan F0 habla
  de reescribir `w._x` y D5 de «rutas de acceso», pero `old = "isChecked"`, `new = "isEnabled"` cambia aserciones en 9
  archivos y `--check` sale 0. Hoy lo único que lo frena es que QA revise el mapa. Sugerido: exigir `old` privado
  (`_…`) o un receptor del mapa.
- **D-4 (baja) · `tests/_t099_ratchets.py:26`.** `EXCLUDED_DIRS` incluye `build` y `dist`, que son importables como
  paquetes. Un `build/ctl.py` de 1.501 líneas que importa `ui` (agregado con `git add -f`, porque `.gitignore:4-5` los
  ignora) pasa tamaño, capas y `--check`.
- **D-5 (media, proceso) · `scripts/t099_rewrite_tests.py` entero.** `--check` corre el script y el mapa de HEAD, y
  `scripts/` no se compara contra la base. Basta un `bad = 0` antes de `if bad:` (`:248`) para que una aserción cambiada
  dé exit 0. QA debería correr el `--check` de la base (`git show <merge-base>:scripts/t099_rewrite_tests.py`) o
  `--check` debería exigir que el script no cambió.
- **D-6 (baja) · `.github/workflows/tests.yml`.** CI no corre `--check` (solo `pytest -q`, `:41-42`) y `--check` no mira
  `.github/`: un `--deselect` en el workflow escapa a los dos. Queda a la vista en el diff de la PR.
- **D-7 (baja) · `scripts/t099_rewrite_tests.py:115-120`.** `store_check` no detecta destinos de tupla, `for`, `with`
  ni anotados. `w._cards, b = …`, `for w._cards in …`, `with … as w._cards` y `w._cards: list = []` se reescriben a
  `w._tree.entries()` (código inválido) en vez de salir con exit 2, como promete el docstring (`:12-13`). Falla ruidosa,
  no pasa en verde. Tampoco reescribe kwargs (`SimpleNamespace(_x=1)`) ni nombres dentro de rutas
  `patch('ui.MainWindow._x')` (→ `ui.MainWindow._c.x`, falla en runtime).
- **D-8 (baja) · `scripts/t099_bench.py:152,158`.** El bench usa privados de `MainWindow` (`_populate_playlists`,
  `_all_cards`) y el codemod solo reescribe `tests/`. El «antes/después» de F6 (Gherkin F6) va a necesitar tocar el
  bench a mano.
- **D-9 (baja) · `tests/test_import_layers.py:67-68,103-107`.** Solo reconoce `PySide6*`: `shiboken6`/`PyQt6` en L0/L1
  pasan sin aviso.

## Supuestos señalados y abstenciones
- `file_access` = L0 (`tests/test_import_layers.py:29`) y `single_instance` = L2 (`:37`) no figuran en la tabla D1. El
  Addendum 1 nombra `single_instance` solo como módulo de arranque importable desde L6 (`02_architecture.md:388`). Hace
  falta que el arquitecto o el PO los ratifiquen. Abstención.
- «L4 → L1 solo tipos de datos» no se puede verificar por AST (`tests/test_import_layers.py:13-15`). Abstención.
- Job de Windows (`tests.yml:47-70`): no lo corrí. Abstención.
- Bench «pegado en el PR»: no hay PR. Abstención.

## Suite
`python -m pytest -q` en el worktree, salida a archivo: **exit 0** (unas 1.006 pruebas, todas verdes). El test inestable
`test_all_and_none_buttons_act_only_on_visible_while_filtering_and_on_all_otherwise` no falló en esta corrida.
Mutaciones con `-n 0` y siempre en clones del scratchpad. El worktree quedó sin cambios, salvo este informe.
