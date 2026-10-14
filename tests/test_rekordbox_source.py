"""T-080: fuente Rekordbox por XML en la ventana real."""
from __future__ import annotations

from _qt_isolated import PROJECT_ROOT, run_isolated
from _window_boot import BOOT

XML = (
    '<?xml version="1.0" encoding="UTF-8"?><DJ_PLAYLISTS Version="1.0.0">'
    '<COLLECTION Entries="1"><TRACK TrackID="1" Name="Uno" Artist="Ana" '
    'AverageBpm="128" Tonality="8A" Location="file://localhost/no/existe/uno.mp3"/>'
    '</COLLECTION><PLAYLISTS><NODE Type="0" Name="ROOT" Count="1">'
    '<NODE Type="0" Name="Sets" Count="1"><NODE Type="1" Name="Viernes" KeyType="0" Entries="1">'
    '<TRACK Key="1"/></NODE></NODE></NODE></PLAYLISTS></DJ_PLAYLISTS>'
)

LOAD = (
    "import pathlib, tempfile\n"
    "orig = ui.MainWindow._load_playlists_real\n"   # BOOT pisa _load_playlists, no el alias
    f"xml = pathlib.Path(tempfile.mkdtemp()) / 'rekordbox.xml'; xml.write_text({XML!r}, encoding='utf-8')\n"
)


def run(code: str) -> str:
    r = run_isolated(code)
    assert r.returncode == 0, r.stderr[-3000:]
    return r.stdout.strip().splitlines()[-1]


def test_no_app_module_imports_pyrekordbox_or_sqlcipher() -> None:
    offenders = []
    for p in PROJECT_ROOT.glob("*.py"):
        text = p.read_text(encoding="utf-8")
        if any(m in text for m in ("import pyrekordbox", "from pyrekordbox", "sqlcipher3")):
            offenders.append(p.name)
    assert offenders == []


def test_rekordbox_loads_playlists_from_the_chosen_xml() -> None:
    out = run(BOOT + LOAD +
        "w, s = make(); w._source = 'rekordbox'\n"
        "w._rb_xml_path = str(xml); orig(w); app.processEvents()\n"
        "print([c.name for c in w._all_cards], type(w._db).__name__)\n")
    assert out == "['Viernes'] RekordboxXmlLibrary"


def test_rekordbox_without_xml_shows_how_to_export_and_a_choose_button() -> None:
    out = run(BOOT + LOAD +
        "from PySide6.QtWidgets import QLabel, QPushButton\n"
        "w, s = make(); w._source = 'rekordbox'; w._rb_xml_path = ''; orig(w); app.processEvents()\n"
        "texts = ' '.join(l.text() for l in w.findChildren(QLabel))\n"
        "btns = [b.text() for b in w.findChildren(QPushButton) if b.objectName() == 'not_installed_btn']\n"
        "print('Exportá' in texts, btns)\n")
    assert out == "True ['Elegir rekordbox.xml…']"


def test_settings_row_is_about_the_xml() -> None:
    out = run(BOOT +
        "from PySide6.QtWidgets import QLabel\n"
        "w, s = make()\n"
        "texts = [l.text() for l in w.findChildren(QLabel)]\n"
        "print('Rekordbox · rekordbox.xml' in texts, any('master.db' in t for t in texts))\n")
    assert out == "True False"


def test_settings_rows_empty_text_and_clear_button_labels() -> None:
    out = run(BOOT +
        "from PySide6.QtWidgets import QPushButton\n"
        "w, s = make()\n"
        "def clear_label(edit):\n"
        "    btns = [b.text() for b in edit.parentWidget().findChildren(QPushButton)]\n"
        "    return btns[-1]\n"
        "print(w._rb_path_edit.text(), clear_label(w._rb_path_edit), "
        "w._tk_path_edit.text(), clear_label(w._tk_path_edit))\n")
    assert out == "(sin elegir) Quitar (automático) Auto"


REKORDBOX_HINT = "Reubicar"


def test_rekordbox_maintenance_actions_are_disabled_with_a_hint() -> None:
    out = run(BOOT +
        "w, s = make(); w._source = 'rekordbox'; w._sync_maintenance_for_source()\n"
        "print(w._act_relocate.isEnabled(), w._act_restore.isEnabled(), "
        f"{REKORDBOX_HINT!r} in w._act_relocate.toolTip())\n")
    assert out == "False False True"


def test_traktor_maintenance_actions_stay_enabled() -> None:
    out = run(BOOT +
        "w, s = make(); w._source = 'traktor'; w._sync_maintenance_for_source()\n"
        "w._set_relocate_state('idle')\n"
        "print(w._act_relocate.isEnabled(), w._act_restore.isEnabled())\n")
    assert out == "True True"


def test_idle_state_does_not_reenable_repair_for_rekordbox() -> None:
    out = run(BOOT +
        "w, s = make(); w._source = 'rekordbox'; w._sync_maintenance_for_source()\n"
        "w._set_relocate_state('idle'); w._set_maintenance_enabled(True)\n"
        "print(w._act_relocate.isEnabled(), w._act_restore.isEnabled())\n")
    assert out == "False False"


def test_start_relocate_never_runs_for_rekordbox() -> None:
    out = run(BOOT +
        "called = []\n"
        "ui.QFileDialog.getExistingDirectory = staticmethod(lambda *a, **k: called.append(1) or '/tmp')\n"
        "w, s = make(); w._source = 'rekordbox'; w._start_relocate()\n"
        "print(called, w._relocate_state)\n")
    assert out == "[] idle"


def test_preview_card_hides_repair_buttons_when_not_supported() -> None:
    out = run(BOOT +
        "from PySide6.QtWidgets import QPushButton\n"
        "from preview_card import PreviewGroupCard\n"
        "from preview_worker import GroupData, TrackRow\n"
        "rows = [TrackRow(num=f'{i:03d}', title='t', artist='', ext='.mp3', raw_path=f'/x/{i}.mp3', exists=i > 1) for i in range(5)]\n"
        "d = GroupData(name='P', order=1, total_count=5, tracks=rows)\n"
        "on = PreviewGroupCard(d, 'dark'); off = PreviewGroupCard(d, 'dark', can_repair=False)\n"
        "names = lambda c: sorted(b.objectName() for b in c.findChildren(QPushButton) if b.objectName().startswith('card_'))\n"
        "print(names(on), names(off))\n")
    assert out == "['card_repair_btn'] []"


def test_rekordbox_relocate_module_is_gone() -> None:
    assert not (PROJECT_ROOT / "rekordbox_relocate.py").exists()


# ───────────────────────── revisión final de la rama ─────────────────────────

def test_failed_load_clears_stale_db_and_blocks_restore_on_the_xml() -> None:
    out = run(BOOT + LOAD +
        "w, s = make(); w._source = 'rekordbox'; w._rb_xml_path = str(xml); orig(w)\n"
        "assert type(w._db).__name__ == 'RekordboxXmlLibrary'\n"
        "w._source = 'traktor'; w._tk_collection_path = '/no/existe/collection.nml'; orig(w)\n"
        "calls = []\n"
        "ui.list_backups = lambda *a, **k: calls.append(a) or []\n"
        "ui.dialogs.warning = lambda *a, **k: None\n"
        "w._sync_maintenance_for_source(); w._open_restore_backup_dialog()\n"
        "print(w._db is None, w._relocate_target_info(), calls)\n")
    assert out == "True ('collection.nml', None) []"


def run_lines(code: str) -> list[str]:
    r = run_isolated(code)
    assert r.returncode == 0, r.stderr[-3000:]
    return r.stdout.strip().splitlines()


def test_source_selector_is_locked_while_relocating() -> None:
    lines = run_lines(BOOT +
        "w, s = make(); w._source = 'traktor'; w._sync_maintenance_for_source()\n"
        "w._set_relocate_state('running')\n"
        "locked = (w._src_rb_btn.isEnabled(), w._src_tk_btn.isEnabled())\n"
        "w._src_rb_btn.click(); w._switch_source('rekordbox'); app.processEvents()\n"
        "print(locked, w._source, w._act_relocate.isEnabled(), w._act_relocate.text())\n"
        "w._set_relocate_state('cancelling')\n"
        "print(w._src_rb_btn.isEnabled())\n"
        "w._set_relocate_state('idle')\n"
        "print(w._src_rb_btn.isEnabled(), w._src_tk_btn.isEnabled())\n")
    assert lines[-3:] == ["(False, False) traktor True Cancelar", "False", "True True"]


def test_source_selector_is_locked_while_restoring() -> None:
    out = run(BOOT +
        "w, s = make(); w._source = 'traktor'\n"
        "w._set_maintenance_enabled(False)\n"
        "a = w._src_rb_btn.isEnabled(); w._switch_source('rekordbox')\n"
        "w._set_maintenance_enabled(True)\n"
        "print(a, w._source, w._src_rb_btn.isEnabled())\n")
    assert out == "False traktor True"


def test_reload_action_in_view_menu_clears_caches_and_reloads() -> None:
    lines = run_lines(BOOT +
        "w, s = make(); calls = []\n"
        "w._load_playlists = lambda: calls.append(1)\n"
        "w._track_meta_cache['x'] = []; w._exists_cache['y'] = True\n"
        "a = w._reload_action\n"
        "print(a.text(), bool(a.shortcut().toString()), [m.title() for m in a.associatedObjects() if hasattr(m, 'title')])\n"
        "a.trigger()\n"
        "print(calls, w._track_meta_cache, w._exists_cache)\n")
    assert lines[-2:] == ["Recargar librería True ['Ver']", "[1] {} {}"]


def test_reload_action_is_disabled_while_relocating_or_restoring() -> None:
    out = run(BOOT +
        "w, s = make(); a = w._reload_action\n"
        "w._set_relocate_state('running'); r1 = a.isEnabled(); w._set_relocate_state('idle')\n"
        "w._set_maintenance_enabled(False); r2 = a.isEnabled(); w._set_maintenance_enabled(True)\n"
        "print(r1, r2, a.isEnabled())\n")
    assert out == "False False True"


def test_rekordbox_button_tooltip_shows_export_date() -> None:
    out = run(BOOT + LOAD +
        "import datetime\n"
        "w, s = make(); w._source = 'rekordbox'; w._rb_xml_path = str(xml); orig(w)\n"
        "exp = w._db.exported_at.strftime('%d/%m/%Y %H:%M')\n"
        "print(w._src_rb_btn.toolTip() == f'XML exportado el {exp}')\n"
        "w._source = 'traktor'; w._tk_collection_path = '/no/existe.nml'; orig(w)\n"
        "print(w._src_rb_btn.toolTip() == '')\n")
    assert out == "True"


def test_export_from_xml_copies_numbered_files_and_reports_missing() -> None:
    # Camino real: rekordbox.xml -> reader -> ExportWorker.run() (síncrono, sin event loop).
    # El ancho del prefijo es el del worker: len(str(cantidad)) -> con 2 pistas, «1 - ».
    lines = run_lines(
        "import pathlib, tempfile\n"
        "import rekordbox_xml, worker\n"
        "tmp = pathlib.Path(tempfile.mkdtemp())\n"
        "audio = tmp / 'uno.mp3'; audio.write_bytes(b'abc')\n"
        "xml = tmp / 'rekordbox.xml'\n"
        "xml.write_text('<?xml version=\"1.0\"?><DJ_PLAYLISTS Version=\"1.0.0\"><COLLECTION>'\n"
        "  f'<TRACK TrackID=\"1\" Name=\"Uno\" Artist=\"Ana\" Location=\"file://localhost{audio}\"/>'\n"
        "  '<TRACK TrackID=\"2\" Name=\"Dos\" Artist=\"Beto\" Location=\"file://localhost/no/existe/dos.mp3\"/>'\n"
        "  '</COLLECTION><PLAYLISTS><NODE Type=\"0\" Name=\"ROOT\"><NODE Type=\"1\" Name=\"Set\" KeyType=\"0\">'\n"
        "  '<TRACK Key=\"1\"/><TRACK Key=\"2\"/></NODE></NODE></PLAYLISTS></DJ_PLAYLISTS>', encoding='utf-8')\n"
        "lib = rekordbox_xml.open_library(xml)\n"
        "pl = rekordbox_xml.get_playlist_tree(lib)[0]['playlist']\n"
        "dest = tmp / 'out'; done = []\n"
        "w = worker.ExportWorker([pl], dest); w.finished_ok.connect(lambda *a: done.append(a)); w.run()\n"
        "d = dest / 'Set'\n"
        "print(sorted(p.name for p in d.iterdir()), done)\n"
        "print((d / '_no_exportados.txt').read_text(encoding='utf-8').splitlines()[0].startswith('Dos'))\n"
    )
    assert lines[-2:] == ["['1 - Ana - Uno.mp3', '_no_exportados.txt'] [(1, 1, 0, 'ok')]", "True"]


def test_not_installed_card_text_is_not_clipped_in_the_narrow_column() -> None:
    out = run(BOOT + LOAD +
        "from PySide6.QtWidgets import QLabel\n"
        "w, s = make(); w.resize(1100, 720); w._source = 'rekordbox'; w._rb_xml_path = ''\n"
        "orig(w)\n"
        "for _ in range(5): app.processEvents()\n"
        "sub = w.findChild(QLabel, 'not_installed_sub')\n"
        "print(sub.height() >= sub.heightForWidth(sub.width()), sub.width() < 400)\n")
    assert out == "True True"
