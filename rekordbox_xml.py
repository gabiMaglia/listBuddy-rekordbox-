"""
rekordbox_xml.py
----------------
Lector de la librería de Rekordbox desde el XML que el propio Rekordbox
exporta (Archivo → Exportar colección en formato xml). Formato público de
AlphaTheta: https://rekordbox.com/en/support/developer/ (xml_format_list.pdf).

No abre ni escribe master.db (T-080 / ADR-004). Interfaz gemela de
traktor_db.py; los objetos son duck-typed con lo que consumen worker.py,
preview_worker.py, db.key_bpm_of y ui.py.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path, PureWindowsPath
from urllib.parse import unquote
from xml.etree import ElementTree as ET

_DRIVE = re.compile(r"^/[A-Za-z]:")


@dataclass
class RbxTrack:
    title: str
    artist: str
    file_path: Path
    bpm: float | None = None
    key: str = ""         # Tonality tal cual la exporta Rekordbox («8A», «Am»)
    TrackNo: int = 0      # posición 1..n dentro de la playlist

    @property
    def FolderPath(self) -> str:
        return str(self.file_path)

    @property
    def Title(self) -> str:
        return self.title

    @property
    def ArtistName(self) -> str:
        return self.artist

    @property
    def Content(self) -> "RbxTrack":
        return self

    @property
    def content(self) -> "RbxTrack":
        return self


@dataclass
class RbxPlaylist:
    name: str
    ID: str
    tracks: list[RbxTrack] = field(default_factory=list, repr=False)

    @property
    def Name(self) -> str:
        return self.name

    @property
    def Songs(self) -> list[RbxTrack]:
        return self.tracks

    @property
    def is_folder(self) -> bool:
        return False

    @property
    def is_playlist(self) -> bool:
        return True


@dataclass
class RbxFolder:
    name: str
    ID: str

    @property
    def Name(self) -> str:
        return self.name

    @property
    def is_folder(self) -> bool:
        return True

    @property
    def is_playlist(self) -> bool:
        return False


class RekordboxXmlLibrary:
    def __init__(self, path: Path, tree: list[dict]) -> None:
        self.path = path
        self.tree = tree
        self.exported_at = datetime.fromtimestamp(path.stat().st_mtime)


_HOW_TO_EXPORT = (
    "Exportá tu colección desde Rekordbox (Archivo → Exportar colección en "
    "formato xml) y elegí el archivo en ⚙ Configuración → Librerías."
)


def location_to_path(location: str) -> Path:
    """URI `file://localhost/...` del XML → ruta local."""
    host = ""
    path = location
    if location.startswith("file://"):
        rest = location[len("file://"):]
        slash = rest.find("/")
        host, path = (rest, "") if slash < 0 else (rest[:slash], rest[slash:])
        if host == "localhost":
            host = ""
    # Sin urlparse: un '#' o '?' crudo en el nombre no es fragmento ni query.
    path = unquote(path)
    if host:
        return Path(f"//{unquote(host)}{path}")
    if _DRIVE.match(path):
        return Path(PureWindowsPath(path[1:]).as_posix())
    return Path(path)


def _float_or_none(raw: str | None) -> float | None:
    try:
        value = float(raw) if raw else 0.0
    except ValueError:
        return None
    return value if value > 0 else None


def _index_collection(root: ET.Element) -> tuple[dict[str, ET.Element], dict[str, ET.Element]]:
    by_id: dict[str, ET.Element] = {}
    by_location: dict[str, ET.Element] = {}
    for el in root.iterfind("./COLLECTION/TRACK"):
        if el.get("TrackID"):
            by_id[el.get("TrackID", "")] = el
        if el.get("Location"):
            by_location[el.get("Location", "")] = el
    return by_id, by_location


def _track(el: ET.Element, position: int) -> RbxTrack:
    return RbxTrack(
        title=el.get("Name", "") or "",
        artist=el.get("Artist", "") or "",
        file_path=location_to_path(el.get("Location", "")),
        bpm=_float_or_none(el.get("AverageBpm")),
        key=(el.get("Tonality", "") or "").strip(),
        TrackNo=position,
    )


def _build_tree(root: ET.Element) -> list[dict]:
    by_id, by_location = _index_collection(root)

    def walk(node: ET.Element, prefix: str, node_id: str) -> dict:
        name = node.get("Name", "") or ""
        if node.get("Type") == "1":
            index = by_location if node.get("KeyType") == "1" else by_id
            tracks: list[RbxTrack] = []
            for ref in node.iterfind("./TRACK"):
                el = index.get(ref.get("Key", ""))
                if el is None or not el.get("Location"):
                    continue
                track = _track(el, len(tracks) + 1)
                if track.file_path.name:
                    tracks.append(track)
            return {"playlist": RbxPlaylist(name, node_id, tracks), "children": []}
        return {"playlist": RbxFolder(name, node_id), "children": walk_children(node, node_id)}

    def walk_children(parent: ET.Element, prefix: str) -> list[dict]:
        seen: dict[str, int] = {}
        out: list[dict] = []
        for child in parent.iterfind("./NODE"):
            name = child.get("Name", "") or ""
            seen[name] = seen.get(name, 0) + 1
            unique = name if seen[name] == 1 else f"{name}#{seen[name]}"
            out.append(walk(child, prefix, f"{prefix}/{unique}" if prefix else unique))
        return out

    root_node = root.find("./PLAYLISTS/NODE")
    if root_node is None:
        return []
    return walk_children(root_node, "")


def open_library(path: Path | None) -> RekordboxXmlLibrary:
    """Abre el rekordbox.xml exportado. RuntimeError con texto para el usuario si falla."""
    if path is None:
        raise RuntimeError(f"Todavía no elegiste el XML de Rekordbox.\n\n{_HOW_TO_EXPORT}")
    if not path.is_file():
        raise RuntimeError(f"No se encontró el archivo:\n{path}\n\n{_HOW_TO_EXPORT}")
    try:
        root = ET.parse(path).getroot()
    except (ET.ParseError, OSError) as e:
        raise RuntimeError(
            f"El XML de Rekordbox no se pudo leer (¿quedó a medio exportar?).\n\n"
            f"Volvé a exportarlo desde Rekordbox.\n\nDetalle: {e}"
        ) from e
    if root.tag != "DJ_PLAYLISTS":
        raise RuntimeError(f"Ese archivo no es un XML de Rekordbox.\n\n{_HOW_TO_EXPORT}")
    return RekordboxXmlLibrary(path, _build_tree(root))


def get_playlist_tree(library: RekordboxXmlLibrary) -> list[dict]:
    return library.tree


def playlist_song_count(playlist: RbxPlaylist) -> int:
    return len(playlist.tracks)


def get_songs(playlist: RbxPlaylist) -> list[RbxTrack]:
    return list(playlist.tracks)
