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
