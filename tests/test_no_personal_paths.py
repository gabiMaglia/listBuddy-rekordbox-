"""SEC-12: el repo es público; ninguna ruta personal del autor puede quedar versionada."""
from __future__ import annotations

import subprocess

from _qt_isolated import PROJECT_ROOT

# Partido a propósito para que este archivo no se delate a sí mismo.
_NEEDLE = "Users" + "/gabrielsk"


def test_no_tracked_file_contains_personal_home_path() -> None:
    r = subprocess.run(["git", "grep", "-l", "-I", _NEEDLE, "--", "."],
                       cwd=PROJECT_ROOT, capture_output=True, text=True)
    assert r.returncode == 1, f"rutas personales versionadas en:\n{r.stdout}"
