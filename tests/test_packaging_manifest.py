"""T-033 / ADR-003: manifiestos de build sin PyQt6, onedir y sin UPX."""
from __future__ import annotations

import re

from _qt_isolated import PROJECT_ROOT

_SPEC = (PROJECT_ROOT / "rb_exporter.spec").read_text(encoding="utf-8")
_REQS = (PROJECT_ROOT / "requirements.txt").read_text(encoding="utf-8").splitlines()


def test_requirements_pin_pyside6_and_drop_pyqt6() -> None:
    assert "PySide6==6.11.1" in _REQS
    assert "shiboken6==6.11.1" in _REQS
    assert [r for r in _REQS if r.lower().startswith("pyqt")] == []


def test_spec_uses_pyside6_multimedia_and_excludes_pyqt6() -> None:
    assert "'PySide6.QtMultimedia'" in _SPEC
    assert "'PyQt6'" in _SPEC.split("excludes=", 1)[1].split("]", 1)[0]
    assert "PyQt6.QtMultimedia" not in _SPEC


def test_spec_never_enables_upx() -> None:
    # LGPL: comprimir las DLL de Qt complica que el usuario las reemplace.
    assert re.findall(r"upx\s*=\s*True", _SPEC) == []


def test_spec_windows_branch_is_onedir() -> None:
    windows = _SPEC.split("# ── Windows", 1)[1]
    assert "exclude_binaries=True" in windows
    assert "COLLECT(" in windows


def test_spec_bundles_fonts_and_qtsvg() -> None:
    assert "('fonts', 'fonts')" in _SPEC
    assert "'PySide6.QtSvg'" in _SPEC
