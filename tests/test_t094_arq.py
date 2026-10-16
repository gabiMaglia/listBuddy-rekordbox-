"""T-094 intento 3: correcciones C1-C3 de la revisión de arquitectura."""
from __future__ import annotations

from pathlib import Path
from xml.etree import ElementTree as ET

import pytest

import rekordbox_xml as rx


def _doc(tracks: list[str]) -> str:
    keys = "".join(f'<TRACK Key="{i + 1}"/>' for i in range(len(tracks)))
    return (
        '<?xml version="1.0" encoding="UTF-8"?><DJ_PLAYLISTS Version="1.0.0">'
        f'<COLLECTION Entries="{len(tracks)}">{"".join(tracks)}</COLLECTION><PLAYLISTS>'
        '<NODE Type="0" Name="ROOT" Count="1"><NODE Name="P" Type="1" KeyType="0" '
        f'Entries="{len(tracks)}">{keys}</NODE></NODE></PLAYLISTS></DJ_PLAYLISTS>'
    )


def _track(i: int, comments: str = "", children: bool = True) -> str:
    attrs = f' Comments="{comments}"' if comments else ""
    head = f'<TRACK TrackID="{i}" Name="T{i}" Artist="A" Location="file://localhost/x/{i}.mp3"{attrs}'
    return head + ('><TEMPO Inizio="0" Bpm="128"/></TRACK>' if children else "/>")


def _raws(path: Path) -> list[bytes]:
    lib = rx.open_library(path)
    pl = lib.tree[0]["playlist"]
    return [t._src.raw for t in pl.tracks]


def _padding_track(i: int, size: int) -> str:
    """Pista de relleno de exactamente `size` bytes (ASCII) para ubicar el siguiente TRACK."""
    base = len(_track(i, "")) + len(' Comments=""')
    return _track(i, "y" * (size - base))


# ───────────── C1: etiqueta de apertura > _MARGIN que cruza el límite de bloque ─────────────

@pytest.mark.parametrize("children", [True, False])
@pytest.mark.parametrize("back", [70_000, 90_000, 150_000])
def test_huge_open_tag_crossing_the_real_chunk_boundary_keeps_raw_intact(
    tmp_path: Path, children: bool, back: int,
) -> None:
    head_len = len('<?xml version="1.0" encoding="UTF-8"?><DJ_PLAYLISTS Version="1.0.0"><COLLECTION Entries="2">')
    pad = _padding_track(1, rx._CHUNK - back - head_len)
    big = _track(2, "x" * 200_000, children)
    p = tmp_path / "big.xml"
    p.write_text(_doc([pad, big]), encoding="utf-8")
    assert _raws(p)[1] == big.encode()


@pytest.mark.parametrize("children", [True, False])
def test_huge_open_tag_with_small_chunk_and_margin_keeps_raw_intact(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, children: bool,
) -> None:
    monkeypatch.setattr(rx, "_CHUNK", 4096)
    monkeypatch.setattr(rx, "_MARGIN", 512)
    tracks = [_track(1), _track(2, "x" * 9000, children), _track(3, "z" * 5000, children)]
    p = tmp_path / "small.xml"
    p.write_text(_doc(tracks), encoding="utf-8")
    assert _raws(p) == [t.encode() for t in tracks]


def test_huge_open_tag_export_roundtrip_matches_small_tag_export(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    tracks = [_track(1), _track(2, "x" * 9000), _track(3)]
    p = tmp_path / "in.xml"
    p.write_text(_doc(tracks), encoding="utf-8")
    ref = tmp_path / "ref.xml"
    pls = [n["playlist"] for n in rx.open_library(p).tree]
    rx.write_playlists_xml(pls, ref, source=p, app_version="1.0.0")
    monkeypatch.setattr(rx, "_CHUNK", 4096)
    monkeypatch.setattr(rx, "_MARGIN", 512)
    out = tmp_path / "out.xml"
    pls = [n["playlist"] for n in rx.open_library(p).tree]
    rx.write_playlists_xml(pls, out, source=p, app_version="1.0.0")
    assert out.read_bytes() == ref.read_bytes()


def test_invalid_cut_fails_loudly_as_the_friendly_error(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Si alguna vez la ventana ya no contiene el inicio del TRACK, nunca se corta con índice negativo.
    monkeypatch.setattr(rx, "_window_keep", lambda base, fed, cap_start, window: fed)
    monkeypatch.setattr(rx, "_CHUNK", 64)
    p = tmp_path / "x.xml"
    p.write_text(_doc([_track(1), _track(2)]), encoding="utf-8")
    with pytest.raises(RuntimeError, match="no se pudo leer"):
        rx.open_library(p)
