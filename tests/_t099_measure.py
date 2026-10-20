# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2025-2026 Gabriel Maglia
"""T-099: mide sobre un árbol cualquiera (el de HEAD o el del merge-base) lo que registran los trinquetes,
con las mismas reglas que los tests estáticos (las importa de ellos para no duplicarlas)."""
from __future__ import annotations

from typing import Any

import test_import_layers as layers
import test_module_size as size
from _t099_ratchets import module_name


def measure_ratchets(files: dict[str, str]) -> dict[str, Any]:
    """`ruta.py` → fuente  ⇒  trinquetes medidos (`typed_modules` vacío: no se mide, se compromete)."""
    lines, methods = size.measure(files)
    modules = {module_name(rel): src for rel, src in files.items()}
    packages = frozenset(module_name(rel) for rel in files if rel.endswith("__init__.py"))
    found = layers.violations(modules, packages=packages)
    return {
        "max_lines": {k: v for k, v in sorted(lines.items()) if v > size.MAX_LINES},
        "max_methods": {k: v for k, v in sorted(methods.items()) if v > size.MAX_METHODS},
        "layer_edges": sorted([a, b] for a, b in found.edges),
        "layer_qt": sorted([a, b] for a, b in found.qt),
        "layer_cycles": sorted(sorted(c) for c in found.cycles),
        "typed_modules": [],
        "module_layers": {},
    }
