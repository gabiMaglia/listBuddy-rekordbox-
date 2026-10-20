# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2025-2026 Gabriel Maglia
"""T-099: barandas sobre el árbol real, en un intérprete aislado (`python -I`).

Uso: python -I tests/_t099_guard.py <size|size_exact|layers|layers_exact|typed|ratchets|--all> [raíz]
Con un tipo imprime en JSON la lista de errores (vacía = verde) y sale 0; lo llama `_t099_ratchets.run_guard`.
Con `--all` corre los seis, imprime los errores y sale 1 si hay alguno; lo usa `scripts/t099_guard_check.py`.

Los módulos de barandas se cargan por ruta (`spec_from_file_location`) y `tests/` NUNCA entra en `sys.path`: un
`tests/ast.py` o `tests/typing.py` no puede reemplazar a la stdlib acá adentro, y `-I` deja afuera
`PYTHONPATH`, el directorio actual y `site` del usuario.
"""
from __future__ import annotations

import importlib.util
import json
import pathlib
import sys
from types import ModuleType

HERE = pathlib.Path(__file__).resolve().parent
# Orden de carga: cada uno importa por nombre a los anteriores, que ya están en `sys.modules`.
GUARD_MODULES = ("_t099_ratchets", "test_module_size", "test_import_layers", "test_type_hints", "_t099_measure")


def load_guards(folder: pathlib.Path = HERE) -> dict[str, ModuleType]:
    loaded: dict[str, ModuleType] = {}
    for name in GUARD_MODULES:
        spec = importlib.util.spec_from_file_location(name, folder / f"{name}.py")
        assert spec is not None and spec.loader is not None
        module = importlib.util.module_from_spec(spec)
        sys.modules[name] = module
        spec.loader.exec_module(module)
        loaded[name] = module
    return loaded


_G = load_guards()
ratchets = _G["_t099_ratchets"]
size = _G["test_module_size"]
layers = _G["test_import_layers"]
hints = _G["test_type_hints"]


def _size(root: pathlib.Path) -> list[str]:
    return size.all_errors(ratchets.project_files(root))


def _size_exact(root: pathlib.Path) -> list[str]:
    lines, methods = size.measure(ratchets.project_files(root))
    out: list[str] = []
    lines_over = {k: v for k, v in lines.items() if v > size.MAX_LINES}
    methods_over = {k: v for k, v in methods.items() if v > size.MAX_METHODS}
    if lines_over != size.ALLOWED_LINES:
        out.append(f"max_lines medido {lines_over} != registrado {size.ALLOWED_LINES}")
    if methods_over != size.ALLOWED_METHODS:
        out.append(f"max_methods medido {methods_over} != registrado {size.ALLOWED_METHODS}")
    return out


def _layer_inputs(root: pathlib.Path) -> tuple[dict[str, str], frozenset[str]]:
    files = ratchets.project_files(root)
    modules = {ratchets.module_name(rel): src for rel, src in files.items()}
    return modules, frozenset(ratchets.module_name(r) for r in files if r.endswith("__init__.py"))


def _layers(root: pathlib.Path) -> list[str]:
    modules, packages = _layer_inputs(root)
    return layers.report(layers.violations(modules, packages=packages))


def _layers_exact(root: pathlib.Path) -> list[str]:
    modules, packages = _layer_inputs(root)
    found = layers.violations(modules, packages=packages)
    measured = (found.edges, found.qt, found.cycles)
    registered = (set(layers.ALLOWED_EDGES), set(layers.ALLOWED_QT), set(layers.ALLOWED_CYCLES))
    return [] if measured == registered else [f"capas medidas {measured} != registradas {registered}"]


def _typed(root: pathlib.Path) -> list[str]:
    return hints.typed_errors(ratchets.project_files(root), hints.TYPED_MODULES)


def _ratchets(root: pathlib.Path) -> list[str]:
    try:
        commit, base = ratchets.base_ratchets(root)
    except ratchets.BaseUnavailable as e:
        return [str(e)]
    current = ratchets.load(root)
    errors = ratchets.monotonic_errors(base, current) + ratchets.new_layer_errors(root, commit, base, current)
    return [f"contra {commit[:10]}: {e}" for e in errors]


KINDS = {"size": _size, "size_exact": _size_exact, "layers": _layers, "layers_exact": _layers_exact,
         "typed": _typed, "ratchets": _ratchets}


def main(argv: list[str]) -> int:
    root = pathlib.Path(argv[2]) if len(argv) > 2 else ratchets.ROOT
    if argv[1] == "--all":
        bad = 0
        for kind, fn in KINDS.items():
            errors = fn(root)
            print(f"{'✗' if errors else 'OK'} baranda {kind}")
            for e in errors:
                print(f"  {e}")
            bad += len(errors)
        return 1 if bad else 0
    print(json.dumps(KINDS[argv[1]](root), ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
