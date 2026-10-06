"""Corre snippets Qt en un intérprete aparte.

Mientras PyQt6 siga instalado, importar un módulo del proyecto y PySide6 en el
mismo proceso cargaría dos copias de las DLL de Qt 6.11.1: el subproceso lo evita
y además mantiene limpio el proceso de pytest.
"""
from __future__ import annotations

import os
import subprocess
import sys
import textwrap
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent


def run_isolated(code: str, timeout: float = 60.0) -> subprocess.CompletedProcess[str]:
    env = {
        **os.environ,
        "QT_QPA_PLATFORM": "offscreen",
        "PYTHONPATH": str(PROJECT_ROOT),
    }
    return subprocess.run(
        [sys.executable, "-c", textwrap.dedent(code)],
        cwd=PROJECT_ROOT,
        env=env,
        capture_output=True,
        text=True,
        timeout=timeout,
    )
