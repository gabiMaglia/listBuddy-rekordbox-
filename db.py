"""
db.py
-----
Capa de acceso a la base de datos de Rekordbox.
Import chain: main → ui → worker / db → rekordbox_export (nunca al revés).
"""
from __future__ import annotations

from rekordbox_export import get_all_playlists, get_songs


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
