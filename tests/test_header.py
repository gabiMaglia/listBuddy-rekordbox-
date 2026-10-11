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


def test_brand_appears_exactly_once() -> None:
    out = run(
        "from PySide6.QtWidgets import QLabel\n"
        "w, _ = make()\n"
        "print(sum(1 for l in w.findChildren(QLabel) if l.text() == 'listBuddy'))\n"
    )
    assert out.split()[-1] == "1"  # hoy son 2 (header_title + brand_name del rack head)


def test_header_is_56px_and_hosts_source_switcher_and_controls() -> None:
    out = run(
        "from PySide6.QtWidgets import QPushButton\n"
        "w, _ = make()\n"
        "bar = w.findChild(ui.QWidget, 'header_bar')\n"
        "assert bar.height() == 56, bar.height()\n"
        "for name in ('_src_rb_btn', '_src_tk_btn', '_maint_btn', '_settings_btn', '_theme_btn', '_donate_btn'):\n"
        "    assert bar.isAncestorOf(getattr(w, name)), name\n"
        "assert w.findChild(ui.QWidget, 'header_eyebrow') is None\n"
        "print('ok')\n"
    )
    assert out.split()[-1] == "ok"


def test_source_switch_from_header_updates_state() -> None:
    out = run(
        "w, _ = make()\n"
        "w._src_tk_btn.click(); app.processEvents()\n"
        "assert w._source == 'traktor'\n"
        "assert w._src_tk_btn.property('src_active') == 'true'\n"
        "assert w._src_rb_btn.property('src_active') == 'false'\n"
        "w._src_rb_btn.click(); app.processEvents()\n"
        "assert w._source == 'rekordbox'\n"
        "print('ok')\n"
    )
    assert out.split()[-1] == "ok"


def test_theme_button_toggles_and_persists() -> None:
    out = run(
        "w, tmp = make()\n"
        "assert w._theme == 'dark'\n"
        "w._theme_btn.click(); app.processEvents()\n"
        "assert w._theme == 'light'\n"
        "w._theme_btn.click(); app.processEvents()\n"
        "assert w._theme == 'dark'\n"
        "assert w._theme_btn.toolTip() == 'Cambiar tema'\n"
        "assert not hasattr(w, '_sun_btn')\n"
        "print('ok')\n"
    )
    assert out.split()[-1] == "ok"


def test_left_column_no_longer_has_source_switcher() -> None:
    out = run(
        "left = (w := make()[0]).findChild(ui.QWidget, 'left_col')\n"
        "assert left.findChild(ui.QWidget, 'source_switcher') is None\n"
        "print('ok')\n"
    )
    assert out.split()[-1] == "ok"


MENU_TEXTS = [
    "Reparar enlaces rotos…",
    "Restaurar copia de seguridad…",
    "Resolver automáticamente con la mejor coincidencia",
]


def test_maintenance_menu_has_the_three_actions_and_left_column_lost_relocate() -> None:
    out = run(
        "from PySide6.QtWidgets import QPushButton, QCheckBox\n"
        "w, _ = make()\n"
        "acts = [a.text() for a in w._maint_menu.actions() if not a.isSeparator()]\n"
        "print('|'.join(acts))\n"
        "assert w._act_auto.isCheckable() and not w._act_auto.isChecked()\n"
        "left = w.findChild(ui.QWidget, 'left_col')\n"
        "assert left.findChild(QPushButton, 'relocate_btn') is None\n"
        "assert left.findChild(QPushButton, 'restore_backup_btn') is None\n"
        "assert left.findChild(QCheckBox, 'relocate_auto_chk') is None\n"
    )
    assert out.strip().splitlines()[-1] == "|".join(MENU_TEXTS)


def test_menu_actions_fire_the_same_flows_as_before() -> None:
    out = run(
        "calls = []\n"
        "ui.MainWindow._start_relocate = lambda self: calls.append('relocate')\n"
        "ui.MainWindow._open_restore_backup_dialog = lambda self: calls.append('restore')\n"
        "w, _ = make()\n"
        "w._act_relocate.trigger(); w._act_restore.trigger()\n"
        "print(calls)\n"
    )
    assert out.strip().splitlines()[-1] == "['relocate', 'restore']"


def test_relocate_action_becomes_cancel_while_running() -> None:
    out = run(
        "calls = []\n"
        "ui.MainWindow._start_relocate = lambda self: calls.append('start')\n"
        "ui.MainWindow._cancel_relocate = lambda self: calls.append('cancel')\n"
        "w, _ = make()\n"
        "w._set_relocate_state('running')\n"
        "assert w._act_relocate.text() == 'Cancelar'\n"
        "w._act_relocate.trigger()\n"
        "w._set_relocate_state('cancelling')\n"
        "assert w._act_relocate.text() == 'Cancelando…' and not w._act_relocate.isEnabled()\n"
        "w._set_relocate_state('idle')\n"
        "assert w._act_relocate.text() == 'Reparar enlaces rotos…' and w._act_relocate.isEnabled()\n"
        "w._act_relocate.trigger()\n"
        "print(calls)\n"
    )
    assert out.strip().splitlines()[-1] == "['cancel', 'start']"


def test_auto_resolve_starts_off_and_is_not_persisted() -> None:
    out = run(
        "w, tmp = make()\n"
        "assert w._auto_resolve_enabled() is False\n"
        "w._act_auto.trigger(); w.settings.sync()\n"
        "assert w._auto_resolve_enabled() is True\n"
        "assert 'relocate_auto_resolve' not in tmp.read_text() if tmp.exists() else True\n"
        "w2 = ui.MainWindow(settings_path=tmp)\n"
        "assert w2._auto_resolve_enabled() is False and not w2._act_auto.isChecked()\n"
        "print('ok')\n"
    )
    assert out.split()[-1] == "ok"


def test_restore_in_flight_disables_both_maintenance_actions() -> None:
    out = run(
        "w, _ = make()\n"
        "w._set_maintenance_enabled(False)\n"
        "assert not w._act_relocate.isEnabled() and not w._act_restore.isEnabled()\n"
        "w._set_maintenance_enabled(True)\n"
        "assert w._act_relocate.isEnabled() and w._act_restore.isEnabled()\n"
        "print('ok')\n"
    )
    assert out.split()[-1] == "ok"


def test_badge_is_hidden_with_zero_broken() -> None:
    out = run(
        "from PySide6.QtWidgets import QLabel\n"
        "from preview_worker import GroupData, TrackRow\n"
        "w, _ = make()\n"
        "ok = [TrackRow('001', 'a', 'x', 'mp3', '/a.mp3', True)]\n"
        "w._queue_group(GroupData('pl', 1, 1, ok)); app.processEvents()\n"
        "badge = w._maint_btn.findChild(QLabel, 'maint_badge')\n"
        "print(w._broken_total, badge.isVisible())\n"
    )
    assert out.strip().splitlines()[-1] == "0 False"


def test_badge_accumulates_across_groups_and_resets_on_clear() -> None:
    out = run(
        "from PySide6.QtWidgets import QLabel\n"
        "from preview_worker import GroupData, TrackRow\n"
        "def tr(n, ex): return TrackRow(f'{n:03d}', 't', 'a', 'mp3', f'/{n}.mp3', ex)\n"
        "w, _ = make()\n"
        "badge = w._maint_btn.findChild(QLabel, 'maint_badge')\n"
        "w._queue_group(GroupData('A', 1, 3, [tr(1, False), tr(2, True), tr(3, False)]))\n"
        "w._queue_group(GroupData('B', 2, 2, [tr(1, False), tr(2, True)]))\n"
        "app.processEvents()\n"
        "assert w._broken_total == 3 and badge.text() == '3 rotos' and badge.isVisible()\n"
        "w._clear_preview_layout(); app.processEvents()\n"
        "assert w._broken_total == 0 and not badge.isVisible()\n"
        "print('ok')\n"
    )
    assert out.split()[-1] == "ok"


def test_badge_singular() -> None:
    out = run(
        "from PySide6.QtWidgets import QLabel\n"
        "w, _ = make(); w._set_broken_total(1); app.processEvents()\n"
        "print(w._maint_btn.findChild(QLabel, 'maint_badge').text())\n"
    )
    assert out.strip().splitlines()[-1] == "1 roto"
