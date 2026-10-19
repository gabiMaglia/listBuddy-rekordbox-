# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2025-2026 Gabriel Maglia
"""T-099 F0: type hints completos en los módulos de TYPED_MODULES.

Todo parámetro (salvo `self`/`cls`, incluidos `*args`/`**kwargs`) y todo retorno anotados, en funciones de
cualquier nivel. La lista crece con cada fase de T-099 y nunca se achica.
"""
from __future__ import annotations

import ast
import pathlib

ROOT = pathlib.Path(__file__).resolve().parents[1]

# F0: los módulos de L0 (ADR-007 D1) que ya cumplen el 2026-10-19.
TYPED_MODULES: tuple[str, ...] = (
    "app_paths",
    "audio_formats",
    "branding",
    "db",
    "load_cancel",
    "playlist_filter",
    "row_blocks",
)


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


def test_listed_modules_are_fully_type_hinted() -> None:
    errors: list[str] = []
    for mod in TYPED_MODULES:
        path = ROOT / f"{mod}.py"
        assert path.is_file(), f"{mod}.py está en TYPED_MODULES pero no existe"
        errors += missing_hints(path.read_text(encoding="utf-8"), path.name)
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
