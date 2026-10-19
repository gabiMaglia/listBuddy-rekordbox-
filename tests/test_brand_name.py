"""T-071: el nombre visible de la marca es «List Buddy»; módulos/bundle no se renombran."""
from __future__ import annotations

import re

from _qt_isolated import PROJECT_ROOT, run_isolated
from _window_boot import BOOT

VISIBLE_CALL = re.compile(r"(setWindowTitle|QLabel|setText|setInformativeText)\(")


def test_no_source_line_sets_visible_text_with_old_brand() -> None:
    offenders = [
        f"{p.name}:{i}"
        for p in PROJECT_ROOT.glob("*.py")
        for i, line in enumerate(p.read_text(encoding="utf-8").splitlines(), 1)
        if VISIBLE_CALL.search(line) and "listBuddy" in line
    ]
    assert offenders == []


def test_no_visible_widget_text_or_window_title_says_listbuddy() -> None:
    r = run_isolated(
        BOOT
        + "from PySide6.QtWidgets import QLabel, QPushButton, QWidget\n"
        "w, _ = make()\n"
        "d = ui.AboutDialog('1.0.0', 'dark', w); d.show(); app.processEvents()\n"
        "texts = [w.windowTitle(), d.windowTitle()]\n"
        "for root in (w, d):\n"
        "    for c in root.findChildren(QWidget):\n"
        "        for attr in ('text', 'toolTip', 'accessibleName'):\n"
        "            f = getattr(c, attr, None)\n"
        "            if callable(f):\n"
        "                v = f()\n"
        "                if isinstance(v, str): texts.append(v)\n"
        "assert 'List Buddy' in w.windowTitle(), w.windowTitle()\n"
        "assert 'List Buddy' in d.windowTitle(), d.windowTitle()\n"
        "bad = [t for t in texts if 'listBuddy' in t]\n"
        "assert bad == [], bad\n"
        "print('ok')\n"
    )
    assert r.returncode == 0 and "ok" in r.stdout, r.stderr[-2000:]


def test_capture_script_uses_temp_settings_not_repo_ini() -> None:
    src = (PROJECT_ROOT / "engram/plans/design/capture.py").read_text(encoding="utf-8")
    assert "settings_path=" in src
    assert "tempfile" in src
