"""T-109 / LEG-25: las capturas de diseño no viajan en el tarball ni están en el HEAD."""
from __future__ import annotations

import subprocess
import tarfile
import io

from _qt_isolated import PROJECT_ROOT


def _git(*args: str) -> bytes:
    return subprocess.run(["git", *args], cwd=PROJECT_ROOT, check=True, capture_output=True).stdout


def test_design_uploads_not_tracked() -> None:
    assert _git("ls-files", "listBuddy_design/uploads").strip() == b""


def test_source_archive_excludes_design_folder() -> None:
    # Se arma sobre el índice (write-tree) para que valga también antes del commit.
    tree = _git("write-tree").decode().strip()
    names = tarfile.open(fileobj=io.BytesIO(_git("archive", tree))).getnames()
    assert not [n for n in names if n.startswith("listBuddy_design")]
