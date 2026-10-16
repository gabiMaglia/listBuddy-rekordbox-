"""D-14 / T-090 QA D1: ningún marcador pendiente del PO puede llegar a un release."""
from __future__ import annotations

import os
import subprocess

import pytest

from _qt_isolated import PROJECT_ROOT

_MARKER = "[A DEFINIR POR EL PO"
_FILES = ("DISCLAIMER.md", "about_dialog.py", "README.md", "branding.py")

_gate_off = pytest.mark.skipif(
    os.environ.get("LISTBUDDY_RELEASE_GATE") != "1",
    reason="gate de release: se activa con LISTBUDDY_RELEASE_GATE=1 (release_mac.sh)",
)


def _offenders(root=PROJECT_ROOT) -> list[str]:
    return [n for n in _FILES if (root / n).exists() and _MARKER in (root / n).read_text(encoding="utf-8")]


@pytest.mark.release_gate
@_gate_off
def test_no_pending_po_markers() -> None:
    assert _offenders() == [], f"Marcadores pendientes del PO en: {_offenders()}"


def test_offenders_detects_marker(tmp_path) -> None:
    (tmp_path / "DISCLAIMER.md").write_text(f"x {_MARKER}: email]", encoding="utf-8")
    (tmp_path / "README.md").write_text("limpio", encoding="utf-8")
    assert _offenders(tmp_path) == ["DISCLAIMER.md"]


def test_release_script_runs_the_gate() -> None:
    text = (PROJECT_ROOT / "scripts" / "release_mac.sh").read_text(encoding="utf-8")
    assert "LISTBUDDY_RELEASE_GATE=1" in text and "test_release_gate.py" in text


def test_release_script_aborts_with_markers_and_passes_without(tmp_path) -> None:
    """Corre solo el tramo del gate del script, contra una copia mínima del repo."""
    script = (PROJECT_ROOT / "scripts" / "release_mac.sh").read_text(encoding="utf-8")
    snippet = script[script.index("# ── Gate de release"):script.index("# ── fin gate")]
    for content, expected in ((f"x {_MARKER}: y]", 1), ("limpio", 0)):
        (tmp_path / "DISCLAIMER.md").write_text(content, encoding="utf-8")
        for n in ("about_dialog.py", "README.md", "branding.py"):
            (tmp_path / n).write_text("ok", encoding="utf-8")
        r = subprocess.run(["bash", "-c", "set -euo pipefail\n" + snippet],
                           cwd=tmp_path, capture_output=True, text=True)
        assert r.returncode == expected, r.stderr
        if expected:
            assert "DISCLAIMER.md" in r.stderr
