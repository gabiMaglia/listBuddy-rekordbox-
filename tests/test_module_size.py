# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2025-2026 Gabriel Maglia
"""T-099 F0 (criterio 1): ningún módulo de la app pasa de 1.000 líneas ni ninguna clase de 40 métodos.

Se recorren la raíz y los subpaquetes (`_t099_ratchets.project_files`). Un método es un `def` del cuerpo de la
clase o un atributo de clase asignado a una lambda, y una clase suma los métodos de las clases del proyecto de
las que hereda (ADR-007 descarta los mixins: partir en herencia no esquiva el límite).

Trinquete: los que hoy se pasan quedan en `tests/baselines/t099_ratchets.json` (`max_lines`, `max_methods`)
con su valor MEDIDO. Acá se exige que el registrado sea igual al real; `tests/test_t099_ratchets.py` exige que
solo baje respecto de la base de la rama.
"""
from __future__ import annotations

import ast

from _t099_ratchets import load, module_name, project_files

MAX_LINES = 1000
MAX_METHODS = 40

_RATCHETS = load()
ALLOWED_LINES: dict[str, int] = _RATCHETS["max_lines"]
ALLOWED_METHODS: dict[str, int] = _RATCHETS["max_methods"]


def count_lines(source: str) -> int:
    return len(source.splitlines())


def _own_methods(cls: ast.ClassDef) -> int:
    n = 0
    for b in cls.body:
        if isinstance(b, (ast.FunctionDef, ast.AsyncFunctionDef)):
            n += 1
        elif isinstance(b, ast.Assign) and isinstance(b.value, ast.Lambda):
            n += sum(isinstance(t, ast.Name) for t in b.targets)
        elif isinstance(b, ast.AnnAssign) and isinstance(b.value, ast.Lambda):
            n += 1
    return n


def class_method_counts_all(sources: dict[str, str]) -> dict[str, int]:
    """`archivo::Clase` → métodos propios más los de sus ancestros del proyecto (cada ancestro una vez)."""
    modules = {module_name(rel): rel for rel in sources}
    own: dict[str, int] = {}
    parents: dict[str, list[str]] = {}
    for rel, src in sources.items():
        tree = ast.parse(src, filename=rel)
        top = {n.name for n in tree.body if isinstance(n, ast.ClassDef)}
        names: dict[str, str] = {}     # nombre local → clase importada `archivo::Clase`
        aliases: dict[str, str] = {}   # nombre local → archivo de un módulo del proyecto
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.level == 0 and node.module in modules:
                for a in node.names:
                    names[a.asname or a.name] = f"{modules[node.module]}::{a.name}"
            elif isinstance(node, ast.Import):
                for a in node.names:
                    if a.name in modules and (a.asname or "." not in a.name):
                        aliases[a.asname or a.name] = modules[a.name]

        def resolve(base: ast.expr, rel: str = rel, top: set[str] = top, names: dict[str, str] = names,
                    aliases: dict[str, str] = aliases) -> str | None:
            if isinstance(base, ast.Name):
                return f"{rel}::{base.id}" if base.id in top else names.get(base.id)
            if isinstance(base, ast.Attribute) and isinstance(base.value, ast.Name) and base.value.id in aliases:
                return f"{aliases[base.value.id]}::{base.attr}"
            return None

        def visit(node: ast.AST, prefix: str) -> None:
            for child in ast.iter_child_nodes(node):
                if isinstance(child, ast.ClassDef):
                    name = f"{prefix}{child.name}"
                    key = f"{rel}::{name}"
                    own[key] = _own_methods(child)
                    parents[key] = [k for k in (resolve(b) for b in child.bases) if k is not None]
                    visit(child, f"{name}.")
                elif isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    # Una clase local también es código que alguien mantiene: se mide igual (como __qualname__).
                    visit(child, f"{prefix}{child.name}.<locals>.")
                else:
                    visit(child, prefix)

        visit(tree, "")

    def lineage(key: str) -> set[str]:
        seen: set[str] = set()
        todo = [key]
        while todo:
            k = todo.pop()
            if k in own and k not in seen:
                seen.add(k)
                todo.extend(parents[k])
        return seen

    return {key: sum(own[k] for k in lineage(key)) for key in own}


def class_method_counts(source: str, filename: str) -> dict[str, int]:
    return class_method_counts_all({filename: source})


def measure(sources: dict[str, str]) -> tuple[dict[str, int], dict[str, int]]:
    lines = {name: count_lines(src) for name, src in sources.items()}
    return lines, class_method_counts_all(sources)


def ratchet_errors(
    measured: dict[str, int], allowed: dict[str, int], limit: int, unit: str,
) -> list[str]:
    errors: list[str] = []
    for name, real in sorted(measured.items()):
        cap = allowed.get(name)
        if cap is None:
            if real > limit:
                errors.append(f"{name}: {real} {unit} (máximo {limit})")
        elif real > cap:
            errors.append(f"{name}: {real} {unit}, creció sobre el trinquete {cap}")
        elif real < cap:
            if real <= limit:
                errors.append(f"{name}: {real} {unit}, ya cumple: sacalo de tests/baselines/t099_ratchets.json")
            else:
                errors.append(f"{name}: {real} {unit} < {cap} registrado: bajá el trinquete a {real}")
    for name in sorted(set(allowed) - set(measured)):
        errors.append(f"{name}: está en el trinquete pero ya no existe: sacalo")
    return errors


def root_sources() -> dict[str, str]:
    return project_files()


def all_errors(
    sources: dict[str, str],
    allowed_lines: dict[str, int] = ALLOWED_LINES,
    allowed_methods: dict[str, int] = ALLOWED_METHODS,
) -> list[str]:
    lines, methods = measure(sources)
    return (ratchet_errors(lines, allowed_lines, MAX_LINES, "líneas")
            + ratchet_errors(methods, allowed_methods, MAX_METHODS, "métodos"))


def test_root_modules_and_classes_respect_the_size_ratchet() -> None:
    errors = all_errors(root_sources())
    assert not errors, "\n".join(errors)


def test_a_module_of_1001_lines_outside_the_allowlist_fails_naming_file_and_count() -> None:
    errors = all_errors({"nuevo.py": "x = 1\n" * 1001}, {}, {})
    assert errors == ["nuevo.py: 1001 líneas (máximo 1000)"], errors


def test_a_module_of_exactly_1000_lines_passes() -> None:
    assert all_errors({"nuevo.py": "x = 1\n" * 1000}, {}, {}) == []


def test_a_class_with_41_methods_outside_the_allowlist_fails_naming_file_and_count() -> None:
    body = "".join(f"    def m{i}(self) -> None: ...\n" for i in range(40))
    body += "    @property\n    def p(self) -> int: return 1\n"
    errors = all_errors({"nuevo.py": f"class Gorda:\n{body}"}, {}, {})
    assert errors == ["nuevo.py::Gorda: 41 métodos (máximo 40)"], errors


def test_nested_and_async_methods_count() -> None:
    src = "class A:\n    class B:\n        async def f(self) -> None: ...\n    def g(self) -> None: ...\n"
    assert class_method_counts(src, "m.py") == {"m.py::A": 1, "m.py::A.B": 1}


def test_an_allowlisted_module_that_grows_fails() -> None:
    sources = root_sources()
    sources["ui.py"] += "x = 1\n"
    errors = all_errors(sources)
    assert errors == [f"ui.py: {ALLOWED_LINES['ui.py'] + 1} líneas, creció sobre el trinquete {ALLOWED_LINES['ui.py']}"], errors


def test_an_allowlisted_value_above_the_real_one_fails_until_lowered() -> None:
    errors = ratchet_errors({"ui.py": 2000}, {"ui.py": 2001}, MAX_LINES, "líneas")
    assert errors == ["ui.py: 2000 líneas < 2001 registrado: bajá el trinquete a 2000"], errors


def test_an_allowlisted_entry_that_already_complies_must_be_removed() -> None:
    errors = ratchet_errors({"ui.py::MainWindow": 39}, {"ui.py::MainWindow": 157}, MAX_METHODS, "métodos")
    assert errors == ["ui.py::MainWindow: 39 métodos, ya cumple: sacalo de tests/baselines/t099_ratchets.json"]


def test_the_allowlists_hold_exactly_the_measured_offenders() -> None:
    lines, methods = measure(root_sources())
    assert {k: v for k, v in lines.items() if v > MAX_LINES} == ALLOWED_LINES
    assert {k: v for k, v in methods.items() if v > MAX_METHODS} == ALLOWED_METHODS


def test_classes_defined_inside_functions_are_measured_too() -> None:
    body = "".join(f"        def m{i}(self) -> None: ...\n" for i in range(41))
    src = f"def fabrica() -> None:\n    class Local:\n{body}"
    assert class_method_counts(src, "m.py") == {"m.py::fabrica.<locals>.Local": 41}
    assert all_errors({"m.py": src}, {}, {}) == ["m.py::fabrica.<locals>.Local: 41 métodos (máximo 40)"]


def test_a_subpackage_module_is_measured() -> None:
    errors = all_errors({"ctl/__init__.py": "", "ctl/grande.py": "x = 1\n" * 1200}, {}, {})
    assert errors == ["ctl/grande.py: 1200 líneas (máximo 1000)"], errors


def test_lambda_class_attributes_count_as_methods() -> None:
    body = "".join(f"    def m{i}(self) -> None: ...\n" for i in range(40))
    body += "    a = b = lambda self: 1\n    c: object = lambda self: 2\n    d = 3\n"
    assert class_method_counts(f"class A:\n{body}", "m.py") == {"m.py::A": 43}


def test_a_class_adds_the_methods_of_its_project_ancestors_across_modules() -> None:
    mixin = "class Mixin:\n" + "".join(f"    def x{i}(self) -> None: ...\n" for i in range(40))
    base = "class Base:\n    def b(self) -> None: ...\n"
    win = ("import base as bm\nfrom mixin import Mixin as M\nfrom PySide6.QtWidgets import QMainWindow\n"
           "class W(M, bm.Base, QMainWindow):\n    def w(self) -> None: ...\n"
           "class Hija(W):\n    pass\n")
    counts = class_method_counts_all({"mixin.py": mixin, "base.py": base, "win.py": win})
    assert counts == {"mixin.py::Mixin": 40, "base.py::Base": 1, "win.py::W": 42, "win.py::Hija": 42}
    errors = all_errors({"mixin.py": mixin, "base.py": base, "win.py": win}, {}, {})
    assert errors == ["win.py::Hija: 42 métodos (máximo 40)", "win.py::W: 42 métodos (máximo 40)"], errors


def test_a_diamond_counts_each_ancestor_once() -> None:
    src = ("class A:\n    def a(self) -> None: ...\nclass B(A):\n    pass\nclass C(A):\n    pass\n"
           "class D(B, C):\n    def d(self) -> None: ...\n")
    assert class_method_counts(src, "m.py")["m.py::D"] == 2
