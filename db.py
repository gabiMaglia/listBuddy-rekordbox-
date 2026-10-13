"""
db.py
-----
Capa de acceso a la base de datos de Rekordbox.
Import chain: main → ui → worker / db → rekordbox_export (nunca al revés).
"""
from __future__ import annotations

from collections.abc import Iterable
from typing import Any

from rekordbox_export import get_all_playlists, get_songs


def order_playlist_songs(songs: Iterable[Any]) -> list[Any]:
    """
    Ordena las canciones de una playlist por TrackNo de la entrada
    playlist-canción (DjmdSongPlaylist).

    pyrekordbox devuelve playlist.Songs sin orden garantizado; TrackNo es la
    única fuente del orden real. None cuenta como 0 y los empates conservan el
    orden de llegada, que es el criterio que el export usó siempre. Export y
    vista previa comparten esta función para numerar igual.
    """
    indexed = list(enumerate(songs))
    indexed.sort(key=lambda i_s: (getattr(i_s[1], "TrackNo", None) or 0, i_s[0]))
    return [s for _, s in indexed]


def key_bpm_of(content: Any) -> tuple[str, float | None]:
    """
    (key, bpm) de una pista de Rekordbox o Traktor; ("", None) si falta el dato.

    Rekordbox: DjmdContent.BPM es BPM×100 (12800 -> 128) y Key.ScaleName ya viene
    en Camelot. Traktor (TraktorTrack): bpm float y key de INFO@KEY. Todo con
    getattr defensivo: Key es una relación lazy que puede fallar fuera de sesión.
    """
    key = ""
    try:
        scale = getattr(getattr(content, "Key", None), "ScaleName", None)
        key = str(scale).strip() if scale else ""
    except Exception:
        key = ""
    if not key:
        raw_key = getattr(content, "key", None)
        key = str(raw_key).strip() if isinstance(raw_key, str) else ""

    bpm: float | None = None
    raw_bpm = getattr(content, "BPM", None)
    if isinstance(raw_bpm, (int, float)) and raw_bpm > 0:
        bpm = raw_bpm / 100
    else:
        trk = getattr(content, "bpm", None)
        if isinstance(trk, (int, float)) and trk > 0:
            bpm = float(trk)
    return key, bpm


def open_database(path: str | None = None):
    """
    Abre la base de datos de Rekordbox 6.
    Si `path` apunta a un master.db válido, lo usa; si no, autodetecta.
    Lanza RuntimeError con mensaje claro y accionable si falla.
    """
    try:
        from pyrekordbox import Rekordbox6Database
        from pyrekordbox.utils import get_rekordbox_pid
    except ImportError as e:
        raise RuntimeError(
            "No se pudo cargar pyrekordbox.\n\n"
            f"Detalle: {e}"
        ) from e

    # Detectar Rekordbox abierto antes de intentar conectar
    try:
        pid = get_rekordbox_pid()
    except Exception:
        pid = None
    if pid:
        raise RuntimeError(
            "Rekordbox está abierto (PID {}).\n\n"
            "Cerrá Rekordbox completamente e intentá de nuevo.\n"
            "La base de datos queda bloqueada mientras el programa está corriendo.".format(pid)
        )

    try:
        if path:
            return Rekordbox6Database(path)
        return Rekordbox6Database()

    except FileNotFoundError as e:
        msg = str(e)
        if "directory" in msg.lower() or "pioneer" in msg.lower():
            raise RuntimeError(
                "No se encontró la instalación de Rekordbox 6.\n\n"
                "Verificá que Rekordbox 6 esté instalado en esta Mac.\n"
                "Si usás una ubicación no estándar, configurá la ruta al master.db "
                "en ⚙ Configuración → Librerías."
            ) from e
        raise RuntimeError(
            "No se encontró el archivo de base de datos.\n\n"
            "Ruta buscada: {}\n\n"
            "Configurá la ruta correcta en ⚙ Configuración → Librerías.".format(msg)
        ) from e

    except Exception as e:
        msg_lower = str(e).lower()
        if "locked" in msg_lower or "busy" in msg_lower or "unable to open" in msg_lower:
            raise RuntimeError(
                "La base de datos está bloqueada.\n\n"
                "Cerrá Rekordbox completamente e intentá de nuevo."
            ) from e
        if "file is not a database" in msg_lower or "malformed" in msg_lower or "notadb" in msg_lower:
            raise RuntimeError(
                "No se pudo desencriptar la base de datos.\n\n"
                "Puede que tu versión de Rekordbox use una clave diferente.\n"
                "Actualizá pyrekordbox a la última versión e intentá de nuevo."
            ) from e
        raise RuntimeError(
            "No se pudo abrir la base de datos de Rekordbox.\n\n"
            "Asegurate de tener Rekordbox cerrado e instalado.\n"
            "Si tu librería está en una ubicación no estándar, configurá la ruta "
            "al master.db en ⚙ Configuración → Librerías.\n\n"
            "Detalle técnico: {}".format(e)
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
