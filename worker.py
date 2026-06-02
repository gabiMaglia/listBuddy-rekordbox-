"""
worker.py
---------
QThread que ejecuta la exportación sin congelar la UI.
Incluye manejo robusto de edge cases (Fase 3 del plan).
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


def get_songs(pl):  # keep public name used by _try_count and callers
    return _get_songs(pl)

# Límite conservador del stem del filename para no superar MAX_PATH de Windows (260).
_MAX_STEM = 200


def _safe_filename(prefix: str, artist: str, title: str, suffix: str) -> str:
    """
    Construye el nombre de archivo final.
    Trunca title (y artist si es necesario) para no pasar _MAX_STEM chars en el stem.
    Nunca trunca prefix ni suffix.
    """
    parts = [prefix]
    if artist:
        parts.append(artist)
    parts.append(title or "Sin título")
    stem = " - ".join(parts)

    if len(stem) <= _MAX_STEM:
        return stem + suffix

    # Calcular cuánto espacio queda para el título
    fixed = len(prefix) + (len(" - ") + len(artist) if artist else 0) + len(" - ")
    budget = _MAX_STEM - fixed

    if budget >= 8:
        title = title[: budget - 1] + "…"
    else:
        # Ni siquiera el artista entra — truncar ambos
        half = (_MAX_STEM - len(prefix) - len(" - ") * 2) // 2
        artist = artist[: max(4, half - 1)] + "…"
        title = title[: max(4, half - 1)] + "…"

    parts = [prefix]
    if artist:
        parts.append(artist)
    parts.append(title)
    return " - ".join(parts) + suffix


class ExportWorker(QThread):
    log = pyqtSignal(str)            # línea de log
    progress = pyqtSignal(int, int)  # (hechas, total)
    finished_ok = pyqtSignal(int, int)  # (copiadas, no_encontradas)

    def __init__(self, playlists: list, output_root: Path) -> None:
        super().__init__()
        self._playlists = playlists
        self._output_root = output_root

    def run(self) -> None:
        copied_total = missing_total = 0
        missing_tracks: list[str] = []

        # Contar total de canciones para la barra de progreso.
        total_songs = sum(
            len(get_songs(pl)) for pl in self._playlists
            if self._try_count(pl) is not None
        )
        done = 0
        self.progress.emit(0, max(total_songs, 1))

        for pl in self._playlists:
            self.log.emit(f"▶  {pl.Name}")
            dest_dir = self._output_root / sanitize(pl.Name)

            # Orden estable: por TrackNo (None → 0), desempate por posición original.
            raw_songs = get_songs(pl)
            songs = [s for _, s in sorted(
                enumerate(raw_songs),
                key=lambda i_s: (i_s[1].TrackNo or 0, i_s[0])
            )]

            if not songs:
                self.log.emit("   [vacía, se omite]")
                continue

            dest_dir.mkdir(parents=True, exist_ok=True)
            pad = len(str(len(songs)))

            for idx, song in enumerate(songs, start=1):
                content = get_content(song)
                raw_path = getattr(content, "FolderPath", None) if content else None
                src = resolve_path(raw_path)

                done += 1
                self.progress.emit(done, max(total_songs, 1))

                if src is None:
                    track_label = (
                        getattr(content, "Title", None) or raw_path or "desconocido"
                    )
                    self.log.emit(f"   ⚠  No se encontró: {track_label}")
                    missing_tracks.append(f"{pl.Name} → {track_label}")
                    missing_total += 1
                    continue

                prefix = str(idx).zfill(pad)
                artist = sanitize(get_artist(content))
                title = sanitize(getattr(content, "Title", None) or "Sin título")
                filename = _safe_filename(prefix, artist, title, src.suffix)
                dest = dest_dir / filename

                if dest.exists():
                    self.log.emit(f"   ⏭  Ya existe: {dest.name}")
                else:
                    try:
                        shutil.copy2(src, dest)
                        self.log.emit(f"   ✓  {dest.name}")
                    except Exception as e:
                        self.log.emit(f"   ✗  Error copiando {dest.name}: {e}")
                        missing_tracks.append(f"{pl.Name} → {dest.name} (error de copia)")
                        missing_total += 1
                        continue
                copied_total += 1

        if missing_tracks:
            self.log.emit("\n─── Tracks no encontradas ───")
            for t in missing_tracks:
                self.log.emit(f"  ✗  {t}")

        self.finished_ok.emit(copied_total, missing_total)

    @staticmethod
    def _try_count(pl) -> int | None:
        try:
            return len(get_songs(pl))
        except Exception:
            return None
