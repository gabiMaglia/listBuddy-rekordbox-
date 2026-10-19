# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2025-2026 Gabriel Maglia
"""T-099 F0 (criterio 1): ningún módulo de la raíz pasa de 1.000 líneas ni ninguna clase de 40 métodos.

Trinquete: los que hoy se pasan quedan en ALLOWED_* con su valor MEDIDO. Ese valor solo puede bajar: si el
real crece, falla; si el real baja, también falla hasta que se baje el número acá en el mismo PR. Al cerrar
T-099 las dos allowlists quedan vacías.
"""
from __future__ import annotations

import ast
import pathlib

ROOT = pathlib.Path(__file__).resolve().parents[1]
MAX_LINES = 1000
MAX_METHODS = 40

# Medido el 2026-10-19 sobre main (6ec2e74). El plan citaba 3264/158: eran de antes de T-113.
ALLOWED_LINES: dict[str, int] = {
    "ui.py": 3183,
    "ui_components.py": 1028,
}
ALLOWED_METHODS: dict[str, int] = {
    "ui.py::MainWindow": 157,
}


def count_lines(source: str) -> int:
    return len(source.splitlines())


def class_method_counts(source: str, filename: str) -> dict[str, int]:
    """`archivo::Clase` → métodos definidos en el cuerpo (propiedades y setters incluidos: cada uno es un def)."""
    out: dict[str, int] = {}

    def visit(node: ast.AST, prefix: str) -> None:
        for child in ast.iter_child_nodes(node):
            if isinstance(child, ast.ClassDef):
                name = f"{prefix}{child.name}"
                out[f"{filename}::{name}"] = sum(
                    isinstance(b, (ast.FunctionDef, ast.AsyncFunctionDef)) for b in child.body
                )
                visit(child, f"{name}.")
            elif isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
                # Una clase local también es código que alguien mantiene: se mide igual (nombre tipo __qualname__).
                visit(child, f"{prefix}{child.name}.<locals>.")
            else:
                visit(child, prefix)

    visit(ast.parse(source, filename=filename), "")
    return out


def measure(sources: dict[str, str]) -> tuple[dict[str, int], dict[str, int]]:
    lines = {name: count_lines(src) for name, src in sources.items()}
    methods: dict[str, int] = {}
    for name, src in sources.items():
        methods.update(class_method_counts(src, name))
    return lines, methods


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
                errors.append(f"{name}: {real} {unit}, ya cumple: sacalo de la allowlist de tests/test_module_size.py")
            else:
                errors.append(f"{name}: {real} {unit} < {cap} registrado: bajá el trinquete a {real}")
    for name in sorted(set(allowed) - set(measured)):
        errors.append(f"{name}: está en la allowlist pero ya no existe: sacalo")
    return errors


def root_sources(root: pathlib.Path = ROOT) -> dict[str, str]:
    # Solo la raíz: tests/, scripts/ y listBuddy_design/ quedan fuera por construcción.
    return {p.name: p.read_text(encoding="utf-8") for p in sorted(root.glob("*.py"))}


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
    assert errors == ["ui.py::MainWindow: 39 métodos, ya cumple: sacalo de la allowlist de tests/test_module_size.py"]


def test_the_allowlists_hold_exactly_the_measured_offenders() -> None:
    lines, methods = measure(root_sources())
    assert {k: v for k, v in lines.items() if v > MAX_LINES} == ALLOWED_LINES
    assert {k: v for k, v in methods.items() if v > MAX_METHODS} == ALLOWED_METHODS


def test_classes_defined_inside_functions_are_measured_too() -> None:
    body = "".join(f"        def m{i}(self) -> None: ...\n" for i in range(41))
    src = f"def fabrica() -> None:\n    class Local:\n{body}"
    assert class_method_counts(src, "m.py") == {"m.py::fabrica.<locals>.Local": 41}
    assert all_errors({"m.py": src}, {}, {}) == ["m.py::fabrica.<locals>.Local: 41 métodos (máximo 40)"]
