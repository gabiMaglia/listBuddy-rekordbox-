# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2025-2026 Gabriel Maglia
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

import codecs
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
from xml.parsers import expat

import file_access
from load_cancel import CancelCheck, LoadCancelled, ProgressCallback

__all__ = ["LoadCancelled"]  # re-export: lo importan los tests y la UI desde acá

_CHUNK = 1 << 20   # lectura del XML por bloques (también es la granularidad de la cancelación)
_MARGIN = 1 << 16  # bytes que se conservan por detrás del último bloque (etiqueta cortada)
_DRIVE = re.compile(r"^/[A-Za-z]:")


@dataclass(slots=True, eq=False)
class _TrackSrc:
    """`<TRACK>` de COLLECTION sin DOM: los pocos atributos que la app lee y el
    texto XML crudo del elemento completo (cues, beatgrid, el resto de los
    atributos) para reconstruirlo idéntico al exportar."""
    name: str
    artist: str
    bpm: str
    tonality: str
    location: str
    raw: bytes

    def to_element(self) -> ET.Element:
        return ET.fromstring(self.raw)


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

    location = src.location
    streaming = is_streaming_location(location)
    original = Path(location) if streaming else location_to_path(location)
    fixed = None if streaming else fixes.get(location)
    # Una reparación solo vale mientras el archivo original siga ausente.
    # El chequeo de disco solo se hace si hay reparación guardada (drives lentos);
    # corre en el hilo de carga, nunca en el de UI (TEC-17).
    use_fix = bool(fixed) and not original.exists()
    return RbxTrack(
        title=src.name,
        artist=src.artist,
        file_path=Path(fixed) if use_fix else original,
        bpm=_float_or_none(src.bpm),
        key=src.tonality.strip(),
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


_XML_DECL_ENCODING = re.compile(rb"""\s*<\?xml[^>]*?\sencoding\s*=\s*["']([\w.:-]+)["']""")
# Fin de una etiqueta de apertura: respeta '>' dentro de valores entre comillas.
_OPEN_TAG = re.compile(rb"""<[^\s/>]+(?:[^>"']|"[^"]*"|'[^']*')*>""")


# Codificaciones de texto que un exportador real declara. Lista blanca y no `_is_text_encoding`
# (privado de CPython, deja pasar idna/punycode/unicode_escape/utf-7). Se comparan por nombre
# canónico de `codecs.lookup`, así cubre los alias. zlib/bz2/base64/hex/rot13 quedan fuera:
# `zlib_codec` descomprimiría sin tope.
_XML_ENCODINGS = frozenset(
    codecs.lookup(n).name for n in (
        "utf-8", "utf-16", "utf-16-le", "utf-16-be", "utf-32", "utf-32-le", "utf-32-be", "ascii",
        *(f"iso8859-{i}" for i in (1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 13, 14, 15, 16)),
        *(f"cp125{i}" for i in range(9)), "cp437", "cp850", "cp852", "cp866", "cp874",
        "koi8-r", "koi8-u", "mac-roman", "mac-cyrillic", "shift_jis", "cp932", "euc-jp",
        "euc-kr", "cp949", "gb2312", "gbk", "gb18030", "big5", "cp950",
    )
)


def _transcode_from(head: bytes) -> str | None:
    """Codificación a decodificar si el archivo no es UTF-8; None si se lee tal cual."""
    if head.startswith(codecs.BOM_UTF8):
        return None
    if head.startswith((codecs.BOM_UTF32_LE, codecs.BOM_UTF32_BE)):
        return "utf-32"
    if head.startswith((codecs.BOM_UTF16_LE, codecs.BOM_UTF16_BE)):
        return "utf-16"
    if head[:2] == b"<\x00":
        return "utf-16-le"
    if head[:2] == b"\x00<":
        return "utf-16-be"
    m = _XML_DECL_ENCODING.match(head)
    enc = m.group(1).decode("ascii").lower() if m else "utf-8"
    if enc in ("utf-8", "utf8"):
        return None
    try:
        known = codecs.lookup(enc).name in _XML_ENCODINGS
    except LookupError:
        known = False
    if not known:
        raise LookupError(f"codificación no admitida: {enc}")
    return enc


def _window_keep(base: int, fed: int, cap_start: int | None, window: bytearray) -> int:
    """Offset absoluto desde el que hay que conservar la ventana tras alimentar a expat.

    Nunca pasa del último `<` alimentado: un `<` sin escapar no puede estar dentro de una
    etiqueta de apertura, así que la etiqueta que expat dejó pendiente empieza ahí o después
    (aunque mida más que _MARGIN).
    """
    keep = max(base, min(fed - _MARGIN, fed if cap_start is None else cap_start))
    lt = window.rfind(b"<")
    if lt >= 0:
        keep = max(base, min(keep, base + lt))
    return keep


def _scan(
    path: Path, should_cancel: CancelCheck | None, on_progress: ProgressCallback | None = None,
) -> _Parsed:
    """Un solo pasaje con expat y sin DOM: COLLECTION/TRACK → `_TrackSrc`,
    PLAYLISTS → `_Node`. Nunca existe un Element; la memoria es lo que se retiene.

    De cada TRACK de COLLECTION se corta el texto crudo usando el offset de bytes
    que informa expat; los hijos (TEMPO, POSITION_MARK…) no se procesan uno a uno.
    """
    by_id: dict[str, _TrackSrc] = {}
    by_location: dict[str, _TrackSrc] = {}
    root_node: _Node | None = None
    tags: list[str] = []
    nstack: list[_Node] = []
    window = bytearray()        # bytes alimentados desde `base` (lo que aún puede hacer falta cortar)
    base = 0
    cap_start: int | None = None   # offset absoluto del TRACK de COLLECTION en curso
    cap_attrs: dict[str, str] = {}
    inner = 0                      # profundidad dentro del TRACK capturado

    def start(name: str, attrs: dict[str, str]) -> None:
        nonlocal cap_start, cap_attrs, inner
        if cap_start is not None:
            inner += 1
            return
        tags.append(name)
        depth = len(tags)
        if depth == 1:
            if name != "DJ_PLAYLISTS":
                raise RuntimeError(f"Ese archivo no es un XML de Rekordbox.\n\n{_HOW_TO_EXPORT}")
        elif name == "TRACK" and depth == 3 and tags[1] == "COLLECTION":
            cap_start, cap_attrs, inner = parser.CurrentByteIndex, attrs, 0
        elif name == "NODE" and depth >= 3 and tags[1] == "PLAYLISTS":
            if depth == 3 and root_node is not None:
                nstack.append(_Node("", "", ""))      # NODE raíz repetido: se descarta
            else:
                nstack.append(_Node(attrs.get("Name", "") or "", attrs.get("Type", "") or "",
                                    attrs.get("KeyType", "") or ""))
        elif name == "TRACK" and nstack and tags[-2] == "NODE":
            nstack[-1].keys.append(attrs.get("Key", "") or "")

    def end(name: str) -> None:
        nonlocal cap_start, root_node, inner
        if cap_start is not None:
            if inner:
                inner -= 1
                return
            a = cap_start - base
            e = parser.CurrentByteIndex - base
            if a < 0 or e < a:
                # El texto crudo ya no está en la ventana: mejor fallar que exportar basura.
                raise ET.ParseError("no se pudo recortar un TRACK del XML (ventana de lectura inválida)")
            # expat informa el inicio de `</TRACK>`, o el FIN de la etiqueta si es `<TRACK …/>`.
            # El `>` de cierre puede no haber llegado todavía: se reescribe en vez de buscarlo.
            raw = window[a:e]
            if not (raw[-2:] == b"/>" and _OPEN_TAG.match(raw).end() == len(raw)):
                raw += b"</TRACK>"
            attrs = cap_attrs
            src = _TrackSrc(attrs.get("Name", "") or "", attrs.get("Artist", "") or "",
                            attrs.get("AverageBpm", "") or "", attrs.get("Tonality", "") or "",
                            attrs.get("Location", "") or "", bytes(raw))
            track_id = attrs.get("TrackID")
            if track_id:
                by_id[track_id] = src
            if src.location:
                by_location[src.location] = src
            cap_start = None
            tags.pop()
            return
        tags.pop()
        if name == "NODE" and nstack and len(tags) >= 2 and tags[1] == "PLAYLISTS":
            node = nstack.pop()
            if len(tags) == 2:                        # era el NODE raíz de PLAYLISTS
                if root_node is None:
                    root_node = node
            elif nstack:
                nstack[-1].children.append(node)

    # Si el archivo no es UTF-8 se transcodifica a UTF-8 y se fuerza esa codificación
    # en expat: así los offsets son de bytes UTF-8 y el texto crudo se reparsea sin deriva.
    parser = expat.ParserCreate("utf-8")
    parser.StartElementHandler = start
    parser.EndElementHandler = end
    # Expat >= 2.6 difiere el reparseo de una etiqueta cortada hasta tener el doble de bytes:
    # los eventos llegarían tarde y la ventana ya habría descartado el inicio del TRACK.
    if hasattr(parser, "SetReparseDeferralEnabled"):
        parser.SetReparseDeferralEnabled(False)
    try:
        total = path.stat().st_size
        with file_access.open_read(path) as fh:
            chunk = fh.read(_CHUNK)
            source_enc = _transcode_from(chunk[:512])
            decoder = codecs.getincrementaldecoder(source_enc)() if source_enc else None
            fed = 0
            while chunk:
                if should_cancel is not None and should_cancel():
                    raise LoadCancelled()
                try:
                    data = decoder.decode(chunk).encode("utf-8") if decoder else chunk
                except Exception as e:     # un decoder ajeno (TypeError, zlib.error…) no escapa del friendly error
                    raise ET.ParseError(f"no se pudo decodificar: {e}") from e
                window += data
                fed += len(data)
                parser.Parse(data, False)
                # expat guarda internamente una etiqueta cortada al final del bloque: se deja margen.
                keep = _window_keep(base, fed, cap_start, window)
                del window[:keep - base]
                base = keep
                chunk = fh.read(_CHUNK)
                if on_progress is not None:
                    on_progress(fh.tell(), total)
            parser.Parse(b"", True)
    except (expat.ExpatError, UnicodeError, LookupError) as e:
        raise ET.ParseError(str(e)) from e
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
                if src is None or not src.location:
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
    should_cancel: CancelCheck | None = None, on_progress: ProgressCallback | None = None,
) -> RekordboxXmlLibrary:
    """Abre el rekordbox.xml exportado. RuntimeError con texto para el usuario si falla.

    `should_cancel` se consulta durante el parseo; si devuelve True se lanza `LoadCancelled`."""
    if path is None:
        raise RuntimeError(f"Todavía no elegiste el XML de Rekordbox.\n\n{_HOW_TO_EXPORT}")
    if not path.is_file():
        raise RuntimeError(f"No se encontró el archivo:\n{path}\n\n{_HOW_TO_EXPORT}")
    try:
        parsed = _scan(path, should_cancel, on_progress)
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
    file_access.ensure_dir(dest.parent)
    # En modo texto, como cuando ElementTree abría la ruta él mismo: CRLF en Windows, LF en macOS.
    with file_access.atomic_write(dest, encoding="UTF-8", errors="xmlcharrefreplace") as fh:
        ET.ElementTree(root).write(fh, encoding="unicode", xml_declaration=True)
    return WriteResult(len(playlists), len(ids), relocated, missing)
