# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2025-2026 Gabriel Maglia
"""T-099 F0: type hints completos en los módulos de `typed_modules` (`tests/baselines/t099_ratchets.json`).

Todo parámetro (salvo `self`/`cls`, incluidos posicionales puros, keyword-only, `*args` y `**kwargs`) y todo
retorno anotados, en funciones de cualquier nivel. Los módulos van con nombre punteado (`pkg.mod` para
subpaquetes). La lista crece con cada fase de T-099 y nunca se achica: lo vigila `tests/test_t099_ratchets.py`
contra la base de la rama.

La GARANTÍA no es este test: es el paso `python -I scripts/t099_guard_check.py`, que corre antes de pytest en los
dos jobs de `.github/workflows/tests.yml`. Cualquier chequeo dentro de pytest lo puede sabotear otro test del
mismo repo (parchear `subprocess.run` o `Path.read_text` al importarse); acá queda como señal rápida en local.
"""
from __future__ import annotations

import ast

from _t099_ratchets import load, module_name, project_files, run_guard

TYPED_MODULES: tuple[str, ...] = tuple(load()["typed_modules"])


def missing_hints(source: str, filename: str = "<src>") -> list[str]:
    out: list[str] = []
    for node in ast.walk(ast.parse(source, filename=filename)):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        a = node.args
        params = [*a.posonlyargs, *a.args, *a.kwonlyargs, *(x for x in (a.vararg, a.kwarg) if x is not None)]
        for arg in params:
            if arg.arg not in ("self", "cls") and arg.annotation is None:
                out.append(f"{filename}:{node.lineno} {node.name}(): parámetro «{arg.arg}» sin tipo")
        if node.returns is None:
            out.append(f"{filename}:{node.lineno} {node.name}(): retorno sin tipo")
    return out


def typed_errors(files: dict[str, str], typed: tuple[str, ...]) -> list[str]:
    errors: list[str] = []
    by_module = {module_name(rel): (rel, src) for rel, src in files.items()}
    for mod in typed:
        if mod not in by_module:
            errors.append(f"{mod} está en typed_modules pero no existe")
            continue
        rel, src = by_module[mod]
        errors += missing_hints(src, rel)
    return errors


def test_listed_modules_are_fully_type_hinted() -> None:
    errors = run_guard("typed")   # en un intérprete propio: otro test no puede parchear la medición
    assert not errors, "\n".join(errors)


def test_the_list_has_no_duplicates() -> None:
    assert len(set(TYPED_MODULES)) == len(TYPED_MODULES)


def test_missing_parameter_return_and_star_args_are_reported() -> None:
    src = ("def f(a, b: int, *args, **kw) -> None: ...\n"
           "class C:\n    def m(self, x: int): ...\n    @classmethod\n    def k(cls) -> None:\n"
           "        async def inner(y) -> None: ...\n")
    assert missing_hints(src, "m.py") == [
        "m.py:1 f(): parámetro «a» sin tipo",
        "m.py:1 f(): parámetro «args» sin tipo",
        "m.py:1 f(): parámetro «kw» sin tipo",
        "m.py:3 m(): retorno sin tipo",
        "m.py:6 inner(): parámetro «y» sin tipo",
    ]


def test_a_fully_hinted_source_passes() -> None:
    assert missing_hints("def f(a: int, *r: str, k: bool = False, **o: object) -> int:\n    return a\n") == []


def test_keyword_only_and_positional_only_parameters_without_type_are_reported() -> None:
    src = "def f(a, /, b: int, *, c) -> None: ...\n"
    assert missing_hints(src, "m.py") == [
        "m.py:1 f(): parámetro «a» sin tipo",
        "m.py:1 f(): parámetro «c» sin tipo",
    ]


def test_subpackage_modules_can_be_listed_and_are_checked() -> None:
    files = {"pkg/__init__.py": "def f(a): ...\n", "pkg/sub/m.py": "def g() -> None: ...\n"}
    assert typed_errors(files, ("pkg.sub.m",)) == []
    assert typed_errors(files, ("pkg", "nada")) == [
        "pkg/__init__.py:1 f(): parámetro «a» sin tipo",
        "pkg/__init__.py:1 f(): retorno sin tipo",
        "nada está en typed_modules pero no existe",
    ]
