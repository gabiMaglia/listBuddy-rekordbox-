"""
db.py
-----
Utilidades compartidas por export y vista previa para pistas de Rekordbox
(XML, rekordbox_xml.py) y Traktor (NML, traktor_db.py).
Import chain: main → ui → worker / db → rekordbox_export (nunca al revés).
"""
from __future__ import annotations

from collections.abc import Iterable
from typing import Any


def order_playlist_songs(songs: Iterable[Any]) -> list[Any]:
    """
    Ordena las canciones de una playlist por TrackNo (posición en la playlist).

    TrackNo es la única fuente del orden real. None cuenta como 0 y los empates conservan el
    orden de llegada, que es el criterio que el export usó siempre. Export y
    vista previa comparten esta función para numerar igual.
    """
    indexed = list(enumerate(songs))
    indexed.sort(key=lambda i_s: (getattr(i_s[1], "TrackNo", None) or 0, i_s[0]))
    return [s for _, s in indexed]


def key_bpm_of(content: Any) -> tuple[str, float | None]:
    """
    (key, bpm) de una pista de Rekordbox (RbxTrack) o Traktor (TraktorTrack);
    ("", None) si falta el dato. Ambas exponen `key` y `bpm` (float) en
    minúscula. Todo con getattr defensivo.
    """
    raw_key = getattr(content, "key", None)
    key = str(raw_key).strip() if isinstance(raw_key, str) else ""

    bpm: float | None = None
    trk = getattr(content, "bpm", None)
    if isinstance(trk, (int, float)) and trk > 0:
        bpm = float(trk)
    return key, bpm
