"""
traktor_db.py
-------------
Lector de la librería de Traktor Pro 3/4 (formato NML).

Interfaz pública compatible con db.py (Rekordbox):
  find_collection_path()     → Path | None
  open_collection(path=None) → TraktorCollection  (lanza RuntimeError si no encuentra)
  get_playlist_tree(col)     → list[dict]          (mismo shape que db.get_playlist_tree)
  playlist_song_count(pl)    → int

Formato NML (XML):
  <NML>
    <COLLECTION ENTRIES="N">
      <ENTRY TITLE="..." ARTIST="...">
        <LOCATION DIR="/:Users/:user/:Music/:" FILE="track.mp3" VOLUME="Macintosh HD"/>
        <TEMPO BPM="128.0"/>
      </ENTRY>
    </COLLECTION>
    <PLAYLISTS>
      <NODE TYPE="FOLDER" NAME="$ROOT">
        <SUBNODES>
          <NODE TYPE="PLAYLIST" NAME="Set 1">
            <PLAYLIST ENTRIES="20" UUID="...">
              <ENTRY>
                <PRIMARYKEY TYPE="TRACK"
                  KEY="Macintosh HD/:Users/:user/:Music/:track.mp3"/>
              </ENTRY>
            </PLAYLIST>
          </NODE>
          <NODE TYPE="FOLDER" NAME="Techno">
            <SUBNODES>...</SUBNODES>
          </NODE>
        </SUBNODES>
      </NODE>
    </PLAYLISTS>
  </NML>

Conversión de rutas:
  KEY / DIR usan '/: ' como separador.
  "Macintosh HD/:Users/:user/:Music/:track.mp3"
  → strip volumen → "/:Users/:user/:Music/:track.mp3"
  → replace '/: ' with '/' → "/Users/user/Music/track.mp3"
"""
from __future__ import annotations

import glob
from dataclasses import dataclass, field
from pathlib import Path
from xml.etree import ElementTree as ET


# ─────────────────────────────────────────────── Data classes ────────────

@dataclass
class TraktorTrack:
    title: str
    artist: str
    file_path: Path
    bpm: float | None = None

    # Compatibility shims used by rekordbox_export helpers in worker.py
    @property
    def FolderPath(self) -> str:
        return str(self.file_path)

    @property
    def Title(self) -> str:
        return self.title

    @property
    def ArtistName(self) -> str:
        return self.artist

    # get_content(song) probes song.Content / song.content → return self
    @property
    def Content(self) -> "TraktorTrack":
        return self

    @property
    def content(self) -> "TraktorTrack":
        return self

    # worker.py sorts by TrackNo; set to 0 so list order is preserved
    TrackNo: int = 0


@dataclass
class TraktorPlaylist:
    name: str
    uuid: str
    track_count: int
    tracks: list[TraktorTrack] = field(default_factory=list, repr=False)

    # ── duck-type interface matching DjmdPlaylist ──
    @property
    def Name(self) -> str:
        return self.name

    @property
    def is_folder(self) -> bool:
        return False

    @property
    def is_playlist(self) -> bool:
        return True


@dataclass
class TraktorFolder:
    name: str

    @property
    def Name(self) -> str:
        return self.name

    @property
    def is_folder(self) -> bool:
        return True

    @property
    def is_playlist(self) -> bool:
        return False


# ─────────────────────────────────────────────── Collection ──────────────

class TraktorCollection:
    def __init__(self, path: Path, tree: list[dict]) -> None:
        self.path = path
        self._tree = tree


# ─────────────────────────────────────────────── Path helpers ────────────

def _nml_key_to_path(key: str) -> Path:
    """
    'Macintosh HD/:Users/:user/:Music/:file.mp3'
    → '/Users/user/Music/file.mp3'
    """
    idx = key.find("/:")
    if idx == -1:
        return Path(key)
    return Path(key[idx:].replace("/:", "/"))


def _location_to_key(volume: str, dir_attr: str, file_attr: str) -> str:
    """Reconstruct the KEY as Traktor stores it: VOLUME + DIR + FILE."""
    return volume + dir_attr + file_attr


def _location_to_path(dir_attr: str, file_attr: str) -> Path:
    """Convert LOCATION DIR+FILE to filesystem path."""
    return Path(dir_attr.replace("/:", "/")) / file_attr


def path_to_location(path: Path) -> tuple[str, str, str]:
    """
    Encoder: filesystem Path -> Traktor's (VOLUME, DIR, FILE) LOCATION
    attributes. Inverse of the decoders above — this is the correctness-
    critical piece of F-07 (relocate): a wrong encoding either fails to
    resolve in Traktor or, worse, silently resolves to the wrong file.

    Confirmed format (real-world Windows Traktor NML samples; KEY is the
    literal concatenation VOLUME + DIR + FILE, see `_location_to_key`):
        "C:/:Users/:dj/:Music/:Track01.mp3"
        -> VOLUME="C:", DIR="/:Users/:dj/:Music/:", FILE="Track01.mp3"

    DIR wraps every parent segment in its own "/:" pair (leading AND a
    final trailing "/:"), which is exactly what `_location_to_path` above
    undoes via `.replace("/:", "/")`.

    macOS branch (below) is UNVERIFIED — this machine is Windows and there
    is no real macOS Traktor collection.nml to test against. See the
    inline comment; flagged as a caveat for QA on macOS (ADR-001,
    Consecuencias: "requiere tests con NML real de Windows y macOS").
    """
    if not path.is_absolute():
        raise ValueError(f"path_to_location requiere un path absoluto: {path}")

    file_attr = path.name
    if not file_attr:
        raise ValueError(f"path sin nombre de archivo: {path}")

    if path.drive:
        # Windows: PureWindowsPath("D:\\Music\\dj\\t.mp3").drive == "D:";
        # .parts == ('D:\\', 'Music', 'dj', 't.mp3') → strip drive + filename.
        if path.drive.startswith("\\\\"):
            # UNC / network share (\\server\share\...) — format unverified,
            # fail loud instead of writing a guessed/likely-wrong LOCATION.
            raise NotImplementedError(
                f"Rutas de red (UNC) no soportadas por el encoder todavía: {path}"
            )
        volume = path.drive  # e.g. "D:"
        dir_parts = path.parts[1:-1]
    else:
        # POSIX (macOS/Linux). UNVERIFIED on a real macOS Traktor NML:
        #   - External volume mounted at /Volumes/<Name>/... → VOLUME=<Name>,
        #     DIR excludes the /Volumes/<Name> prefix (matches how macOS
        #     itself and Traktor address external disks).
        #   - Anything else (e.g. boot volume path like /Users/...) → real
        #     Traktor NML stores the boot volume's *display name* (e.g.
        #     "Macintosh HD") in VOLUME even though that name never appears
        #     in the path itself (it's a disk label, not a path component).
        #     We cannot derive that name from the path alone, so this falls
        #     back to a hardcoded placeholder. TODO(macOS QA): confirm via
        #     `diskutil info /` (or similar) whether this placeholder is
        #     safe to assume, or whether it must be a user-provided setting.
        parts = path.parts  # ('/', 'Volumes', 'Name', ...) or ('/', 'Users', ...)
        if len(parts) > 2 and parts[1] == "Volumes":
            volume = parts[2]
            dir_parts = parts[3:-1]
        else:
            volume = "Macintosh HD"  # best-effort placeholder — UNVERIFIED, see above
            dir_parts = parts[1:-1]

    dir_attr = "".join(f"/:{segment}" for segment in dir_parts) + "/:"
    return volume, dir_attr, file_attr


def path_to_key(path: Path) -> str:
    """Convenience: path -> new KEY string, ready for PRIMARYKEY@KEY."""
    return _location_to_key(*path_to_location(path))


# ─────────────────────────────────────────────── Discovery ───────────────

def find_collection_path() -> Path | None:
    """Return the most recent Traktor collection.nml, or None."""
    base = Path.home() / "Documents" / "Native Instruments"
    if not base.exists():
        return None
    candidates = sorted(
        glob.glob(str(base / "Traktor*" / "collection.nml")),
        reverse=True,
    )
    return Path(candidates[0]) if candidates else None


def detect_installed_version() -> str | None:
    """
    Return a human-readable version string if Traktor is found,
    e.g. 'Traktor 4.4.1', otherwise None.
    """
    base = Path.home() / "Documents" / "Native Instruments"
    if not base.exists():
        return None
    dirs = sorted(
        [d.name for d in base.iterdir() if d.is_dir() and d.name.startswith("Traktor")],
        reverse=True,
    )
    return dirs[0] if dirs else None


# ─────────────────────────────────────────────── Parser ──────────────────

def open_collection(path: Path | None = None) -> TraktorCollection:
    """
    Parse the NML file and return a TraktorCollection.
    Raises RuntimeError with a user-friendly message if not found.
    """
    if path is None:
        path = find_collection_path()
    if path is None or not path.exists():
        raise RuntimeError(
            "No se encontró la librería de Traktor.\n"
            "Asegurate de que Traktor Pro 3 o 4 esté instalado y\n"
            "que hayas abierto Traktor al menos una vez."
        )

    try:
        root = ET.parse(str(path)).getroot()
    except ET.ParseError as e:
        raise RuntimeError(
            f"No se pudo leer la librería de Traktor.\nDetalle: {e}"
        ) from e

    track_index = _build_track_index(root)
    tree = _build_tree(root, track_index)
    return TraktorCollection(path=path, tree=tree)


def _build_track_index(root: ET.Element) -> dict[str, TraktorTrack]:
    """Build {KEY: TraktorTrack} from <COLLECTION>."""
    index: dict[str, TraktorTrack] = {}
    collection = root.find("COLLECTION")
    if collection is None:
        return index

    for entry in collection.findall("ENTRY"):
        loc = entry.find("LOCATION")
        if loc is None:
            continue

        volume = loc.get("VOLUME", "")
        dir_attr = loc.get("DIR", "")
        file_attr = loc.get("FILE", "")

        key = _location_to_key(volume, dir_attr, file_attr)
        file_path = _location_to_path(dir_attr, file_attr)

        title = entry.get("TITLE", "") or file_attr
        artist = entry.get("ARTIST", "") or ""

        bpm: float | None = None
        tempo_el = entry.find("TEMPO")
        if tempo_el is not None:
            try:
                raw = float(tempo_el.get("BPM", 0) or 0)
                bpm = raw if raw > 0 else None
            except (ValueError, TypeError):
                pass

        index[key] = TraktorTrack(
            title=title,
            artist=artist,
            file_path=file_path,
            bpm=bpm,
        )
    return index


def _build_tree(
    root: ET.Element,
    track_index: dict[str, TraktorTrack],
) -> list[dict]:
    """
    Build the same {'playlist': obj, 'children': [...]} tree
    as db.get_playlist_tree(), so ui.py needs no branching.
    """
    playlists_el = root.find("PLAYLISTS")
    if playlists_el is None:
        return []

    root_node = playlists_el.find("NODE")  # $ROOT
    if root_node is None:
        return []

    def walk(node: ET.Element) -> dict | None:
        node_type = node.get("TYPE", "")
        name = node.get("NAME", "")

        # Skip smart/auto lists
        if node_type == "SMARTLIST":
            return None

        if node_type == "FOLDER":
            children: list[dict] = []
            subnodes = node.find("SUBNODES")
            if subnodes is not None:
                for child in subnodes:
                    result = walk(child)
                    if result is not None:
                        children.append(result)
            folder = TraktorFolder(name=name)
            return {"playlist": folder, "children": children}

        if node_type == "PLAYLIST":
            pl_el = node.find("PLAYLIST")
            entries = 0
            uuid = ""
            tracks: list[TraktorTrack] = []

            if pl_el is not None:
                entries = int(pl_el.get("ENTRIES", 0) or 0)
                uuid = pl_el.get("UUID", "") or ""

                for entry in pl_el.findall("ENTRY"):
                    pk = entry.find("PRIMARYKEY")
                    if pk is None:
                        continue
                    key = pk.get("KEY", "")
                    track = track_index.get(key)
                    if track is not None:
                        tracks.append(track)

            playlist = TraktorPlaylist(
                name=name,
                uuid=uuid,
                track_count=entries,
                tracks=tracks,
            )
            return {"playlist": playlist, "children": []}

        return None

    result: list[dict] = []
    subnodes = root_node.find("SUBNODES")
    if subnodes is not None:
        for child in subnodes:
            item = walk(child)
            if item is not None:
                result.append(item)
    return result


# ─────────────────────────────────── Public API (mirrors db.py) ──────────

def get_playlist_tree(collection: TraktorCollection) -> list[dict]:
    return collection._tree


def playlist_song_count(playlist: TraktorPlaylist) -> int:
    return playlist.track_count if isinstance(playlist, TraktorPlaylist) else 0


def get_songs(playlist: TraktorPlaylist) -> list[TraktorTrack]:
    """Return a copy of the track list with TrackNo set for sort order."""
    from copy import copy
    result = []
    for i, t in enumerate(playlist.tracks):
        t2 = copy(t)
        t2.TrackNo = i + 1
        result.append(t2)
    return result
