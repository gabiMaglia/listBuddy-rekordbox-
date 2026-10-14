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
