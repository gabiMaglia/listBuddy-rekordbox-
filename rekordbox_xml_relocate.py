"""
rekordbox_xml_relocate.py
-------------------------
T-081: reparar enlaces rotos de la fuente Rekordbox (XML exportado). Mismo
loop que Traktor (relocate_core.BaseRelocateWorker: indexado, matching,
modal, auto-resolución), pero «aplicar» solo anota la ruta nueva en el
almacén propio de List Buddy (rekordbox_fixes.json). Nunca escribe el XML
ni ningún archivo de Rekordbox (ADR-004).
"""
from __future__ import annotations

import logging
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from relocate_core import BaseRelocateWorker, RelocateScope, scope_contains
from rekordbox_fixes import FixStore
from rekordbox_xml import RekordboxXmlLibrary, get_playlist_tree, open_library

_log = logging.getLogger("listBuddy")
_PROGRESS_EVERY = 25


@dataclass
class XmlBrokenTrack:
    title: str
    artist: str
    original_path: Path
    location: str


def _iter_tracks(nodes: list[dict]):
    for node in nodes:
        pl = node["playlist"]
        if pl.is_folder:
            yield from _iter_tracks(node["children"])
        else:
            yield from pl.tracks


def find_broken_tracks(
    library: RekordboxXmlLibrary,
    should_stop: Callable[[], bool] | None = None,
    on_progress: Callable[[int, int], None] | None = None,
    scope: RelocateScope | None = None,
) -> list[tuple[str, XmlBrokenTrack]]:
    """Pistas de las playlists cuyo archivo (ya con reparaciones aplicadas) no
    existe. Una por `Location`, aunque esté en varias playlists."""
    unique: dict[str, object] = {}
    for t in _iter_tracks(get_playlist_tree(library)):
        if t.location and not t.streaming and t.location not in unique:
            unique[t.location] = t
    tracks = list(unique.values())
    broken: list[tuple[str, XmlBrokenTrack]] = []
    total = len(tracks)
    for i, t in enumerate(tracks, start=1):
        if should_stop is not None and should_stop():
            break
        if scope_contains(scope, t.FolderPath) and not t.file_path.exists():
            broken.append((t.location, XmlBrokenTrack(t.title, t.artist, t.file_path, t.location)))
        if on_progress is not None and (i % _PROGRESS_EVERY == 0 or i == total):
            on_progress(i, total)
    return broken


class RekordboxXmlRelocateWorker(BaseRelocateWorker):
    def __init__(
        self, xml_path: Path, fixes_path: Path, search_root: Path,
        auto_resolve: bool = False, scope: RelocateScope | None = None,
    ) -> None:
        super().__init__(search_root, auto_resolve=auto_resolve, scope=scope)
        self._xml_path = xml_path
        self._store = FixStore(fixes_path)
        self._new_fixes: dict[str, str] = {}

    def _broken_scope_noun(self) -> str:
        return "lista exportada de Rekordbox"

    def _write_target_name(self) -> str:
        return "XML"

    def _engine_name(self) -> str:
        return "Rekordbox XML"

    def _label_for(self, broken_track: XmlBrokenTrack) -> str:
        return broken_track.title or broken_track.original_path.name

    def _apply_one(self, raw_entry: str, broken_track: XmlBrokenTrack, chosen: Path) -> bool:
        self._new_fixes[raw_entry] = str(chosen)
        return True

    def run(self) -> None:
        _log.info("Relocate Rekordbox XML: inicio · xml=%s · search_root=%s · auto=%s",
                  self._xml_path, self._search_root, self._auto_resolve)
        try:
            library = open_library(self._xml_path, fixes=self._store.load())
        except RuntimeError as e:
            self.log.emit(f"✗  {e}")
            self.finished_ok.emit(0, 0, 0, "error")
            return

        self.log.emit("🔎  Detectando enlaces rotos…")
        broken = find_broken_tracks(
            library,
            should_stop=self.isInterruptionRequested,
            on_progress=lambda done, total: self.progress.emit(done, total),
            scope=self._scope,
        )
        if self.isInterruptionRequested():
            self._emit_cancelled(0, 0, 0)
            return

        result = self._run_resolution(broken)
        if result is None:
            return
        if result.repaired == 0:
            self.log.emit("\nSin reparaciones para guardar.")
            self.finished_ok.emit(0, result.skipped, result.unresolved, "ok")
            return
        try:
            self._store.merge(self._new_fixes)
        except OSError as e:
            self.log.emit("✗  No se pudieron guardar las reparaciones (espacio o permisos).")
            _log.error("Relocate Rekordbox XML: no se pudo guardar %s: %s", self._store.path, e)
            self.finished_ok.emit(0, 0, 0, "error")
            return
        self.log.emit(
            "💾  Reparaciones guardadas en List Buddy. Tu XML y Rekordbox no se modificaron."
        )
        self._log_final_success(result.repaired, result.skipped, result.unresolved)
