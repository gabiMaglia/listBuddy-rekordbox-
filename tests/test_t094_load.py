"""T-094: carga del XML en streaming (sin DOM vivo) y round-trip idéntico del export."""
from __future__ import annotations

import gc
from pathlib import Path
from xml.etree import ElementTree as ET

import pytest

import rekordbox_xml as rx

DATA = Path(__file__).parent / "data"
FIXES = {"file://localhost/viejo/perdido.wav": "/nuevo/dir/perdido.flac"}


def _playlists(lib: rx.RekordboxXmlLibrary) -> list[rx.RbxPlaylist]:
    out: list[rx.RbxPlaylist] = []

    def walk(nodes: list[dict]) -> None:
        for n in nodes:
            if n["playlist"].is_folder:
                walk(n["children"])
            else:
                out.append(n["playlist"])

    walk(rx.get_playlist_tree(lib))
    return out


# ───────────── Ítem 1: el export no cambia ni un byte (cues, beatgrid, atributos) ─────────────

@pytest.mark.parametrize("expected,count", [("t094_roundtrip_all.xml", None), ("t094_roundtrip_one.xml", 1)])
def test_exported_xml_is_byte_identical_to_the_pre_t094_output(
    tmp_path: Path, expected: str, count: int | None,
) -> None:
    src = DATA / "t094_roundtrip_in.xml"
    pls = _playlists(rx.open_library(src, fixes=FIXES))
    dest = tmp_path / "out.xml"
    rx.write_playlists_xml(pls[:count], dest, source=src, app_version="1.0.0")
    assert dest.read_bytes() == (DATA / expected).read_bytes()


# ───────────── Ítem 2 (SEC-09): sin DOM retenido ─────────────

def _big_xml(path: Path, tracks: int = 1500) -> None:
    rows = "".join(
        f'<TRACK TrackID="{i}" Name="T{i}" Artist="A" Location="file://localhost/x/{i}.mp3">'
        '<TEMPO Inizio="0.1" Bpm="120.00" Metro="4/4" Battito="1"/>'
        + "".join(f'<POSITION_MARK Name="" Type="0" Start="{m}" Num="{m}"/>' for m in range(6))
        + "</TRACK>"
        for i in range(tracks)
    )
    keys = "".join(f'<TRACK Key="{i}"/>' for i in range(tracks))
    path.write_text(
        '<?xml version="1.0" encoding="UTF-8"?><DJ_PLAYLISTS Version="1.0.0">'
        f'<COLLECTION Entries="{tracks}">{rows}</COLLECTION><PLAYLISTS><NODE Type="0" Name="ROOT" Count="1">'
        f'<NODE Type="1" Name="P" KeyType="0" Entries="{tracks}">{keys}</NODE></NODE></PLAYLISTS></DJ_PLAYLISTS>',
        encoding="utf-8")


def _live_elements() -> int:
    gc.collect()
    return sum(1 for o in gc.get_objects() if isinstance(o, ET.Element))


def test_open_library_keeps_no_dom_alive(tmp_path: Path) -> None:
    xml = tmp_path / "rekordbox.xml"
    _big_xml(xml)
    before = _live_elements()
    lib = rx.open_library(xml)
    after = _live_elements()
    assert len(_playlists(lib)[0].tracks) == 1500
    # Antes del cambio quedaban ~10.500 Element (pista + 7 hijos) colgados de RbxTrack.element.
    assert after - before < 100


def test_open_library_does_not_parse_the_whole_tree(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    xml = tmp_path / "rekordbox.xml"
    _big_xml(xml, 10)

    def boom(*a: object, **k: object) -> None:
        raise AssertionError("ET.parse arma el DOM completo")

    monkeypatch.setattr(rx.ET, "parse", boom)
    assert len(_playlists(rx.open_library(xml))[0].tracks) == 10


def test_track_element_is_rebuilt_on_demand_with_children(tmp_path: Path) -> None:
    xml = tmp_path / "rekordbox.xml"
    _big_xml(xml, 3)
    track = _playlists(rx.open_library(xml))[0].tracks[1]
    el = track.element
    assert el is not None and el.get("TrackID") == "1"
    assert [c.tag for c in el] == ["TEMPO"] + ["POSITION_MARK"] * 6


def test_open_library_can_be_cancelled(tmp_path: Path) -> None:
    xml = tmp_path / "rekordbox.xml"
    _big_xml(xml, 50)
    with pytest.raises(rx.LoadCancelled):
        rx.open_library(xml, should_cancel=lambda: True)


def test_cancellation_is_checked_while_scanning(tmp_path: Path, monkeypatch) -> None:
    """QA T-094 D2: la cancelación corta el parseo en sí, no solo el armado del árbol posterior."""
    xml = tmp_path / "rekordbox.xml"
    _big_xml(xml, 1500)                      # ~300 KB → decenas de bloques con _CHUNK chico
    monkeypatch.setattr(rx, "_CHUNK", 4096)

    def never_here(*a, **k):
        raise AssertionError("el parseo terminó entero: la cancelación no se miró en _scan")
    monkeypatch.setattr(rx, "_build_tree", never_here)

    calls = {"n": 0}

    def cancel_on_third_block() -> bool:
        calls["n"] += 1
        return calls["n"] >= 3

    with pytest.raises(rx.LoadCancelled):
        rx.open_library(xml, should_cancel=cancel_on_third_block)
    assert calls["n"] == 3


@pytest.mark.parametrize("body,fragment", [
    ("<NOPE/>", "no es un XML de Rekordbox"),
])
def test_wrong_root_still_gives_the_friendly_error(tmp_path: Path, body: str, fragment: str) -> None:
    xml = tmp_path / "x.xml"
    xml.write_text(body, encoding="utf-8")
    with pytest.raises(RuntimeError, match=fragment):
        rx.open_library(xml)


def test_truncated_xml_still_gives_the_friendly_error(tmp_path: Path) -> None:
    xml = tmp_path / "x.xml"
    xml.write_text('<DJ_PLAYLISTS><COLLECTION><TRACK TrackID="1"', encoding="utf-8")
    with pytest.raises(RuntimeError, match="no se pudo leer"):
        rx.open_library(xml)


# ───────────── Ítem 3 (SEC-09): Traktor ─────────────

NML = (
    '<?xml version="1.0" encoding="UTF-8"?><NML VERSION="19"><COLLECTION ENTRIES="{n}">{entries}</COLLECTION>'
    '<PLAYLISTS><NODE TYPE="FOLDER" NAME="$ROOT"><SUBNODES COUNT="1">'
    '<NODE TYPE="PLAYLIST" NAME="Set"><PLAYLIST ENTRIES="{n}" TYPE="LIST" UUID="u">{refs}</PLAYLIST></NODE>'
    '</SUBNODES></NODE></PLAYLISTS></NML>'
)


def _nml(path: Path, n: int) -> None:
    entries = "".join(
        f'<ENTRY TITLE="T{i}" ARTIST="A"><LOCATION DIR="/:x/:" FILE="{i}.mp3" VOLUME="Mac"/>'
        '<TEMPO BPM="125.5"/><INFO KEY="4A"/></ENTRY>'
        for i in range(n)
    )
    refs = "".join(f'<ENTRY><PRIMARYKEY TYPE="TRACK" KEY="Mac/:x/:{i}.mp3"/></ENTRY>' for i in range(n))
    path.write_text(NML.format(n=n, entries=entries, refs=refs), encoding="utf-8")


def test_traktor_collection_streams_and_keeps_the_same_tracks(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    import traktor_db as tk

    nml = tmp_path / "collection.nml"
    _nml(nml, 1200)

    def boom(*a: object, **k: object) -> None:
        raise AssertionError("ET.parse arma el DOM completo")

    monkeypatch.setattr(tk.ET, "parse", boom)
    before = _live_elements()
    col = tk.open_collection(nml)
    pl = tk.get_playlist_tree(col)[0]["playlist"]
    assert len(pl.tracks) == 1200
    t = pl.tracks[7]
    assert (t.title, t.artist, t.bpm, t.key) == ("T7", "A", 125.5, "4A")
    # Quedan los NODE/ENTRY de PLAYLISTS (≈2.400 elementos) pero ninguno de COLLECTION (≈7.200).
    assert _live_elements() - before < 3000


def test_traktor_open_can_be_cancelled(tmp_path: Path) -> None:
    import traktor_db as tk

    nml = tmp_path / "collection.nml"
    _nml(nml, 50)
    with pytest.raises(tk.LoadCancelled):
        tk.open_collection(nml, should_cancel=lambda: True)


def test_traktor_cancellation_is_checked_while_scanning(tmp_path: Path) -> None:
    """QA T-094 D3: la cancelación se consulta a lo largo del parseo (cada CHECK_EVERY eventos),
    no solo en el primer evento: un NML grande tiene que poder cortarse a mitad de camino."""
    import traktor_db as tk
    from load_cancel import CHECK_EVERY

    nml = tmp_path / "collection.nml"
    _nml(nml, 3000)                       # > 2×CHECK_EVERY eventos: hay más de una consulta
    calls = {"n": 0}

    def cancel_on_second_check() -> bool:
        calls["n"] += 1
        return calls["n"] >= 2

    with pytest.raises(tk.LoadCancelled):
        tk.open_collection(nml, should_cancel=cancel_on_second_check)
    assert calls["n"] == 2, f"se consultó {calls['n']} veces (CHECK_EVERY={CHECK_EVERY})"


def test_track_source_roundtrips_escapes_nesting_and_tails(tmp_path: Path) -> None:
    raw = (
        '<TRACK TrackID="1" Name="a &amp; &lt;b&gt; &quot;c&quot;&#10;d" Location="file://localhost/x/a.mp3">tx'
        '<POSITION_MARK Name="Ñ &amp; &quot;q&quot; &#9;t&#10;n" Start="1"/>cola &amp; &lt;1&gt;'
        '<NESTED a="1"><INNER b="2">hola &lt;x&gt;</INNER>fin</NESTED><VACIO></VACIO></TRACK>'
    )
    xml = tmp_path / "rekordbox.xml"
    xml.write_text(
        '<?xml version="1.0" encoding="UTF-8"?><DJ_PLAYLISTS Version="1.0.0">'
        f'<COLLECTION Entries="1">{raw}</COLLECTION><PLAYLISTS><NODE Type="0" Name="ROOT" Count="1">'
        '<NODE Type="1" Name="P" KeyType="0" Entries="1"><TRACK Key="1"/></NODE></NODE></PLAYLISTS></DJ_PLAYLISTS>',
        encoding="utf-8")
    track = _playlists(rx.open_library(xml))[0].tracks[0]
    assert ET.tostring(track.element) == ET.tostring(ET.fromstring(raw))


@pytest.mark.parametrize("encoding,decl", [
    ("utf-8", ""), ("utf-8-sig", ""), ("latin-1", ' encoding="ISO-8859-1"'), ("utf-16", ' encoding="UTF-16"'),
])
def test_non_utf8_encodings_and_edge_tags_load_and_export_the_same(
    tmp_path: Path, encoding: str, decl: str,
) -> None:
    body = (
        f'<?xml version="1.0"{decl or " encoding=" + chr(34) + "UTF-8" + chr(34)}?><DJ_PLAYLISTS Version="1.0.0">'
        '<COLLECTION Entries="3">'
        '<TRACK TrackID="1" Name="Ñandú > raw" Artist="Á" Location="file://localhost/x/uno.mp3"/>'
        '<TRACK TrackID="2" Name="Dos" Location="file://localhost/x/dos.mp3"></TRACK>'
        '<TRACK TrackID="3" Name="Tres" Location="file://localhost/x/tres.mp3"><TEMPO Inizio="0" Bpm="1"/></TRACK>'
        '</COLLECTION><PLAYLISTS><NODE Type="0" Name="ROOT" Count="1">'
        '<NODE Type="1" Name="P" KeyType="0" Entries="3"><TRACK Key="1"/><TRACK Key="2"/><TRACK Key="3"/></NODE>'
        '</NODE></PLAYLISTS></DJ_PLAYLISTS>')
    xml = tmp_path / "rekordbox.xml"
    xml.write_bytes(body.encode(encoding))
    tracks = _playlists(rx.open_library(xml))[0].tracks
    assert [t.title for t in tracks] == ["Ñandú > raw", "Dos", "Tres"]
    assert [t.element.get("TrackID") for t in tracks] == ["1", "2", "3"]
    assert tracks[0].element.get("Artist") == "Á" and len(tracks[0].element) == 0
    assert [c.tag for c in tracks[2].element] == ["TEMPO"]


def test_tracks_spanning_read_chunks_are_cut_correctly(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    xml = tmp_path / "rekordbox.xml"
    _big_xml(xml, 40)
    monkeypatch.setattr(rx, "_CHUNK", 37)       # cortes en medio de etiquetas, atributos y cierres
    monkeypatch.setattr(rx, "_MARGIN", 400)     # y la ventana sí se recorta
    tracks = _playlists(rx.open_library(xml))[0].tracks
    assert len(tracks) == 40
    assert all(len(t.element) == 7 and t.element.get("TrackID") == str(i) for i, t in enumerate(tracks))
