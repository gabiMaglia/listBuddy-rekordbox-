# T-099 F0 · verificación ciega 3 (nerv-verifier, nivel X, P-11/P-12)

Commit verificado: `808e0cd` (rama `feat/t099-f0-barandas`). Base: `main` @ `6e77dea`.
Trabajé en clones propios: tipo CI (`main` solo como `origin/main`, rama en detached/branch), y tipo F1
(`origin/main` = `808e0cd`, rama `feat/t099-f1-modelos`). Cada mutación se commitea y se corre
`python -I -S scripts/t099_guard_check.py --with-check` (Python 3.14.8, `PYTHONDONTWRITEBYTECODE=1`), sin
tocar `.github/` ni `scripts/t099_guard_check.py`.

## Veredicto: REFUTADO

Grounded: sí (cada punto lleva archivo:línea o salida de comando).

## Lo que se cumple

- Gherkin F0: allowlist exacta `ui.py`=3264, `ui_components.py`=1028, `ui.py::MainWindow`=158
  (`tests/baselines/t099_ratchets.json:3-7`), igual a lo medido en el merge-base (Addendum 1, nota). Codemod
  `--check` sobre main: «85 archivos de la base 6e77dea1d5 (main), 0 renombres, diff vacío». Bench: mediana
  `click10_ui_cpu_ms=47 click10_wall_ms=90 pop800_worst_gap_ms=85`.
- Step de CI en el clon tipo CI: `--with-check` EXIT=0, sin `--with-check` EXIT=0.
- Clon F1, en rojo como se esperaba (EXIT=1): `ui.py` +1 línea; `def` extra compensando líneas; lambda como
  atributo; mixin directo en módulo nuevo (168 > 158); import perezoso `ui_components → ui`; QtWidgets en L3
  (existente y declarado); vista L4 → worker; ciclo nuevo L4; módulo nuevo de 1.001 líneas; módulo nuevo sin
  capa; reclasificar `worker` vía `module_layers`; subir el techo en el JSON; sacar un `typed_modules`;
  agregar la arista a `layer_edges`; import desde `tests/` y desde `ctl/tests/`; editar en HEAD
  `test_module_size.py` o `_t099_ratchets.py` (se usa el de la base); tocar `.github/` en rama T-099.
- En verde como pide el PO: módulo nuevo `buddy_lists` declarado L0 en `module_layers` (EXIT=0); F1 bajando
  `ui_components.py` -5 y `ui.py` -10 (EXIT=0).

## Defectos que BLOQUEAN

1. **(media) Métodos definidos dentro de un bloque del cuerpo de la clase no cuentan.**
   `tests/test_module_size.py:41-48` (`_own_methods`) solo recorre `cls.body` de primer nivel: un `def` dentro
   de `if`/`try` del cuerpo de `MainWindow` no suma. Mutación plausible (ventana sin marco multiplataforma):
   ```python
       if sys.platform == "win32":
           def nativeEvent(self, et, msg): ...
           def _win_a(self) -> None: ...
           def _win_b(self) -> None: ...
   ```
   compensando 5 líneas en blanco → `--with-check` EXIT=0 con `MainWindow` en 161 `def` de primer nivel del
   cuerpo de clase (158 en la base). Variante `try:` con un `def` → EXIT=0; en runtime `vars(ui.MainWindow)`
   pasa de 160 a 161 callables propios. Viola el criterio 1 y la definición del propio test
   («un método es un `def` del cuerpo de la clase», `tests/test_module_size.py:5-6`).
2. **(media) La suma de métodos heredados se pierde si la base llega por re-export.**
   `tests/test_module_size.py:108-109` asume que `from m import C` define `C` en `m`; si `m` solo la
   re-exporta, la clave `m.py::C` no está en `own` y `lineage` la descarta (`:185`). ADR-007 D6 manda
   re-exportar durante la transición, así que la forma es la sancionada:
   - módulo nuevo `pw_base.py` (clase de 30 métodos), `pw_view.py` (`from pw_base import Base30`),
     `pw_child.py` (`from pw_view import Base30; class Child(Base30)` + 15 métodos), los tres declarados L4 →
     EXIT=0 con 45 métodos reales. El control con import directo da rojo («pw_child.py::Child: 45 métodos»).
   - mixin de 10 métodos re-exportado por `mw_reexp.py` o por `mwpkg/__init__.py` y heredado por
     `MainWindow` → EXIT=0 (168 reales sobre 158).
3. **(media) El test nuevo falla en el CI de la propia PR.** `tests/test_t099_guard_check.py:67` hace
   `git fetch <ROOT> main:refs/remotes/origin/main`, que necesita una rama local `main`. En un `pull_request`,
   `actions/checkout` con `fetch-depth: 0` trae `+refs/heads/*:refs/remotes/origin/*` y deja HEAD detached
   (docs de actions/checkout: `getRefSpecForAllHistory`; ADR 0153 «For PR, continue to checkout detached
   head»): no hay `main` local. Reproducido en el clon tipo CI: `FAILED
   tests/test_t099_guard_check.py::test_the_ci_step_is_green_on_the_branch_and_red_when_ui_grows_even_with_a_saboteur`
   (`CalledProcessError ... 'fetch', '-q', ..., 'main:refs/remotes/origin/main' ... exit status 128`). Con
   `main` local pasa (4 passed). No es una evasión; es pytest en rojo en el job de macOS de la PR.

## Deuda (no bloquea; reportada)

- D-a (baja) `importlib.import_module(name="ui")`, `importlib.import_module(f"ui")` y
  `sys.modules["ui"]` desde `ui_components` → EXIT=0 (`tests/test_import_layers.py:110-111` solo mira un
  primer argumento posicional `ast.Constant`). Emparentado con Y4.
- D-b (baja) `from mw_mix import *` + `class MainWindow(Mix, QMainWindow)` → EXIT=0: la base sin resolver
  cae en «externa» (`tests/test_module_size.py:141`). No hay `import *` en la app hoy.
- D-c (baja) Redefinir `class MainWindow(MainWindow)` al final de `ui.py` y quitar la clave de `max_methods`
  → EXIT=0: la clave `ui.py::MainWindow` se pisa (`tests/test_module_size.py:154-156`). Poco plausible.
- D-d (informativa) Un módulo nuevo puede declararse L5 en `module_layers` e importar workers (EXIT=0): la
  capa elegida no se contrasta con el rol D1. Es lo que aceptó el PO (`engram/plans/T-099.md`, «F0 · cierre
  de alcance»); queda a la revisión.
- Y1/Y2/Y4/Y5 (deuda declarada por el PO): no las reprobé.

## Abstenciones

- Windows (`tests.yml` job windows): no lo corrí.
- `.pyw` importable solo en Windows: no lo probé.

## Suite

`python -m pytest -q` en mi clon (con `main` local): EXIT=0, 1068 tests. Ningún inestable de T-125 apareció.
En el clon tipo CI, el test del defecto 3 falla.

## Recomprobación (HEAD `d9e1af1`: arreglo `6b1e5ce` + merge de main `93bee3f` con T-098)

Clones nuevos: tipo F1 (`origin/main` = `d9e1af1`) y tipo PR de GitHub (`git init` + fetch
`+refs/heads/*:refs/remotes/origin/*`, HEAD detached en `d9e1af1`, sin `main` local). Mismos casos.

| Bloqueante | Caso | Resultado |
|---|---|---|
| 1 | `if sys.platform == "win32":` + 3 `def` en `MainWindow` | EXIT=1 «ui.py::MainWindow: 161 métodos, creció sobre el trinquete 158» |
| 1 | `try:` + 1 `def` | EXIT=1 «159 métodos, creció sobre el trinquete 158» |
| 1 | `if True:` + 1 `def` | EXIT=1 «159 métodos» |
| 2 | clase nueva 30+15 con la base re-exportada | EXIT=1 «pw_child.py::Child: 45 métodos (máximo 40)» |
| 2 | mixin re-exportado por módulo (`mw_reexp`) | EXIT=1 «ui.py::MainWindow: 168 métodos» |
| 2 | mixin re-exportado por `mwpkg/__init__.py` | EXIT=1 «ui.py::MainWindow: 168 métodos» |
| 3 | `pytest -n 0 tests/test_t099_guard_check.py` en el clon tipo PR | PYTEST_EXIT=0, «4 passed in 10.77s» |

El step `python -I -S scripts/t099_guard_check.py --with-check` en el clon tipo PR: GUARD_EXIT=0 («87 archivos
de la base 93bee3f2f4 (main), 0 renombres, diff vacío»).

**Los 3 bloqueantes quedaron CERRADOS.**

Regresión, 40 mutaciones en el clon F1: los casos que antes daban rojo siguen en rojo (crecimiento de
`ui.py`, `def` extra, lambda, mixin directo, imports y Qt prohibidos, ciclo, 1.001 líneas, módulo sin capa,
reclasificación, JSON con techo subido / `typed_modules` sacado / arista nueva, import desde `tests/`,
edición en HEAD del código de las barandas, `.github/` tocado). Los verdes esperados siguen en verde: módulo
nuevo declarado (`m05`) y F1 bajando límites (`m08`, `m09`). Los únicos otros verdes son la deuda ya
reportada, sin cambios: D-a (`n18`-`n20`), D-b (`m16`), D-c (`n26`), D-d (`m14`, `m28`, `m31`) y `m32`
(`thread_keeper` nuevo, L3 con QtCore, correcto). No corrí la suite completa en esta pasada (no se pidió).
