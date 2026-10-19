# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2025-2026 Gabriel Maglia
"""T-099: barandas sobre el árbol real, en un intérprete aislado (`python -I`).

Uso: python -I tests/_t099_guard.py <size|size_exact|layers|layers_exact|typed|ratchets> [raíz]
Imprime en JSON la lista de errores (vacía = verde). Lo llama `_t099_ratchets.run_guard`.
"""
from __future__ import annotations

import json
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))   # -I no agrega la carpeta del script

import _t099_ratchets as ratchets  # noqa: E402
import test_import_layers as layers  # noqa: E402
import test_module_size as size  # noqa: E402
import test_type_hints as hints  # noqa: E402


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
    return [f"contra {commit[:10]}: {e}" for e in ratchets.monotonic_errors(base, ratchets.load(root))]


KINDS = {"size": _size, "size_exact": _size_exact, "layers": _layers, "layers_exact": _layers_exact,
         "typed": _typed, "ratchets": _ratchets}


def main(argv: list[str]) -> int:
    root = pathlib.Path(argv[2]) if len(argv) > 2 else ratchets.ROOT
    print(json.dumps(KINDS[argv[1]](root), ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
