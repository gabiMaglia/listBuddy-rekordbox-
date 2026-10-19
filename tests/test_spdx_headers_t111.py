"""T-111 (LEG-30): cada módulo Python de la raíz declara su licencia y copyright al principio.

El encabezado SPDX es legible por máquina (REUSE/FSF) y hace que cada archivo, copiado por separado,
siga diciendo bajo qué licencia va; el copyright acompaña al aviso de LICENSE.
"""
from __future__ import annotations

import pathlib

ROOT = pathlib.Path(__file__).resolve().parents[1]
SPDX = "# SPDX-License-Identifier: GPL-3.0-or-later"
COPYRIGHT = "# Copyright (C) 2025-2026 Gabriel Maglia"


def _modules() -> list[pathlib.Path]:
    return sorted(ROOT.glob("*.py"))


def test_there_are_root_modules_to_check() -> None:
    assert len(_modules()) >= 30


def test_every_root_module_starts_with_spdx_and_copyright() -> None:
    bad = []
    for p in _modules():
        head = p.read_text(encoding="utf-8").splitlines()[:2]
        if head != [SPDX, COPYRIGHT]:
            bad.append(p.name)
    assert not bad, f"sin encabezado SPDX/copyright en las dos primeras líneas: {bad}"


def test_spdx_identifier_matches_license_file() -> None:
    lic = (ROOT / "LICENSE").read_text(encoding="utf-8")
    assert "SPDX-License-Identifier: GPL-3.0-or-later" in lic
    assert "Gabriel Maglia" in lic
