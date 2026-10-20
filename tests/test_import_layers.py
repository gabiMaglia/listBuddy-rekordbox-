# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2025-2026 Gabriel Maglia
"""T-099 F0 (criterio 4, ADR-007 D1): capas de import con un solo sentido, vigiladas por AST.

Se recorre el AST entero de cada módulo de la app (raíz y subpaquetes, con nombre punteado `pkg.mod`), así
que cuentan también los imports dentro de funciones, de `try` y de `if TYPE_CHECKING`, los relativos y
`importlib.import_module("x")` con texto literal. Falla ante un import hacia una capa no permitida, ante un
import de Qt prohibido para la capa y ante un ciclo. Las violaciones de hoy viven en
`tests/baselines/t099_ratchets.json` (`layer_edges`, `layer_qt`, `layer_cycles`): acá se exige que coincidan
con lo medido y `tests/test_t099_ratchets.py`, que solo se achiquen respecto de la base. Al cerrar T-099 quedan
vacías.

La GARANTÍA no es este test: es el paso `python -I scripts/t099_guard_check.py`, que corre antes de pytest en los
dos jobs de `.github/workflows/tests.yml`. Cualquier chequeo dentro de pytest lo puede sabotear otro test del
mismo repo (parchear `subprocess.run` o `Path.read_text` al importarse); acá queda como señal rápida en local.

Chequeo manual de QA (no se puede por AST): D1 deja que L4 importe L1 «solo tipos de datos». El test admite
cualquier import L4 → L1; QA revisa en cada fase que lo importado sean dataclasses/NamedTuple/enums y no
funciones con E/S ni workers (hoy no hay ningún import L4 → L1).
"""
from __future__ import annotations

import ast
from typing import NamedTuple

from _t099_ratchets import UNMEASURED_DIRS, load, module_name, project_files, run_guard, unmeasured_import

# ADR-007 D1 (engram/02_architecture.md). Incluye módulos que todavía no existen: se declaran antes de llegar.
LAYERS: dict[str, int] = {
    # L0 puros (sin Qt)
    "rekordbox_export": 0, "db": 0, "models": 0, "library_model": 0, "row_blocks": 0, "playlist_filter": 0,
    "load_cancel": 0, "branding": 0, "app_paths": 0, "audio_formats": 0, "layout_metrics": 0,
    "file_access": 0,  # T-120
    # L1 fuentes y persistencia (sin Qt)
    "rekordbox_xml": 1, "traktor_db": 1, "rekordbox_fixes": 1, "relocate_core": 1, "traktor_relocate": 1,
    "rekordbox_xml_relocate": 1, "update_checker": 1,
    # L2 workers
    "worker": 2, "preview_worker": 2, "library_load_worker": 2, "waveform_worker": 2, "audio_player": 2,
    "audio_decode": 2,
    # Llega con T-098 (instancia única, QtCore/QtNetwork, sin widgets): declarado antes para que su merge no rompa.
    "single_instance": 2,
    # L3 controladores y modelos Qt (nunca QtWidgets)
    "thread_keeper": 3, "export_controller": 3, "maintenance_controller": 3, "playback_controller": 3,
    "library_controller": 3, "preview_controller": 3, "playlist_tree_model": 3, "track_list_model": 3,
    # L4 vistas (nunca workers ni controladores)
    "styles": 4, "icons": 4, "dialogs": 4, "ui_components": 4, "player_widgets": 4, "relocate_dialogs": 4,
    "preview_card": 4, "footer": 4, "window_chrome": 4, "settings_page": 4, "playlist_panel": 4,
    "preview_panel": 4, "track_delegate": 4, "about_dialog": 4,
    # ADR-007 Addendum 1, punto 1 (PO, 2026-10-19): usa QtWidgets y `dialogs`.
    "app_logging": 4,
    # L5 raíz de composición
    "ui": 5,
    # L6
    "main": 6, "startup_guard": 6,
}

# Columna «Puede importar» de D1. L4 lee además los modelos de L3 (`*_model`). L6 importa `ui` y los módulos de
# arranque (ADR-007 Addendum 1, punto 2).
ALLOWED_LAYERS: dict[int, frozenset[int]] = {
    0: frozenset({0}),
    1: frozenset({0, 1}),
    2: frozenset({0, 1, 2}),
    3: frozenset({0, 1, 2, 3}),
    4: frozenset({0, 1, 4}),
    5: frozenset({0, 1, 2, 3, 4, 5}),
    6: frozenset(),
}
L6_ALLOWED_MODULES = frozenset({"ui", "styles", "app_logging", "startup_guard", "single_instance"})

# Qt por capa: L0/L1 sin Qt; L2/L3 sin QtWidgets.
QT_BINDINGS = ("PySide6", "shiboken6", "PyQt6")
QT_FORBIDDEN: dict[int, tuple[str, ...]] = {0: QT_BINDINGS, 1: QT_BINDINGS,
                                             2: ("PySide6.QtWidgets", "PyQt6.QtWidgets"),
                                             3: ("PySide6.QtWidgets", "PyQt6.QtWidgets")}

_RATCHETS = load()
ALLOWED_EDGES: frozenset[tuple[str, str]] = frozenset((a, b) for a, b in _RATCHETS["layer_edges"])
ALLOWED_QT: frozenset[tuple[str, str]] = frozenset((a, b) for a, b in _RATCHETS["layer_qt"])
ALLOWED_CYCLES: frozenset[frozenset[str]] = frozenset(frozenset(c) for c in _RATCHETS["layer_cycles"])


class Imports(NamedTuple):
    project: set[str]
    qt: set[str]
    unmeasured: set[str]


def imports_of(source: str, project: set[str], filename: str = "<src>", module: str = "",
               is_package: bool = False) -> Imports:
    """Módulos del proyecto y de PySide6 que importa `source`, en cualquier nivel del AST."""
    names: set[str] = set()
    package = module.split(".") if is_package else module.split(".")[:-1]
    for node in ast.walk(ast.parse(source, filename=filename)):
        if isinstance(node, ast.Import):
            names.update(a.name for a in node.names)
        elif isinstance(node, ast.ImportFrom):
            if node.level:
                base = package[:len(package) - (node.level - 1)] if node.level - 1 <= len(package) else []
                full = ".".join([*base, *([node.module] if node.module else [])])
            else:
                full = node.module or ""
            if full:
                names.add(full)
            names.update(f"{full}.{a.name}" if full else a.name for a in node.names)
        elif (isinstance(node, ast.Call) and node.args and isinstance(node.args[0], ast.Constant)
              and isinstance(node.args[0].value, str) and _is_dynamic_import(node.func)):
            names.add(node.args[0].value)
    found = Imports(set(), set(), set())
    for name in names:
        if unmeasured_import(name, project) is not None:
            found.unmeasured.add(name)
            continue
        parts = name.split(".")
        if parts[0] in QT_BINDINGS:
            if len(parts) == 1 or (len(parts) == 2 and parts[1].startswith("Qt")):
                found.qt.add(name)
            continue
        # El módulo del proyecto más largo que sea prefijo: `pkg.mod.Clase` → `pkg.mod`.
        for k in range(len(parts), 0, -1):
            cand = ".".join(parts[:k])
            if cand in project:
                found.project.add(cand)
                break
    return found


def _is_dynamic_import(func: ast.expr) -> bool:
    if isinstance(func, ast.Name):
        return func.id in ("__import__", "import_module")
    return isinstance(func, ast.Attribute) and func.attr == "import_module"


def graph_of(sources: dict[str, str], packages: frozenset[str] = frozenset()) -> dict[str, Imports]:
    project = set(sources)
    return {mod: imports_of(src, project, f"{mod}.py", mod, mod in packages) for mod, src in sources.items()}


def cycles(graph: dict[str, set[str]]) -> set[frozenset[str]]:
    """Componentes fuertemente conexas de más de un módulo (Tarjan) y autoimports."""
    index: dict[str, int] = {}
    low: dict[str, int] = {}
    stack: list[str] = []
    on_stack: set[str] = set()
    found: set[frozenset[str]] = set()
    counter = 0

    def strong(v: str) -> None:
        nonlocal counter
        index[v] = low[v] = counter
        counter += 1
        stack.append(v)
        on_stack.add(v)
        for w in sorted(graph.get(v, ())):
            if w not in index:
                strong(w)
                low[v] = min(low[v], low[w])
            elif w in on_stack:
                low[v] = min(low[v], index[w])
        if low[v] == index[v]:
            comp: set[str] = set()
            while True:
                w = stack.pop()
                on_stack.discard(w)
                comp.add(w)
                if w == v:
                    break
            if len(comp) > 1 or v in graph.get(v, ()):
                found.add(frozenset(comp))

    for v in sorted(graph):
        if v not in index:
            strong(v)
    return found


class Violations(NamedTuple):
    undeclared: list[str]
    edges: set[tuple[str, str]]
    qt: set[tuple[str, str]]
    cycles: set[frozenset[str]]
    unmeasured: set[tuple[str, str]] = set()


def violations(sources: dict[str, str], layers: dict[str, int] = LAYERS,
               packages: frozenset[str] = frozenset()) -> Violations:
    graph = graph_of(sources, packages)
    undeclared = sorted(m for m in graph if m not in layers)
    edges: set[tuple[str, str]] = set()
    qt: set[tuple[str, str]] = set()
    unmeasured = {(mod, name) for mod, imp in graph.items() for name in imp.unmeasured}
    for mod, imp in graph.items():
        if mod not in layers:
            continue
        layer = layers[mod]
        for dep in imp.project:
            if dep == mod or dep not in layers:
                continue
            if not _may_import(layer, dep, layers[dep]):
                edges.add((mod, dep))
        for q in imp.qt:
            if any(q == f or q.startswith(f + ".") for f in QT_FORBIDDEN.get(layer, ())):
                qt.add((mod, q))
    return Violations(undeclared, edges, qt, cycles({m: i.project for m, i in graph.items()}), unmeasured)


def _may_import(layer: int, dep: str, dep_layer: int) -> bool:
    if layer == 6:
        return dep in L6_ALLOWED_MODULES
    if layer == 4 and dep_layer == 3 and dep.endswith("_model"):
        return True
    return dep_layer in ALLOWED_LAYERS[layer]


def report(found: Violations) -> list[str]:
    errors = [f"módulo sin capa: declarar capa de {m} en tests/test_import_layers.py (LAYERS)"
              for m in found.undeclared]
    for mod, name in sorted(found.unmeasured):   # sin allowlist: no hay ninguno y no puede haberlo
        errors.append(f"import de código no medido: {mod} → {name} ({name.split('.')[0]}/ queda fuera de las "
                      "barandas)" if name.split(".")[0] in UNMEASURED_DIRS else
                      f"import de código no medido: {mod} → {name} (carpeta no medida dentro de un paquete)")
    for mod, dep in sorted(found.edges - ALLOWED_EDGES):
        errors.append(f"import prohibido: {mod} (L{LAYERS[mod]}) → {dep} (L{LAYERS[dep]})")
    for edge in sorted(ALLOWED_EDGES - found.edges):
        errors.append(f"la violación {edge[0]} → {edge[1]} ya no existe: sacala de ALLOWED_EDGES")
    for mod, q in sorted(found.qt - ALLOWED_QT):
        errors.append(f"Qt prohibido en L{LAYERS[mod]}: {mod} importa {q}")
    for pair in sorted(ALLOWED_QT - found.qt):
        errors.append(f"la violación Qt {pair[0]} → {pair[1]} ya no existe: sacala de ALLOWED_QT")
    for comp in sorted(found.cycles - ALLOWED_CYCLES, key=sorted):
        errors.append(f"ciclo de imports: {' ↔ '.join(sorted(comp))}")
    for comp in sorted(ALLOWED_CYCLES - found.cycles, key=sorted):
        errors.append(f"el ciclo {' ↔ '.join(sorted(comp))} ya no existe: sacalo de ALLOWED_CYCLES")
    return errors


def root_sources() -> dict[str, str]:
    return {module_name(rel): src for rel, src in project_files().items()}


def root_packages() -> frozenset[str]:
    return frozenset(module_name(rel) for rel in project_files() if rel.endswith("__init__.py"))


def test_root_modules_respect_the_adr007_layers() -> None:
    errors = run_guard("layers")   # en un intérprete propio: otro test no puede parchear la medición
    assert not errors, "\n".join(errors)


def test_every_layer_has_a_known_rule() -> None:
    assert set(LAYERS.values()) <= set(ALLOWED_LAYERS)


def test_ui_components_importing_ui_inside_a_function_fails_as_upward_import_and_cycle() -> None:
    sources = root_sources()
    sources["ui_components"] += "\n\ndef _late() -> None:\n    import ui  # noqa\n"
    errors = report(violations(sources))
    assert "import prohibido: ui_components (L4) → ui (L5)" in errors, errors
    assert any(e.startswith("ciclo de imports:") and "ui ↔" in e for e in errors), errors


def test_from_import_and_dynamic_import_are_seen() -> None:
    project = {"ui", "worker", "db"}
    src = ("from ui import MainWindow\n"
           "def f() -> None:\n    import importlib\n    importlib.import_module('worker.sub')\n"
           "try:\n    __import__('db')\nexcept ImportError:\n    pass\n"
           "from PySide6 import QtWidgets\nimport PySide6.QtCore as C\n")
    found = imports_of(src, project)
    assert found.project == {"ui", "worker", "db"}
    assert found.qt == {"PySide6", "PySide6.QtWidgets", "PySide6.QtCore"}


def test_an_undeclared_root_module_fails_with_a_clear_message() -> None:
    errors = report(violations({**root_sources(), "nuevo_modulo": "x = 1\n"}))
    assert errors == ["módulo sin capa: declarar capa de nuevo_modulo en tests/test_import_layers.py (LAYERS)"]


def test_qt_in_a_pure_layer_and_widgets_in_a_controller_fail() -> None:
    sources = {"db": "from PySide6.QtCore import QObject\n", "thread_keeper": "from PySide6 import QtWidgets\n"}
    found = violations(sources)
    assert found.qt == {("db", "PySide6.QtCore"), ("thread_keeper", "PySide6.QtWidgets")}


def test_views_may_read_qt_models_but_not_controllers_and_main_only_ui() -> None:
    sources = {"footer": "import track_list_model\nimport preview_controller\n",
               "track_list_model": "", "preview_controller": "", "main": "import ui\nimport db\n", "ui": "",
               "db": ""}
    assert violations(sources).edges == {("footer", "preview_controller"), ("main", "db")}


def test_cycle_detection_finds_long_cycles_and_ignores_dags() -> None:
    assert cycles({"a": {"b"}, "b": {"c"}, "c": {"a"}, "d": {"a"}}) == {frozenset({"a", "b", "c"})}
    assert cycles({"a": {"b"}, "b": {"c"}, "c": set()}) == set()


def test_a_fixed_violation_must_leave_the_allowlist() -> None:
    sources = root_sources()
    sources["rekordbox_export"] = sources["rekordbox_export"].replace("rekordbox_xml", "rekordbox_xml_x")
    errors = report(violations(sources))
    assert "la violación rekordbox_export → rekordbox_xml ya no existe: sacala de ALLOWED_EDGES" in errors, errors


def test_a_worker_importing_widgets_fails() -> None:
    found = violations({"worker": "def f() -> None:\n    from PySide6.QtWidgets import QWidget\n"})
    assert found.qt == {("worker", "PySide6.QtWidgets")}


def test_a_controller_importing_a_view_fails() -> None:
    sources = {"export_controller": "import dialogs\n", "dialogs": ""}
    errors = [e for e in report(violations(sources)) if e.startswith("import prohibido")]
    assert errors == ["import prohibido: export_controller (L3) → dialogs (L4)"]


def test_stale_qt_and_cycle_allowlist_entries_must_be_removed() -> None:
    sources = root_sources()
    sources["relocate_core"] = sources["relocate_core"].replace("PySide6", "PySide6_x")
    sources["preview_card"] = sources["preview_card"].replace("ui_components", "ui_components_x")
    errors = report(violations(sources))
    assert "la violación Qt relocate_core → PySide6.QtCore ya no existe: sacala de ALLOWED_QT" in errors, errors
    assert "el ciclo preview_card ↔ ui_components ya no existe: sacalo de ALLOWED_CYCLES" in errors, errors


def test_subpackage_modules_need_a_layer_and_obey_it() -> None:
    sources = {"ui": "", "ctl": "", "ctl.export": "import ui\n"}
    assert report(violations(sources, {"ui": 5}))[:2] == [
        "módulo sin capa: declarar capa de ctl en tests/test_import_layers.py (LAYERS)",
        "módulo sin capa: declarar capa de ctl.export en tests/test_import_layers.py (LAYERS)",
    ]
    assert violations(sources, {"ui": 5, "ctl": 3, "ctl.export": 3}).edges == {("ctl.export", "ui")}


def test_relative_and_dotted_imports_resolve_to_the_longest_project_module() -> None:
    project = {"ui", "pkg", "pkg.a", "pkg.b", "pkg.sub", "pkg.sub.c"}
    src = "from . import b\nfrom .sub import c\nfrom .. import ui\nimport pkg.sub.c.Clase\n"
    assert imports_of(src, project, module="pkg.a").project == {"ui", "pkg", "pkg.b", "pkg.sub", "pkg.sub.c"}
    assert imports_of("from . import a\n", project, module="pkg", is_package=True).project == {"pkg", "pkg.a"}
    assert imports_of("from .sub.c import X\n", project, module="pkg.a").project == {"pkg.sub.c"}


def test_the_allowlists_hold_exactly_the_measured_violations() -> None:
    errors = run_guard("layers_exact")
    assert not errors, "\n".join(errors)


def test_l6_may_import_ui_and_the_startup_modules_but_nothing_else() -> None:
    boot = "import ui\nimport styles\nimport app_logging\nimport startup_guard\nimport single_instance\n"
    sources = {"main": boot + "import db\n", "startup_guard": "import ui\nimport worker\n", "ui": "", "styles": "",
               "app_logging": "", "single_instance": "", "db": "", "worker": ""}
    assert violations(sources).edges == {("main", "db"), ("startup_guard", "worker")}
    assert "single_instance" in LAYERS


def test_other_qt_bindings_count_as_qt() -> None:
    sources = {"db": "import shiboken6\n", "traktor_db": "from PyQt6 import QtCore\n",
               "worker": "from PyQt6.QtWidgets import QWidget\n"}
    assert violations(sources).qt == {("db", "shiboken6"), ("traktor_db", "PyQt6"),
                                      ("traktor_db", "PyQt6.QtCore"), ("worker", "PyQt6.QtWidgets")}



def test_a_measured_build_package_and_unrelated_names_are_not_unmeasured() -> None:
    sources = {"ui": "import build.ctl\nimport build\nimport numpy.testing\nfrom ui_tests import x\n",
               "build.ctl": ""}
    assert violations(sources, {"ui": 5, "build.ctl": 5}).unmeasured == set()
