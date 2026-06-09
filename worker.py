"""
worker.py
---------
QThread que ejecuta la exportación sin congelar la UI.
"""
from __future__ import annotations

import shutil
from pathlib import Path

from PyQt6.QtCore import QThread, pyqtSignal

from rekordbox_export import get_songs as _rb_get_songs
from rekordbox_export import get_content, get_artist, resolve_path, sanitize


def _get_songs(pl):
    """Dispatch to Traktor or Rekordbox get_songs depending on playlist type."""
    try:
        from traktor_db import TraktorPlaylist, get_songs as _tk_get_songs
        if isinstance(pl, TraktorPlaylist):
            return _tk_get_songs(pl)
    except ImportError:
        pass
    return _rb_get_songs(pl)


def get_songs(pl):
    return _get_songs(pl)


_MAX_STEM = 200


def _safe_filename(prefix: str, artist: str, title: str, suffix: str) -> str:
    parts = [prefix]
    if artist:
        parts.append(artist)
    parts.append(title or "Sin título")
    stem = " - ".join(parts)

    if len(stem) <= _MAX_STEM:
        return stem + suffix

    fixed = len(prefix) + (len(" - ") + len(artist) if artist else 0) + len(" - ")
    budget = _MAX_STEM - fixed

    if budget >= 8:
        title = title[: budget - 1] + "…"
    else:
        half = (_MAX_STEM - len(prefix) - len(" - ") * 2) // 2
        artist = artist[: max(4, half - 1)] + "…"
        title = title[: max(4, half - 1)] + "…"

    parts = [prefix]
    if artist:
        parts.append(artist)
    parts.append(title)
    return " - ".join(parts) + suffix


class ExportWorker(QThread):
    log         = pyqtSignal(str)
    progress    = pyqtSignal(int, int)        # (hechas, total)
    finished_ok = pyqtSignal(int, int, int, str)  # (copiadas, faltantes, saltadas, status)
    # status: "ok" | "cancelled" | "error"

    def __init__(self, playlists: list, output_root: Path) -> None:
        super().__init__()
        self._playlists = playlists
        self._output_root = output_root

    def run(self) -> None:
        copied_total = missing_total = skipped_total = 0
        missing_tracks: list[str] = []

        # ── Pre-build: una sola query lazy por playlist ───────────────────
        playlist_songs: list[tuple] = []
        for pl in self._playlists:
            songs = _get_songs_list(pl)
            if songs:
                playlist_songs.append((pl, songs))

        total_songs = sum(len(s) for _, s in playlist_songs)
        self.progress.emit(0, max(total_songs, 1))

        # ── Chequeo de espacio en disco ───────────────────────────────────
        try:
            total_bytes = _estimate_size(playlist_songs)
            if total_bytes > 0:
                dest_check = (
                    self._output_root
                    if self._output_root.exists()
                    else _nearest_existing(self._output_root)
                )
                free = shutil.disk_usage(str(dest_check)).free
                if total_bytes > free:
                    needed = total_bytes / 1_073_741_824
                    avail  = free / 1_073_741_824
                    self.log.emit(
                        f"✗  Espacio insuficiente: necesitás ~{needed:.1f} GB, "
                        f"disponible: {avail:.1f} GB.\n"
                        "   Liberá espacio e intentá de nuevo."
                    )
                    self.finished_ok.emit(0, 0, 0, "error")
                    return
        except Exception:
            pass  # si el chequeo falla, seguimos igual

        # ── Loop principal ────────────────────────────────────────────────
        done = 0
        for pl, songs in playlist_songs:
            self.log.emit(f"▶  {pl.Name}")
            dest_dir = self._output_root / sanitize(pl.Name)

            sorted_songs = [s for _, s in sorted(
                enumerate(songs),
                key=lambda i_s: (i_s[1].TrackNo or 0, i_s[0])
            )]

            dest_dir.mkdir(parents=True, exist_ok=True)
            pad = len(str(len(sorted_songs)))

            for idx, song in enumerate(sorted_songs, start=1):
                if self.isInterruptionRequested():
                    self.log.emit("\n⏹  Exportación cancelada.")
                    self.finished_ok.emit(copied_total, missing_total, skipped_total, "cancelled")
                    return

                content  = get_content(song)
                raw_path = getattr(content, "FolderPath", None) if content else None
                src      = resolve_path(raw_path)

                done += 1
                self.progress.emit(done, max(total_songs, 1))

                if src is None:
                    label = getattr(content, "Title", None) or raw_path or "desconocido"
                    self.log.emit(f"   ⚠  No se encontró: {label}")
                    missing_tracks.append(f"{pl.Name} → {label}")
                    missing_total += 1
                    continue

                prefix   = str(idx).zfill(pad)
                artist   = sanitize(get_artist(content))
                title    = sanitize(getattr(content, "Title", None) or "Sin título")
                filename = _safe_filename(prefix, artist, title, src.suffix)
                dest     = dest_dir / filename

                if dest.exists():
                    self.log.emit(f"   ⏭  Ya existe: {dest.name}")
                    skipped_total += 1
                else:
                    try:
                        shutil.copy2(src, dest)
                        self.log.emit(f"   ✓  {dest.name}")
                        copied_total += 1
                    except OSError as e:
                        if e.errno == 28:  # ENOSPC — disco lleno
                            self.log.emit(f"   ✗  Disco lleno al copiar {dest.name}")
                            self.log.emit("      Liberá espacio e intentá de nuevo.")
                            self.finished_ok.emit(copied_total, missing_total, skipped_total, "error")
                            return
                        self.log.emit(f"   ✗  Error copiando {dest.name}: {e}")
                        missing_tracks.append(f"{pl.Name} → {dest.name} (error de copia)")
                        missing_total += 1
                    except Exception as e:
                        self.log.emit(f"   ✗  Error copiando {dest.name}: {e}")
                        missing_tracks.append(f"{pl.Name} → {dest.name} (error de copia)")
                        missing_total += 1

        if missing_tracks:
            self.log.emit("\n─── Tracks no encontradas ───")
            for t in missing_tracks:
                self.log.emit(f"  ✗  {t}")

        self.finished_ok.emit(copied_total, missing_total, skipped_total, "ok")


# ── Helpers ───────────────────────────────────────────────────────────────

def _get_songs_list(pl) -> list:
    try:
        return list(get_songs(pl))
    except Exception:
        return []


def _estimate_size(playlist_songs: list[tuple]) -> int:
    """Suma los tamaños de los archivos fuente que existen en disco."""
    total = 0
    for _, songs in playlist_songs:
        for song in songs:
            content = get_content(song)
            raw = getattr(content, "FolderPath", None) if content else None
            src = resolve_path(raw)
            if src:
                try:
                    total += src.stat().st_size
                except OSError:
                    pass
    return total


def _nearest_existing(path: Path) -> Path:
    """Sube por los padres hasta encontrar un directorio que exista."""
    p = path
    while p != p.parent:
        p = p.parent
        if p.exists():
            return p
    return Path("/")
