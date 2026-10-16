"""T-094 intento 3, C3: la declaración encoding= solo admite codificaciones de texto."""
from __future__ import annotations

import zlib
from pathlib import Path

import pytest

import rekordbox_xml as rx
from test_t094_arq import _doc, _raws, _track


def _with_decl(tmp_path: Path, enc: str, payload: bytes) -> Path:
    p = tmp_path / "enc.xml"
    p.write_bytes(f'<?xml version="1.0" encoding="{enc}"?>'.encode() + payload)
    return p


@pytest.mark.parametrize("enc,payload", [
    pytest.param("zlib_codec", zlib.compress(b"<DJ_PLAYLISTS>" + b"A" * 1_000_000), id="zlib_codec"),
    pytest.param("zlib", zlib.compress(b"<DJ_PLAYLISTS/>"), id="zlib"),
    ("rot_13", b"<DJ_PLAYLISTS/>"),
    ("base64", b"PERKX1BMQVlMSVNUUy8+"),
    ("hex_codec", b"3c444a5f504c41594c495354532f3e"),
    ("bz2", b"<DJ_PLAYLISTS/>"),
    ("idna", b"<DJ_PLAYLISTS/>"),
    ("unicode_escape", b"<DJ_PLAYLISTS/>"),
    ("no_existe_xyz", b"<DJ_PLAYLISTS/>"),
])
def test_non_text_or_unknown_declared_encoding_gives_the_friendly_error(
    tmp_path: Path, enc: str, payload: bytes,
) -> None:
    with pytest.raises(RuntimeError, match="no se pudo leer"):
        rx.open_library(_with_decl(tmp_path, enc, payload))


@pytest.mark.parametrize("enc", ["ISO-8859-1", "windows-1252", "Shift_JIS", "latin1", "US-ASCII", "koi8-r", "GBK"])
def test_legitimate_declared_encodings_still_load(tmp_path: Path, enc: str) -> None:
    body = _doc([_track(1)]).split("?>", 1)[1]
    p = _with_decl(tmp_path, enc, body.encode("ascii"))
    assert len(_raws(p)) == 1


def test_any_decoder_exception_becomes_the_friendly_error(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    import codecs

    class Boom:
        def decode(self, data: bytes, final: bool = False) -> str:
            raise TypeError("boom")

    monkeypatch.setattr(codecs, "getincrementaldecoder", lambda enc: Boom)
    p = _with_decl(tmp_path, "ISO-8859-1", _doc([_track(1)]).split("?>", 1)[1].encode())
    with pytest.raises(RuntimeError, match="no se pudo leer"):
        rx.open_library(p)
