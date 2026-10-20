# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2025-2026 Gabriel Maglia
"""T-099 F0: el código de una carpeta no medida (`tests/`, `scripts/`, `engram/`, `listBuddy_design/`) no puede
entrar en la app ni por import (capas) ni por herencia (conteo de métodos). Casos X1-X4 de QA, por carpeta.

Va en un archivo aparte porque los módulos de barandas no pueden importar pytest: el paso de CI los corre con
`python -I -S` antes de instalar dependencias.
"""
from __future__ import annotations

import pytest

from test_import_layers import report, violations
from test_module_size import all_errors


@pytest.mark.parametrize("folder", ["tests", "scripts", "engram", "listBuddy_design"])
def test_importing_code_from_an_unmeasured_folder_is_a_violation(folder: str) -> None:
    # X2 (L0 que trae QtWidgets desde scripts/) y X3 (módulo de 1.501 líneas en listBuddy_design/), por carpeta.
    sources = {"row_blocks": f"from {folder}.qa.qa_qt import QWidget\n",
               "db": f"def f() -> None:\n    from {folder}.qa import qa_big\n",
               "worker": f"import {folder}.qa.x as y\nimport importlib\nimportlib.import_module('{folder}.z')\n",
               "ui": ""}
    found = violations(sources)
    assert found.unmeasured == {("row_blocks", f"{folder}.qa.qa_qt"), ("row_blocks", f"{folder}.qa.qa_qt.QWidget"),
                                ("db", f"{folder}.qa"),
                                ("db", f"{folder}.qa.qa_big"), ("worker", f"{folder}.qa.x"),
                                ("worker", f"{folder}.z")}, found.unmeasured
    assert f"import de código no medido: db → {folder}.qa ({folder}/ queda fuera de las barandas)" in report(found)


@pytest.mark.parametrize("folder", ["tests", "scripts", "engram", "listBuddy_design"])
def test_a_base_from_an_unmeasured_folder_is_an_error(folder: str) -> None:
    # X1 (mixin en engram/ que hereda MainWindow) y X4 (mixin en tests/ que hereda FooterBar), por carpeta.
    src = (f"from {folder}.qa.qa_mix import Mix\nfrom {folder} import helper\nimport {folder}.qa.otro\n"
           "from PySide6.QtWidgets import QMainWindow\n"
           "class A(Mix, QMainWindow):\n    pass\nclass B(helper.Mix):\n    pass\n"
           f"class C({folder}.qa.otro.Mix):\n    pass\n")
    assert all_errors({"ui.py": src}, {}, {}) == [
        f"ui.py::A: base «Mix» viene de código no medido ({folder}/): la herencia esquivaría el límite",
        f"ui.py::B: base «helper.Mix» viene de código no medido ({folder}/): la herencia esquivaría el límite",
        f"ui.py::C: base «{folder}.qa.otro.Mix» viene de código no medido ({folder}/): la herencia esquivaría el límite",
    ]
