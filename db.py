"""
db.py
-----
Capa de acceso a la base de datos de Rekordbox.
Import chain: main → ui → worker / db → rekordbox_export (nunca al revés).
"""
from __future__ import annotations

from rekordbox_export import get_all_playlists, get_songs


def open_database():
    """
    Abre la base de datos de Rekordbox 6.
    Lanza RuntimeError con mensaje claro si falla.
    """
    try:
        from pyrekordbox import Rekordbox6Database
        return Rekordbox6Database()
    except Exception as e:
        raise RuntimeError(
            "No se pudo abrir la base de datos de Rekordbox.\n"
            "Asegurate de tener Rekordbox cerrado e instalado.\n\n"
            f"Detalle: {e}"
        ) from e


def list_playlists(db) -> list:
    """Retorna todas las playlists (no carpetas) como lista plana."""
    return get_all_playlists(db)


def playlist_song_count(playlist) -> int:
    """Número de canciones en una playlist. Retorna 0 si falla."""
    try:
        return len(get_songs(playlist))
    except Exception:
        return 0


def get_playlist_tree(db) -> list[dict]:
    """
    Retorna la jerarquía completa de playlists y carpetas como árbol.

    Cada nodo: {'playlist': DjmdPlaylist, 'children': [nodo, ...]}
    Ordenado por Seq (orden de visualización de Rekordbox).
    Los items con ParentID == 'root' son nodos raíz.
    """
    all_items = sorted(db.get_playlist(), key=lambda p: p.Seq or 0)

    by_id: dict[str, dict] = {
        pl.ID: {"playlist": pl, "children": []} for pl in all_items
    }

    roots: list[dict] = []
    for pl in all_items:
        node = by_id[pl.ID]
        if pl.ParentID == "root":
            roots.append(node)
        else:
            parent = by_id.get(str(pl.ParentID))
            if parent:
                parent["children"].append(node)
            else:
                roots.append(node)  # huérfano → tratar como raíz

    return roots
