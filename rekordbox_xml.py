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

import contextlib
import copy
import os
import re
import sys
import unicodedata
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path, PurePath, PureWindowsPath
from urllib.parse import quote, unquote
from xml.etree import ElementTree as ET

from load_cancel import CHECK_EVERY, CancelCheck, LoadCancelled

__all__ = ["LoadCancelled"]  # re-export: lo importan los tests y la UI desde acá

_DRIVE = re.compile(r"^/[A-Za-z]:")


@dataclass(slots=True, eq=False)
class _TrackSrc:
    """`<TRACK>` del XML sin el DOM: atributos, texto y los hijos (TEMPO,
    POSITION_MARK…) serializados con sus colas, para reconstruirlo idéntico."""
    attrib: dict[str, str]
    text: str | None
    children: str

    @classmethod
    def from_element(cls, el: ET.Element) -> "_TrackSrc":
        kids = "".join(ET.tostring(c, encoding="unicode") for c in el)
        return cls(dict(el.attrib), el.text, kids)

    def to_element(self) -> ET.Element:
        el = ET.Element("TRACK", self.attrib)
        el.text = self.text
        if self.children:
            el.extend(ET.fromstring(f"<r>{self.children}</r>"))
        return el


@dataclass
class RbxTrack:
    title: str
    artist: str
    file_path: Path
    bpm: float | None = None
    key: str = ""         # Tonality tal cual la exporta Rekordbox («8A», «Am»)
    TrackNo: int = 0      # posición 1..n dentro de la playlist
    location: str = ""    # URI Location original del XML (clave de las reparaciones)
    relocated: bool = False  # True si la ruta viene de una reparación de List Buddy
    streaming: bool = False   # Location que no es un archivo (Beatport, TIDAL, SoundCloud…)
    # Fuente compacta del TRACK original (atributos + cues/beatgrid serializados),
    # solo para write_playlists_xml. No es un DOM vivo (T-094 / SEC-09).
    _src: "_TrackSrc | None" = field(default=None, repr=False, compare=False)

    @property
    def element(self) -> ET.Element | None:
        """TRACK original reconstruido a pedido (copia nueva en cada llamada)."""
        return self._src.to_element() if self._src is not None else None

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


def path_to_location(path: PurePath) -> str:
    """Ruta local → URI `file://localhost/...` (inversa de `location_to_path`)."""
    posix = path.as_posix()
    if not posix.startswith("/"):
        posix = "/" + posix          # «C:/Users/...» → «/C:/Users/...»
    return "file://localhost" + quote(posix, safe="/:")


def _float_or_none(raw: str | None) -> float | None:
    try:
        value = float(raw) if raw else 0.0
    except ValueError:
        return None
    return value if value > 0 else None


def is_streaming_location(location: str) -> bool:
    """Una Location que no es `file:` es una pista de streaming: no hay archivo que copiar."""
    return bool(location) and not location.lower().startswith("file:")


def _track(src: _TrackSrc, position: int, fixes: dict[str, str]) -> RbxTrack:
    attrs = src.attrib
    location = attrs.get("Location", "") or ""
    streaming = is_streaming_location(location)
    original = Path(location) if streaming else location_to_path(location)
    fixed = None if streaming else fixes.get(location)
    # Una reparación solo vale mientras el archivo original siga ausente.
    # El chequeo de disco solo se hace si hay reparación guardada (drives lentos);
    # corre en el hilo de carga, nunca en el de UI (TEC-17).
    use_fix = bool(fixed) and not original.exists()
    return RbxTrack(
        title=attrs.get("Name", "") or "",
        artist=attrs.get("Artist", "") or "",
        file_path=Path(fixed) if use_fix else original,
        bpm=_float_or_none(attrs.get("AverageBpm")),
        key=(attrs.get("Tonality", "") or "").strip(),
        TrackNo=position,
        location=location,
        relocated=use_fix,
        streaming=streaming,
        _src=src,
    )


@dataclass(slots=True)
class _Node:
    """NODE de PLAYLISTS sin DOM: nombre, tipo y las referencias a pistas."""
    name: str
    type: str
    key_type: str
    keys: list[str] = field(default_factory=list)
    children: list["_Node"] = field(default_factory=list)


@dataclass(slots=True)
class _Parsed:
    by_id: dict[str, _TrackSrc]
    by_location: dict[str, _TrackSrc]
    root_node: _Node | None


def _scan(path: Path, should_cancel: CancelCheck | None) -> _Parsed:
    """Un solo pasaje en streaming: COLLECTION/TRACK → `_TrackSrc`, PLAYLISTS → `_Node`.

    Cada elemento terminado se vacía y su padre se vacía también, así el DOM
    nunca crece más que un TRACK a la vez (memoria ~ lo que se retiene, no el XML).
    """
    by_id: dict[str, _TrackSrc] = {}
    by_location: dict[str, _TrackSrc] = {}
    root_node: _Node | None = None
    estack: list[ET.Element] = []
    nstack: list[_Node] = []
    ticks = 0
    with open(path, "rb") as fh:
        for event, el in ET.iterparse(fh, events=("start", "end")):
            ticks += 1
            if should_cancel is not None and ticks % CHECK_EVERY == 0 and should_cancel():
                raise LoadCancelled()
            tag = el.tag
            if event == "start":
                if not estack and tag != "DJ_PLAYLISTS":
                    raise RuntimeError(f"Ese archivo no es un XML de Rekordbox.\n\n{_HOW_TO_EXPORT}")
                estack.append(el)
                if tag == "NODE" and len(estack) >= 3 and estack[1].tag == "PLAYLISTS":
                    if len(estack) == 3 and root_node is not None:
                        nstack.append(_Node("", "", ""))   # NODE raíz repetido: se descarta
                    else:
                        nstack.append(_Node(el.get("Name", "") or "", el.get("Type", "") or "",
                                            el.get("KeyType", "") or ""))
                continue
            estack.pop()
            parent = estack[-1] if estack else None
            if parent is None:
                continue
            if tag == "TRACK" and parent.tag == "COLLECTION" and len(estack) == 2:
                src = _TrackSrc.from_element(el)
                track_id = src.attrib.get("TrackID")
                if track_id:
                    by_id[track_id] = src
                loc = src.attrib.get("Location")
                if loc:
                    by_location[loc] = src
                el.clear()
                parent.clear()
            elif tag == "TRACK" and parent.tag == "NODE" and nstack:
                key = el.get("Key", "") or ""
                nstack[-1].keys.append(key)
                el.clear()
                parent.clear()
            elif tag == "NODE" and nstack and estack[1].tag == "PLAYLISTS":
                node = nstack.pop()
                if len(estack) == 2:                      # era el NODE raíz de PLAYLISTS
                    if root_node is None:
                        root_node = node
                elif nstack:
                    nstack[-1].children.append(node)
                el.clear()
    return _Parsed(by_id, by_location, root_node)


def _build_tree(parsed: _Parsed, fixes: dict[str, str], should_cancel: CancelCheck | None = None) -> list[dict]:
    def walk(node: _Node, prefix: str, node_id: str) -> dict:
        if node.type == "1":
            index = parsed.by_location if node.key_type == "1" else parsed.by_id
            tracks: list[RbxTrack] = []
            for key in node.keys:
                if should_cancel is not None and len(tracks) % 512 == 0 and should_cancel():
                    raise LoadCancelled()
                src = index.get(key)
                if src is None or not src.attrib.get("Location"):
                    continue
                track = _track(src, len(tracks) + 1, fixes)
                if track.file_path.name:
                    tracks.append(track)
            return {"playlist": RbxPlaylist(node.name, node_id, tracks), "children": []}
        return {"playlist": RbxFolder(node.name, node_id), "children": walk_children(node, node_id)}

    def walk_children(parent: _Node, prefix: str) -> list[dict]:
        seen: dict[str, int] = {}
        out: list[dict] = []
        for child in parent.children:
            seen[child.name] = seen.get(child.name, 0) + 1
            unique = child.name if seen[child.name] == 1 else f"{child.name}#{seen[child.name]}"
            out.append(walk(child, prefix, f"{prefix}/{unique}" if prefix else unique))
        return out

    if parsed.root_node is None:
        return []
    return walk_children(parsed.root_node, "")


def open_library(
    path: Path | None, fixes: dict[str, str] | None = None, *,
    should_cancel: CancelCheck | None = None,
) -> RekordboxXmlLibrary:
    """Abre el rekordbox.xml exportado. RuntimeError con texto para el usuario si falla.

    `should_cancel` se consulta durante el parseo; si devuelve True se lanza `LoadCancelled`."""
    if path is None:
        raise RuntimeError(f"Todavía no elegiste el XML de Rekordbox.\n\n{_HOW_TO_EXPORT}")
    if not path.is_file():
        raise RuntimeError(f"No se encontró el archivo:\n{path}\n\n{_HOW_TO_EXPORT}")
    try:
        parsed = _scan(path, should_cancel)
    except (ET.ParseError, OSError) as e:
        raise RuntimeError(
            f"El XML de Rekordbox no se pudo leer (¿quedó a medio exportar?).\n\n"
            f"Volvé a exportarlo desde Rekordbox.\n\nDetalle: {e}"
        ) from e
    return RekordboxXmlLibrary(path, _build_tree(parsed, fixes or {}, should_cancel))


def get_playlist_tree(library: RekordboxXmlLibrary) -> list[dict]:
    return library.tree


def playlist_song_count(playlist: RbxPlaylist) -> int:
    return len(playlist.tracks)


def get_songs(playlist: RbxPlaylist) -> list[RbxTrack]:
    return list(playlist.tracks)


@dataclass
class WriteResult:
    playlists: int
    tracks: int
    relocated: int
    missing: int


def _same_file(a: Path, b: Path) -> bool:
    if a.resolve() == b.resolve():
        return True
    return a.exists() and b.exists() and os.path.samefile(a, b)


def _adapt_relocated(el: ET.Element, t: RbxTrack) -> None:
    """Size real del archivo reparado; si cambió el formato, fuera los datos del viejo."""
    with contextlib.suppress(OSError):
        el.set("Size", str(t.file_path.stat().st_size))
    if t.file_path.suffix.lower() != location_to_path(t.location).suffix.lower():
        for attr in ("Kind", "BitRate", "SampleRate"):
            el.attrib.pop(attr, None)


def _file_key(location: str) -> str:
    """Clave canónica del archivo al que apunta una Location: ruta decodificada,
    Unicode NFC y, en macOS/Windows (discos sin distinción de mayúsculas por
    defecto), en minúsculas."""
    key = unicodedata.normalize("NFC", location_to_path(location).as_posix())
    return key.casefold() if sys.platform in ("darwin", "win32") else key


def write_playlists_xml(
    playlists: list[RbxPlaylist], dest: Path, *, source: Path | None = None,
    name_suffix: str = " (List Buddy)", app_version: str = "",
) -> WriteResult:
    """XML nuevo (formato oficial) con solo estas playlists, para importar en
    Rekordbox. Copia cada TRACK original (cues, beatgrid, metadatos) y pone en
    `Location` la ruta reparada. Nunca escribe sobre el XML de origen."""
    tmp = dest.with_name(dest.name + ".tmp")
    if source is not None and (_same_file(dest, source) or _same_file(tmp, source)):
        raise ValueError("No se puede sobrescribir el XML que exportaste desde Rekordbox.")
    root = ET.Element("DJ_PLAYLISTS", Version="1.0.0")
    ET.SubElement(root, "PRODUCT", Name="List Buddy", Version=app_version, Company="")
    collection = ET.SubElement(root, "COLLECTION")
    # Una entrada por ARCHIVO: Rekordbox rechaza el import si dos TRACK apuntan
    # a la misma ruta. La comparación es por archivo físico (clave canónica), no
    # por texto: el XML de Rekordbox y path_to_location() escapan distinto
    # ( ( ) ' & ! ) y macOS puede dar la misma ruta en NFC o NFD (D-11).
    def final_location(t: RbxTrack) -> str:
        return path_to_location(t.file_path) if t.relocated else t.location

    def key_of(t: RbxTrack) -> str:
        return t.location if t.streaming else _file_key(final_location(t))

    ids: dict[str, str] = {}
    relocated = missing = 0
    for pl in playlists:
        for t in pl.tracks:
            key = key_of(t)
            if key in ids:
                continue
            location = final_location(t)
            new_id = str(len(ids) + 1)
            ids[key] = new_id
            el = copy.deepcopy(t.element) if t.element is not None else ET.Element(
                "TRACK", Name=t.title, Artist=t.artist)
            el.set("TrackID", new_id)
            el.set("Location", location)
            if t.relocated:
                _adapt_relocated(el, t)
            collection.append(el)
            relocated += int(t.relocated)
            missing += int(not t.streaming and not t.file_path.exists())
    collection.set("Entries", str(len(ids)))
    root_node = ET.SubElement(ET.SubElement(root, "PLAYLISTS"), "NODE",
                              Type="0", Name="ROOT", Count=str(len(playlists)))
    for pl in playlists:
        node = ET.SubElement(root_node, "NODE", Name=pl.name + name_suffix, Type="1",
                             KeyType="0", Entries=str(len(pl.tracks)))
        for t in pl.tracks:
            ET.SubElement(node, "TRACK", Key=ids[key_of(t)])
    ET.indent(root)
    dest.parent.mkdir(parents=True, exist_ok=True)
    try:
        ET.ElementTree(root).write(tmp, encoding="UTF-8", xml_declaration=True)
        os.replace(tmp, dest)
    except BaseException:
        with contextlib.suppress(OSError):
            tmp.unlink(missing_ok=True)
        raise
    return WriteResult(len(playlists), len(ids), relocated, missing)
