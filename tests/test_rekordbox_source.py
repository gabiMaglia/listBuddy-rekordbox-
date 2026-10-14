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
        if p.name == "rekordbox_relocate.py":  # lo borra la Task 3 de T-080
            continue
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
