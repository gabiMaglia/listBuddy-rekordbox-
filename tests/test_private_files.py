"""SEC-11: log y settings.ini quedan legibles solo por el usuario en POSIX."""
from __future__ import annotations

import logging
import stat
import sys
from pathlib import Path

import pytest

import app_logging
from _qt_isolated import run_isolated
from _window_boot import BOOT

posix_only = pytest.mark.skipif(sys.platform.startswith("win"), reason="permisos POSIX")


def _mode(p: Path) -> int:
    return stat.S_IMODE(p.stat().st_mode)


@pytest.fixture
def fresh_logging(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(app_logging, "log_dir", lambda: tmp_path)
    root = logging.getLogger()
    saved = root.handlers[:]
    yield tmp_path
    for h in root.handlers:
        h.close()
    root.handlers[:] = saved


@posix_only
def test_new_log_is_0600(fresh_logging: Path) -> None:
    path = app_logging.setup_logging("t")
    assert _mode(path) == 0o600


@posix_only
def test_existing_0644_log_is_tightened(fresh_logging: Path) -> None:
    p = fresh_logging / "listBuddy.log"
    p.write_text("viejo\n")
    p.chmod(0o644)
    old = fresh_logging / "listBuddy.log.1"
    old.write_text("rotado\n")
    old.chmod(0o644)
    app_logging.setup_logging("t")
    assert _mode(p) == 0o600 and _mode(old) == 0o600


@posix_only
def test_rotated_log_files_are_0600(fresh_logging: Path) -> None:
    path = app_logging.setup_logging("t")
    handler = next(h for h in logging.getLogger().handlers if hasattr(h, "doRollover"))
    handler.doRollover()
    logging.getLogger("listBuddy").info("después de rotar")
    handler.flush()
    assert _mode(path) == 0o600
    assert _mode(path.with_name("listBuddy.log.1")) == 0o600


@posix_only
def test_settings_ini_is_0600_new_and_existing(tmp_path: Path) -> None:
    out = run_isolated(
        BOOT +
        "import os, stat, tempfile, pathlib\n"
        "d = pathlib.Path(tempfile.mkdtemp())\n"
        "old = d / 'old.ini'; old.write_text('[General]\\ntheme=dark\\n'); old.chmod(0o644)\n"
        "res = []\n"
        "for p in (d / 'new.ini', old):\n"
        "    w = ui.MainWindow(settings_path=p); w.settings.setValue('x', 1); w.settings.sync()\n"
        "    res.append(oct(stat.S_IMODE(p.stat().st_mode)))\n"
        "print(res)\n"
    )
    assert out.returncode == 0, out.stderr[-3000:]
    assert out.stdout.strip().splitlines()[-1] == "['0o600', '0o600']"
