"""T-080: lector del rekordbox.xml oficial (sin master.db)."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

import rekordbox_xml as rx

XML = """<?xml version="1.0" encoding="UTF-8"?>
<DJ_PLAYLISTS Version="1.0.0">
  <PRODUCT Name="rekordbox" Version="7.1.0" Company="AlphaTheta"/>
  <COLLECTION Entries="4">
    <TRACK TrackID="1" Name="Uno" Artist="Ana" AverageBpm="128.00" Tonality="8A"
           Location="file://localhost/Users/gab/Music/uno.mp3"/>
    <TRACK TrackID="2" Name="Dos &amp; Tres" Artist="" AverageBpm="0" Tonality=""
           Location="file://localhost/Users/gab/Music/Bj%C3%B6rk%20-%20dos.flac"/>
    <TRACK TrackID="3" Name="Tres" Artist="Cami" AverageBpm="122.5" Tonality="Am"
           Location="file://localhost/Users/gab/Music/tres.wav"/>
    <TRACK TrackID="4" Name="Sin playlist" Artist="X"
           Location="file://localhost/Users/gab/Music/x.mp3"/>
  </COLLECTION>
  <PLAYLISTS>
    <NODE Type="0" Name="ROOT" Count="2">
      <NODE Type="0" Name="Sets" Count="1">
        <NODE Type="1" Name="Viernes" KeyType="0" Entries="3">
          <TRACK Key="3"/><TRACK Key="1"/><TRACK Key="99"/><TRACK Key="2"/>
        </NODE>
      </NODE>
      <NODE Type="1" Name="Por ruta" KeyType="1" Entries="1">
        <TRACK Key="file://localhost/Users/gab/Music/uno.mp3"/>
      </NODE>
    </NODE>
  </PLAYLISTS>
</DJ_PLAYLISTS>
"""


@pytest.fixture
def lib(tmp_path: Path) -> rx.RekordboxXmlLibrary:
    p = tmp_path / "rekordbox.xml"
    p.write_text(XML, encoding="utf-8")
    return rx.open_library(p)


def test_tree_keeps_folders_and_playlists_without_root(lib) -> None:
    tree = rx.get_playlist_tree(lib)
    assert [n["playlist"].Name for n in tree] == ["Sets", "Por ruta"]
    sets = tree[0]
    assert sets["playlist"].is_folder and not sets["playlist"].is_playlist
    assert [c["playlist"].Name for c in sets["children"]] == ["Viernes"]
    assert tree[1]["playlist"].is_playlist and tree[1]["children"] == []


def test_playlist_order_is_xml_order_and_unknown_keys_are_skipped(lib) -> None:
    viernes = rx.get_playlist_tree(lib)[0]["children"][0]["playlist"]
    songs = rx.get_songs(viernes)
    assert [s.Title for s in songs] == ["Tres", "Uno", "Dos & Tres"]
    assert [s.TrackNo for s in songs] == [1, 2, 3]
    assert rx.playlist_song_count(viernes) == 3
    assert viernes.Songs == songs


def test_keytype_location_resolves_by_uri(lib) -> None:
    por_ruta = rx.get_playlist_tree(lib)[1]["playlist"]
    assert [s.Title for s in rx.get_songs(por_ruta)] == ["Uno"]


def test_track_exposes_the_duck_typed_fields_the_app_uses(lib) -> None:
    uno = rx.get_songs(rx.get_playlist_tree(lib)[1]["playlist"])[0]
    assert uno.Content is uno and uno.content is uno
    assert uno.ArtistName == "Ana" and uno.key == "8A" and uno.bpm == 128.0
    assert uno.FolderPath == str(Path("/Users/gab/Music/uno.mp3"))
    assert not hasattr(uno, "BPM")          # db.key_bpm_of lee BPM×100 de pyrekordbox
    dos = rx.get_songs(rx.get_playlist_tree(lib)[0]["children"][0]["playlist"])[2]
    assert dos.bpm is None and dos.key == "" and dos.ArtistName == ""


def test_playlist_ids_are_unique_paths(lib) -> None:
    tree = rx.get_playlist_tree(lib)
    assert tree[0]["children"][0]["playlist"].ID == "Sets/Viernes"
    assert tree[1]["playlist"].ID == "Por ruta"


def test_location_decodes_percent_escapes() -> None:
    p = rx.location_to_path("file://localhost/Users/gab/Music/Bj%C3%B6rk%20-%20dos.flac")
    assert p == Path("/Users/gab/Music/Björk - dos.flac")


@pytest.mark.skipif(sys.platform != "win32", reason="rutas con letra de unidad")
def test_location_windows_drive() -> None:
    p = rx.location_to_path("file://localhost/C:/Users/gab/Music/a%20b.mp3")
    assert p == Path("C:/Users/gab/Music/a b.mp3")


def test_location_windows_drive_is_stripped_of_leading_slash_on_any_os() -> None:
    assert rx.location_to_path("file://localhost/D:/M/a.mp3").as_posix() == "D:/M/a.mp3"


def test_location_network_host_keeps_unc_form() -> None:
    assert rx.location_to_path("file://nas/share/a.mp3").as_posix() == "//nas/share/a.mp3"


def test_missing_path_asks_to_choose_the_file() -> None:
    with pytest.raises(RuntimeError, match="Exportá"):
        rx.open_library(None)


def test_nonexistent_file_says_so(tmp_path: Path) -> None:
    with pytest.raises(RuntimeError, match="No se encontró"):
        rx.open_library(tmp_path / "nada.xml")


def test_broken_xml_is_a_friendly_error(tmp_path: Path) -> None:
    p = tmp_path / "rekordbox.xml"
    p.write_text("<DJ_PLAYLISTS><COLL", encoding="utf-8")
    with pytest.raises(RuntimeError, match="no se pudo leer"):
        rx.open_library(p)


def test_other_xml_is_rejected(tmp_path: Path) -> None:
    p = tmp_path / "otro.xml"
    p.write_text("<NML/>", encoding="utf-8")
    with pytest.raises(RuntimeError, match="no es un XML de Rekordbox"):
        rx.open_library(p)


def test_exported_at_is_the_file_mtime(lib) -> None:
    assert lib.exported_at.timestamp() == pytest.approx(lib.path.stat().st_mtime, abs=1)


def test_location_keeps_hash_and_question_mark_in_the_name() -> None:
    assert rx.location_to_path("file://localhost/x/Track #1.mp3").as_posix() == "/x/Track #1.mp3"
    assert rx.location_to_path("file://localhost/x/Qu%C3%A9? mp3.mp3").as_posix() == "/x/Qué? mp3.mp3"
    assert rx.location_to_path("file:///x/a#b.mp3").as_posix() == "/x/a#b.mp3"


def _lib_from(tmp_path: Path, body: str, collection: str) -> rx.RekordboxXmlLibrary:
    p = tmp_path / "r.xml"
    p.write_text(
        '<?xml version="1.0"?><DJ_PLAYLISTS Version="1.0.0"><COLLECTION>'
        f"{collection}</COLLECTION><PLAYLISTS><NODE Type=\"0\" Name=\"ROOT\">{body}"
        "</NODE></PLAYLISTS></DJ_PLAYLISTS>",
        encoding="utf-8",
    )
    return rx.open_library(p)


def test_tracks_without_location_or_file_name_are_skipped_and_numbering_stays_contiguous(tmp_path) -> None:
    coll = (
        '<TRACK TrackID="1" Name="A" Location="file://localhost/m/a.mp3"/>'
        '<TRACK TrackID="2" Name="Vacio" Location=""/>'
        '<TRACK TrackID="3" Name="SinLoc"/>'
        '<TRACK TrackID="4" Name="Dir" Location="file://localhost/"/>'
        '<TRACK TrackID="5" Name="B" Location="file://localhost/m/b.mp3"/>'
    )
    body = '<NODE Type="1" Name="P" KeyType="0"><TRACK Key="1"/><TRACK Key="2"/><TRACK Key="3"/><TRACK Key="4"/><TRACK Key="5"/></NODE>'
    pl = rx.get_playlist_tree(_lib_from(tmp_path, body, coll))[0]["playlist"]
    assert [(t.title, t.TrackNo) for t in pl.tracks] == [("A", 1), ("B", 2)]


def test_repeated_sibling_names_get_distinct_ids(tmp_path) -> None:
    body = (
        '<NODE Type="0" Name="Sets">'
        '<NODE Type="1" Name="Viernes" KeyType="0"/>'
        '<NODE Type="1" Name="Viernes" KeyType="0"/>'
        '<NODE Type="1" Name="Viernes" KeyType="0"/></NODE>'
        '<NODE Type="0" Name="Sets"><NODE Type="1" Name="Viernes" KeyType="0"/></NODE>'
    )
    tree = rx.get_playlist_tree(_lib_from(tmp_path, body, ""))
    ids = [c["playlist"].ID for c in tree[0]["children"]]
    assert ids == ["Sets/Viernes", "Sets/Viernes#2", "Sets/Viernes#3"]
    assert tree[0]["playlist"].ID == "Sets" and tree[1]["playlist"].ID == "Sets#2"
    assert tree[1]["children"][0]["playlist"].ID == "Sets#2/Viernes"


def test_fixes_replace_the_path_and_mark_the_track(tmp_path: Path) -> None:
    p = tmp_path / "rekordbox.xml"
    p.write_text(XML, encoding="utf-8")
    lib = rx.open_library(p, fixes={"file://localhost/Users/gab/Music/uno.mp3": "/Nuevo/uno.mp3"})
    uno = rx.get_songs(rx.get_playlist_tree(lib)[1]["playlist"])[0]
    assert uno.FolderPath == str(Path("/Nuevo/uno.mp3"))
    assert uno.relocated and uno.location == "file://localhost/Users/gab/Music/uno.mp3"
    tres = rx.get_songs(rx.get_playlist_tree(lib)[0]["children"][0]["playlist"])[0]
    assert not tres.relocated and tres.element is not None and tres.element.get("TrackID") == "3"


def test_path_to_location_round_trips() -> None:
    for raw in ("/Users/gab/Music/Björk - dos #1.flac", "/a b/c?d.mp3"):
        loc = rx.path_to_location(Path(raw))
        assert loc.startswith("file://localhost/") and " " not in loc
        assert rx.location_to_path(loc) == Path(raw)


def test_path_to_location_windows_drive() -> None:
    from pathlib import PureWindowsPath
    loc = rx.path_to_location(PureWindowsPath("C:/Users/gab/a b.mp3"))
    assert loc == "file://localhost/C:/Users/gab/a%20b.mp3"


# ───────────────────── revisión final de la rama (T-081) ─────────────────────

def _one_track_xml(tmp_path: Path, loc: str, extra: str = "") -> Path:
    p = tmp_path / "rekordbox.xml"
    p.write_text(
        '<?xml version="1.0" encoding="UTF-8"?><DJ_PLAYLISTS Version="1.0.0"><COLLECTION Entries="1">'
        f'<TRACK TrackID="1" Name="Uno" Artist="Ana" Location="{loc}" {extra}/></COLLECTION>'
        '<PLAYLISTS><NODE Type="0" Name="ROOT" Count="1"><NODE Type="1" Name="P" KeyType="0" Entries="1">'
        '<TRACK Key="1"/></NODE></NODE></PLAYLISTS></DJ_PLAYLISTS>', encoding="utf-8")
    return p


def test_fix_is_ignored_when_the_original_file_exists_again(tmp_path: Path) -> None:
    orig = tmp_path / "uno.mp3"
    orig.write_bytes(b"x")
    loc = rx.path_to_location(orig)
    p = _one_track_xml(tmp_path, loc)
    lib = rx.open_library(p, fixes={loc: "/Nuevo/uno.mp3"})
    t = rx.get_songs(rx.get_playlist_tree(lib)[0]["playlist"])[0]
    assert t.file_path == orig and t.relocated is False
    orig.unlink()
    lib = rx.open_library(p, fixes={loc: "/Nuevo/uno.mp3"})
    t = rx.get_songs(rx.get_playlist_tree(lib)[0]["playlist"])[0]
    assert t.file_path == Path("/Nuevo/uno.mp3") and t.relocated is True


def test_load_without_fixes_never_touches_the_disk_from_track(tmp_path: Path, monkeypatch) -> None:
    import pathlib

    orig = tmp_path / "uno.mp3"
    orig.write_bytes(b"x")
    p = _one_track_xml(tmp_path, rx.path_to_location(orig))
    calls: list[str] = []
    real_exists = pathlib.Path.exists

    def counting_exists(self, *a, **kw):
        calls.append(str(self))
        return real_exists(self, *a, **kw)

    monkeypatch.setattr(pathlib.Path, "exists", counting_exists)
    lib = rx.open_library(p, fixes={})
    assert calls == []
    t = rx.get_songs(rx.get_playlist_tree(lib)[0]["playlist"])[0]
    assert t.file_path == orig and t.relocated is False


def _export_one(tmp_path: Path, new_name: str, attrs: str):
    new = tmp_path / new_name
    new.write_bytes(b"x" * 1234)
    loc = "file://localhost/no/existe/uno.mp3"
    p = _one_track_xml(tmp_path, loc, attrs)
    lib = rx.open_library(p, fixes={loc: str(new)})
    pl = rx.get_playlist_tree(lib)[0]["playlist"]
    dest = tmp_path / "out.xml"
    rx.write_playlists_xml([pl], dest, source=p)
    from xml.etree import ElementTree as ET
    return ET.parse(dest).getroot().find("./COLLECTION/TRACK")


def test_export_sets_the_real_size_of_a_repaired_file(tmp_path: Path) -> None:
    el = _export_one(tmp_path, "uno.mp3", 'Size="99" Kind="MP3 File" BitRate="320" SampleRate="44100"')
    assert el.get("Size") == "1234"
    assert (el.get("Kind"), el.get("BitRate"), el.get("SampleRate")) == ("MP3 File", "320", "44100")


def test_export_drops_format_attributes_when_the_repaired_file_changes_format(tmp_path: Path) -> None:
    el = _export_one(tmp_path, "uno.flac", 'Size="99" Kind="MP3 File" BitRate="320" SampleRate="44100"')
    assert el.get("Size") == "1234"
    assert el.get("Kind") is None and el.get("BitRate") is None and el.get("SampleRate") is None


STREAM_XML = """<?xml version="1.0" encoding="UTF-8"?>
<DJ_PLAYLISTS Version="1.0.0"><COLLECTION Entries="3">
  <TRACK TrackID="1" Name="Archivo" Location="file://localhost/Users/gab/Music/a.mp3"/>
  <TRACK TrackID="2" Name="De Tidal" Location="tidal:tracks:123456"/>
  <TRACK TrackID="3" Name="De Beatport" Location="https://www.beatport.com/track/x/987"/>
</COLLECTION><PLAYLISTS><NODE Type="0" Name="ROOT" Count="1">
  <NODE Type="1" Name="Mix" KeyType="0" Entries="3"><TRACK Key="1"/><TRACK Key="2"/><TRACK Key="3"/></NODE>
</NODE></PLAYLISTS></DJ_PLAYLISTS>"""


def test_non_file_locations_are_streaming_tracks_kept_in_order(tmp_path: Path) -> None:
    p = tmp_path / "rekordbox.xml"
    p.write_text(STREAM_XML, encoding="utf-8")
    songs = rx.get_songs(rx.get_playlist_tree(rx.open_library(p))[0]["playlist"])
    assert [(s.Title, s.streaming) for s in songs] == [
        ("Archivo", False), ("De Tidal", True), ("De Beatport", True)]
    assert [s.TrackNo for s in songs] == [1, 2, 3]


def test_streaming_tracks_never_take_a_stored_fix(tmp_path: Path) -> None:
    p = tmp_path / "rekordbox.xml"
    p.write_text(STREAM_XML, encoding="utf-8")
    lib = rx.open_library(p, fixes={"tidal:tracks:123456": "/x/a.mp3"})
    tidal = rx.get_songs(rx.get_playlist_tree(lib)[0]["playlist"])[1]
    assert tidal.streaming and not tidal.relocated
