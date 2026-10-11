"""T-062: header (marca, selector, Mantenimiento, ajustes, tema, Apoyar)."""
from __future__ import annotations

from _qt_isolated import PROJECT_ROOT, run_isolated
from _window_boot import BOOT


def run(code: str):
    r = run_isolated(BOOT + code)
    assert r.returncode == 0, r.stderr[-2000:]
    return r.stdout


def test_settings_path_is_injected_and_repo_ini_untouched() -> None:
    repo_ini = PROJECT_ROOT / ".rbe_settings.ini"
    before = repo_ini.stat().st_mtime_ns if repo_ini.exists() else None
    out = run(
        "w, tmp = make()\n"
        "w.settings.setValue('probe', 1); w.settings.sync()\n"
        "print(w.settings.fileName() == str(tmp), tmp.exists())\n"
    )
    assert out.split()[-2:] == ["True", "True"]
    after = repo_ini.stat().st_mtime_ns if repo_ini.exists() else None
    assert before == after


def test_new_icons_are_registered_and_render() -> None:
    out = run(
        "import icons\n"
        "for n in ('wrench', 'logo', 'dot'):\n"
        "    assert n in icons.ICON_NAMES, n\n"
        "    px = icons.pixmap(n, '#f0a93b', 22)\n"
        "    assert any(px.toImage().pixelColor(x, y).alpha() > 0\n"
        "               for x in range(px.width()) for y in range(px.height())), n\n"
        "print('ok')\n"
    )
    assert out.split()[-1] == "ok"


def test_broken_badge_text() -> None:
    out = run(
        "from ui_components import broken_badge_text as b\n"
        "print(repr(b(0)) + '|' + repr(b(-3)) + '|' + repr(b(1)) + '|' + repr(b(30)))\n"
    )
    assert out.strip().splitlines()[-1] == "''|''|'1 roto'|'30 rotos'"


def test_maintenance_button_badge_and_compact() -> None:
    out = run(
        "from PySide6.QtWidgets import QLabel\n"
        "from ui_components import MaintenanceButton\n"
        "b = MaintenanceButton(); b.show(); app.processEvents()\n"
        "badge = b.findChild(QLabel, 'maint_badge'); text = b.findChild(QLabel, 'maint_text')\n"
        "assert text.text() == 'Mantenimiento'\n"
        "assert not badge.isVisible()\n"
        "b.set_broken(30); app.processEvents()\n"
        "assert badge.isVisible() and badge.text() == '30 rotos'\n"
        "b.set_compact(True); app.processEvents()\n"
        "assert not text.isVisible() and badge.isVisible()\n"
        "assert b.toolTip() == 'Mantenimiento'\n"
        "b.set_compact(False); b.set_broken(0); app.processEvents()\n"
        "assert text.isVisible() and not badge.isVisible()\n"
        "print('ok')\n"
    )
    assert out.split()[-1] == "ok"
