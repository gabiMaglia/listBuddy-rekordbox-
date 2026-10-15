"""T-081: reparar enlaces del XML de Rekordbox sin tocar el XML.

Sin Qt en el proceso de pytest: `rekordbox_xml_relocate` importa
`relocate_core` (QThread), así que todo lo que lo usa corre con `run_isolated`.
"""
from __future__ import annotations

from pathlib import Path

from _qt_isolated import run_isolated
import rekordbox_xml as rx


def _xml(tmp: Path, music: Path) -> Path:
    ok = music / "ok.mp3"
    ok.write_bytes(b"x")
    loc_ok = rx.path_to_location(ok)
    loc_gone = rx.path_to_location(tmp / "viejo" / "perdido.mp3")
    xml = tmp / "rekordbox.xml"
    xml.write_text(
        '<?xml version="1.0" encoding="UTF-8"?><DJ_PLAYLISTS Version="1.0.0"><COLLECTION Entries="2">'
        f'<TRACK TrackID="1" Name="Ok" Artist="A" Location="{loc_ok}"/>'
        f'<TRACK TrackID="2" Name="Perdido" Artist="B" Location="{loc_gone}"/>'
        '</COLLECTION><PLAYLISTS><NODE Type="0" Name="ROOT" Count="2">'
        '<NODE Type="1" Name="L1" KeyType="0" Entries="2"><TRACK Key="1"/><TRACK Key="2"/></NODE>'
        '<NODE Type="1" Name="L2" KeyType="0" Entries="1"><TRACK Key="2"/></NODE>'
        '</NODE></PLAYLISTS></DJ_PLAYLISTS>', encoding="utf-8")
    return xml


def test_broken_tracks_are_unique_by_location(tmp_path: Path) -> None:
    music = tmp_path / "m"; music.mkdir()
    xml = _xml(tmp_path, music)
    r = run_isolated(
        "from pathlib import Path\n"
        "import rekordbox_xml as rx\n"
        "from rekordbox_xml_relocate import find_broken_tracks\n"
        f"lib = rx.open_library(Path({str(xml)!r}))\n"
        "broken = find_broken_tracks(lib)\n"
        "assert [b.title for _, b in broken] == ['Perdido'], broken\n"
        "assert broken[0][0] == broken[0][1].location\n"
        "print('OK')\n"
    )
    assert r.returncode == 0, r.stderr[-2000:]
    assert r.stdout.strip().splitlines()[-1] == "OK"


def test_scope_limits_to_the_playlist_paths(tmp_path: Path) -> None:
    music = tmp_path / "m"; music.mkdir()
    xml = _xml(tmp_path, music)
    r = run_isolated(
        "from pathlib import Path\n"
        "import rekordbox_xml as rx\n"
        "from relocate_core import RelocateScope\n"
        "from rekordbox_xml_relocate import find_broken_tracks\n"
        f"lib = rx.open_library(Path({str(xml)!r}))\n"
        f"scope = RelocateScope('L1', frozenset({{{str(music / 'ok.mp3')!r}}}))\n"
        "assert find_broken_tracks(lib, scope=scope) == []\n"
        "print('OK')\n"
    )
    assert r.returncode == 0, r.stderr[-2000:]
    assert r.stdout.strip().splitlines()[-1] == "OK"


def test_worker_saves_fixes_and_never_touches_the_xml(tmp_path: Path) -> None:
    music = tmp_path / "m"; music.mkdir()
    xml = _xml(tmp_path, music)
    before = xml.read_bytes()
    nuevo = tmp_path / "nuevo"; nuevo.mkdir(); (nuevo / "perdido.mp3").write_bytes(b"y")
    fixes = tmp_path / "rekordbox_fixes.json"
    r = run_isolated(
        "from pathlib import Path\n"
        "from PySide6.QtCore import QCoreApplication\n"
        "app = QCoreApplication([])\n"
        "from rekordbox_xml_relocate import RekordboxXmlRelocateWorker\n"
        "done = []\n"
        f"w = RekordboxXmlRelocateWorker(Path({str(xml)!r}), Path({str(fixes)!r}), Path({str(nuevo)!r}))\n"
        "w.finished_ok.connect(lambda *a: done.append(a))\n"
        "w.run()\n"
        "print(done[-1])\n"
    )
    assert r.returncode == 0, r.stderr[-2000:]
    assert r.stdout.strip().splitlines()[-1] == "(1, 0, 0, 'ok')"
    assert xml.read_bytes() == before
    from rekordbox_fixes import FixStore
    assert list(FixStore(fixes).load().values()) == [str(nuevo / "perdido.mp3")]


def test_worker_with_nothing_found_writes_nothing(tmp_path: Path) -> None:
    music = tmp_path / "m"; music.mkdir()
    xml = _xml(tmp_path, music)
    vacio = tmp_path / "vacio"; vacio.mkdir()
    fixes = tmp_path / "rekordbox_fixes.json"
    r = run_isolated(
        "from pathlib import Path\n"
        "from PySide6.QtCore import QCoreApplication\n"
        "app = QCoreApplication([])\n"
        "from rekordbox_xml_relocate import RekordboxXmlRelocateWorker\n"
        "done = []\n"
        f"w = RekordboxXmlRelocateWorker(Path({str(xml)!r}), Path({str(fixes)!r}), Path({str(vacio)!r}))\n"
        "w.finished_ok.connect(lambda *a: done.append(a))\n"
        "w.run()\n"
        "print(done[-1])\n"
    )
    assert r.returncode == 0, r.stderr[-2000:]
    assert r.stdout.strip().splitlines()[-1] == "(0, 0, 1, 'ok')"
    assert not fixes.exists()
