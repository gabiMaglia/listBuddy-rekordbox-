"""T-109 / LEG-23 + SEC-22: rekordbox_fixes.json 0600 y carpetas de datos/logs 0700."""
from __future__ import annotations

import stat
import sys
from pathlib import Path

import pytest

import app_logging
import app_paths
from rekordbox_fixes import FixStore

posix_only = pytest.mark.skipif(sys.platform.startswith("win"), reason="permisos POSIX")


def _mode(p: Path) -> int:
    return stat.S_IMODE(p.stat().st_mode)


@posix_only
def test_new_fixes_json_is_0600(tmp_path: Path) -> None:
    store = FixStore(tmp_path / "rekordbox_fixes.json")
    store.save({"file://localhost/a.mp3": str(tmp_path / "a.mp3")})
    assert _mode(store.path) == 0o600


@posix_only
def test_existing_0644_fixes_json_is_tightened_on_write(tmp_path: Path) -> None:
    p = tmp_path / "rekordbox_fixes.json"
    p.write_text("{}")
    p.chmod(0o644)
    FixStore(p).merge({"k": str(tmp_path / "x.mp3")})
    assert _mode(p) == 0o600


@posix_only
def test_make_private_on_a_directory_is_0700(tmp_path: Path) -> None:
    d = tmp_path / "datos"
    d.mkdir(mode=0o755)
    app_paths.make_private(d)
    assert _mode(d) == 0o700


@posix_only
def test_data_dir_is_0700(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(Path, "home", staticmethod(lambda: tmp_path))
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "cfg"))
    assert _mode(app_paths.data_dir()) == 0o700


@posix_only
def test_log_dir_is_0700(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(Path, "home", staticmethod(lambda: tmp_path))
    assert _mode(app_logging.log_dir()) == 0o700


def test_make_private_dir_is_noop_on_windows(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    d = tmp_path / "w"
    d.mkdir()
    before = _mode(d)
    monkeypatch.setattr(sys, "platform", "win32")
    app_paths.make_private(d)
    assert _mode(d) == before


def test_disclaimer_section_8_names_every_stored_file_and_is_true() -> None:
    text = " ".join((Path(__file__).resolve().parent.parent / "DISCLAIMER.md")
                    .read_text(encoding="utf-8").split())
    for needle in ("rekordbox_fixes.json", "listBuddy_backups/", "retención de 10"):
        assert needle in text, needle
    assert "se crean legibles solo por tu usuario" not in text
