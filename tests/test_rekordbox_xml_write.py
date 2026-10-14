"""T-081: XML nuevo con las playlists marcadas, importable en Rekordbox."""
from __future__ import annotations

import os
from pathlib import Path
from xml.etree import ElementTree as ET

import pytest

import rekordbox_xml as rx


def _lib(tmp: Path) -> tuple[rx.RekordboxXmlLibrary, Path]:
    ok = tmp / "ok.mp3"; ok.write_bytes(b"x")
    xml = tmp / "rekordbox.xml"
    xml.write_text(
        '<?xml version="1.0" encoding="UTF-8"?><DJ_PLAYLISTS Version="1.0.0">'
        '<PRODUCT Name="rekordbox" Version="7.1.0" Company="AlphaTheta"/><COLLECTION Entries="3">'
        f'<TRACK TrackID="10" Name="Ok" Artist="A" AverageBpm="128.00" Location="{rx.path_to_location(ok)}">'
        '<TEMPO Inizio="0.1" Bpm="128.00" Metro="4/4" Battito="1"/>'
        '<POSITION_MARK Name="" Type="0" Start="12.5" Num="0"/></TRACK>'
        '<TRACK TrackID="20" Name="Perdido" Artist="B" Location="file://localhost/viejo/perdido.mp3"/>'
        '<TRACK TrackID="30" Name="Otra" Artist="C" Location="file://localhost/viejo/otra.mp3"/>'
        '</COLLECTION><PLAYLISTS><NODE Type="0" Name="ROOT" Count="2">'
        '<NODE Type="1" Name="Viernes" KeyType="0" Entries="2"><TRACK Key="20"/><TRACK Key="10"/></NODE>'
        '<NODE Type="1" Name="Sábado" KeyType="0" Entries="1"><TRACK Key="30"/></NODE>'
        '</NODE></PLAYLISTS></DJ_PLAYLISTS>', encoding="utf-8")
    nuevo = tmp / "nuevo"; nuevo.mkdir(); (nuevo / "perdido.mp3").write_bytes(b"y")
    lib = rx.open_library(xml, fixes={"file://localhost/viejo/perdido.mp3": str(nuevo / "perdido.mp3")})
    return lib, xml


def test_writes_only_the_chosen_playlist_with_repaired_paths(tmp_path: Path) -> None:
    lib, xml = _lib(tmp_path)
    viernes = rx.get_playlist_tree(lib)[0]["playlist"]
    dest = tmp_path / "out" / "ListBuddy.xml"
    res = rx.write_playlists_xml([viernes], dest, source=xml, app_version="1.0.0")
    assert (res.playlists, res.tracks, res.relocated, res.missing) == (1, 2, 1, 0)

    root = ET.parse(dest).getroot()
    assert root.tag == "DJ_PLAYLISTS" and root.get("Version") == "1.0.0"
    assert root.find("PRODUCT").get("Name") == "List Buddy"
    tracks = root.findall("./COLLECTION/TRACK")
    assert root.find("COLLECTION").get("Entries") == "2"
    assert [t.get("Name") for t in tracks] == ["Perdido", "Ok"]
    assert rx.location_to_path(tracks[0].get("Location")) == tmp_path / "nuevo" / "perdido.mp3"
    assert tracks[1].find("POSITION_MARK").get("Start") == "12.5"     # cues viajan
    assert tracks[1].find("TEMPO") is not None                         # beatgrid viaja
    nodes = root.findall("./PLAYLISTS/NODE/NODE")
    assert [n.get("Name") for n in nodes] == ["Viernes (List Buddy)"]
    assert nodes[0].get("Type") == "1" and nodes[0].get("KeyType") == "0" and nodes[0].get("Entries") == "2"
    assert [t.get("Key") for t in nodes[0].findall("TRACK")] == [t.get("TrackID") for t in tracks]
    assert root.find("./PLAYLISTS/NODE").get("Name") == "ROOT"
    assert root.find("./PLAYLISTS/NODE").get("Count") == "1"


def test_shared_tracks_appear_once_in_the_collection(tmp_path: Path) -> None:
    lib, xml = _lib(tmp_path)
    tree = rx.get_playlist_tree(lib)
    res = rx.write_playlists_xml([tree[0]["playlist"], tree[1]["playlist"]], tmp_path / "o.xml", source=xml)
    assert (res.playlists, res.tracks, res.missing) == (2, 3, 1)
    root = ET.parse(tmp_path / "o.xml").getroot()
    assert root.find("COLLECTION").get("Entries") == "3"


def test_refuses_to_overwrite_the_loaded_xml(tmp_path: Path) -> None:
    lib, xml = _lib(tmp_path)
    before = xml.read_bytes()
    with pytest.raises(ValueError):
        rx.write_playlists_xml([rx.get_playlist_tree(lib)[0]["playlist"]], xml, source=xml)
    assert xml.read_bytes() == before


def test_output_reloads_with_list_buddy_itself(tmp_path: Path) -> None:
    lib, xml = _lib(tmp_path)
    dest = tmp_path / "o.xml"
    rx.write_playlists_xml([rx.get_playlist_tree(lib)[0]["playlist"]], dest, source=xml)
    again = rx.open_library(dest)
    songs = rx.get_songs(rx.get_playlist_tree(again)[0]["playlist"])
    assert [s.Title for s in songs] == ["Perdido", "Ok"] and all(s.file_path.exists() for s in songs)


def _case_insensitive(tmp: Path) -> bool:
    probe = tmp / "CaseProbe.tmp"
    probe.write_bytes(b"x")
    try:
        return probe.with_name("caseprobe.tmp").exists()
    finally:
        probe.unlink()


def test_refuses_case_swapped_name_of_the_source(tmp_path: Path) -> None:
    lib, xml = _lib(tmp_path)
    if not _case_insensitive(tmp_path):
        pytest.skip("el filesystem distingue mayúsculas")
    before = xml.read_bytes()
    with pytest.raises(ValueError):
        rx.write_playlists_xml([rx.get_playlist_tree(lib)[0]["playlist"]],
                               xml.with_name(xml.name.upper()), source=xml)
    assert xml.read_bytes() == before


@pytest.mark.skipif(not hasattr(os, "symlink"), reason="sin os.symlink")
def test_refuses_symlink_to_the_source(tmp_path: Path) -> None:
    lib, xml = _lib(tmp_path)
    link = tmp_path / "link.xml"
    try:
        os.symlink(xml, link)
    except OSError:
        pytest.skip("no se pudo crear el symlink")
    before = xml.read_bytes()
    with pytest.raises(ValueError):
        rx.write_playlists_xml([rx.get_playlist_tree(lib)[0]["playlist"]], link, source=xml)
    assert xml.read_bytes() == before


def test_failed_write_leaves_no_tmp_file(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    lib, xml = _lib(tmp_path)
    out = tmp_path / "out"
    out.mkdir()
    dest = out / "o.xml"
    def boom(src: str, dst: str) -> None:
        assert Path(src).exists()          # el .tmp ya está escrito cuando falla
        raise OSError("disco lleno")
    monkeypatch.setattr(rx.os, "replace", boom)
    with pytest.raises(OSError, match="disco lleno"):
        rx.write_playlists_xml([rx.get_playlist_tree(lib)[0]["playlist"]], dest, source=xml)
    assert not list(out.glob("*.tmp"))
    assert not dest.exists()


def test_refuses_source_named_like_the_temp_file(tmp_path: Path) -> None:
    lib, xml = _lib(tmp_path)
    src = tmp_path / "x.xml.tmp"
    src.write_bytes(xml.read_bytes())
    before = src.read_bytes()
    with pytest.raises(ValueError):
        rx.write_playlists_xml([rx.get_playlist_tree(lib)[0]["playlist"]],
                               tmp_path / "x.xml", source=src)
    assert src.read_bytes() == before
