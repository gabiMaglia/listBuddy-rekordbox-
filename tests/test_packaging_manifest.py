"""T-033 / ADR-003: manifiestos de build sin PyQt6, onedir y sin UPX."""
from __future__ import annotations

import re

from _qt_isolated import PROJECT_ROOT

_SPEC = (PROJECT_ROOT / "rb_exporter.spec").read_text(encoding="utf-8")
_REQS = (PROJECT_ROOT / "requirements.txt").read_text(encoding="utf-8").splitlines()


def test_requirements_pin_pyside6_and_drop_pyqt6() -> None:
    assert "PySide6==6.12.0" in _REQS
    assert "shiboken6==6.12.0" in _REQS
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


def test_bundle_version_matches_app_version() -> None:
    ui_src = (PROJECT_ROOT / "ui.py").read_text(encoding="utf-8")
    version = re.search(r'^_APP_VERSION = "([^"]+)"', ui_src, re.M).group(1)
    assert f"'CFBundleVersion': '{version}'" in _SPEC
    assert f"'CFBundleShortVersionString': '{version}'" in _SPEC


def test_mac_bundle_uses_visible_brand_name() -> None:
    assert "name='List Buddy.app'" in _SPEC
    assert "'CFBundleDisplayName': 'List Buddy'" in _SPEC


def test_rekordbox_db_stack_is_not_shipped() -> None:
    assert not any(r.lower().startswith(("pyrekordbox", "sqlcipher3")) for r in _REQS)
    excludes = _SPEC.split("excludes=", 1)[1].split("]", 1)[0]
    for mod in ("'pyrekordbox'", "'sqlcipher3'", "'sqlalchemy'"):
        assert mod in excludes, mod
    assert "collect_data_files('pyrekordbox')" not in _SPEC
