"""
worker.py
---------
QThread que ejecuta la exportación sin congelar la UI.
"""
from __future__ import annotations

import logging
import os
import shutil
import sys
import unicodedata
from pathlib import Path

from PySide6.QtCore import QThread, Signal

from rekordbox_export import get_songs as _rb_get_songs
from rekordbox_export import get_content, get_artist, resolve_path, sanitize
from db import order_playlist_songs

_log = logging.getLogger("listBuddy")


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


# Tope del nombre sin extensión, en BYTES UTF-8. ext4/FAT/exFAT limitan el
# nombre a 255 bytes; APFS y NTFS a 255 unidades UTF-16 (según conocimiento, no
# verificado hoy). 200 bytes deja lugar a la extensión y al «.part» temporal y
# cubre las tres (T-093, TEC-21).
_MAX_STEM = 200
_ELLIPSIS = "\u2026"


# Windows clásico corta en MAX_PATH=260; se avisa con margen (T-093).
_WIN_PATH_WARN = 240


def _long_path_warning(dest: Path) -> str | None:
    if sys.platform == "win32" and len(str(dest)) > _WIN_PATH_WARN:
        return (
            f"   ⚠  Ruta muy larga ({len(str(dest))} caracteres): Windows puede rechazarla "
            f"por el límite de 260. Elegí una carpeta de destino más corta."
        )
    return None


def _nbytes(text: str) -> int:
    return len(text.encode("utf-8"))


def _is_extender(ch: str) -> bool:
    """Carácter que se pega al anterior dentro de un mismo grafema."""
    cp = ord(ch)
    return (
        unicodedata.combining(ch) != 0
        or unicodedata.category(ch) in ("Mn", "Me")
        or cp in (0x200D, 0xFE0E, 0xFE0F)
        or 0x1F3FB <= cp <= 0x1F3FF          # modificadores de tono de piel
        or 0xE0020 <= cp <= 0xE007F          # etiquetas (banderas de subregión)
    )


def _is_regional(ch: str) -> bool:
    return 0x1F1E6 <= ord(ch) <= 0x1F1FF


def _splits_cluster(text: str, i: int) -> bool:
    """True si cortar en `i` partiría un grafema (aproximación de UAX #29:
    `unicodedata` no trae segmentación; cubre combinantes, ZWJ, selectores de
    variación, tonos y pares de indicadores regionales)."""
    if i <= 0 or i >= len(text):
        return False
    prev, cur = text[i - 1], text[i]
    if _is_extender(cur) or prev == "\u200d":
        return True
    if _is_regional(prev) and _is_regional(cur):
        run = 0
        j = i - 1
        while j >= 0 and _is_regional(text[j]):
            run += 1
            j -= 1
        return run % 2 == 1
    return False


def _truncate_bytes(text: str, max_bytes: int) -> str:
    """Recorta `text` a `max_bytes` UTF-8 agregando «…», sin partir un grafema."""
    if _nbytes(text) <= max_bytes:
        return text
    room = max_bytes - _nbytes(_ELLIPSIS)
    cut, used = 0, 0
    for ch in text:
        size = _nbytes(ch)
        if used + size > room:
            break
        used += size
        cut += 1
    while cut > 0 and _splits_cluster(text, cut):
        cut -= 1
    return text[:cut] + _ELLIPSIS


def _safe_filename(prefix: str, artist: str, title: str, suffix: str) -> str:
    title = title or "Sin título"
    parts = [prefix] + ([artist] if artist else []) + [title]
    stem = " - ".join(parts)
    if _nbytes(stem) <= _MAX_STEM:
        return stem + suffix

    fixed = _nbytes(prefix) + _nbytes(" - ") + (_nbytes(artist) + _nbytes(" - ") if artist else 0)
    budget = _MAX_STEM - fixed
    if budget >= 8:
        title = _truncate_bytes(title, budget)
    else:
        half = (_MAX_STEM - _nbytes(prefix) - _nbytes(" - ") * 2) // 2
        artist = _truncate_bytes(artist, half)
        title = _truncate_bytes(title, half)

    parts = [prefix] + ([artist] if artist else []) + [title]
    return " - ".join(parts) + suffix


_CHUNK = 1024 * 1024


class _CopyInterrupted(Exception):
    """El usuario canceló (o la app se cierra) en medio de la copia de un archivo."""


def _copy_stream(fsrc, fdst, should_stop) -> None:
    """Copia por bloques para poder cortar a mitad de un archivo grande."""
    while True:
        if should_stop():
            raise _CopyInterrupted
        buf = fsrc.read(_CHUNK)
        if not buf:
            return
        fdst.write(buf)


def _copy_atomic(src: Path, dest: Path, should_stop) -> None:
    """Copia a `<dest>.part` y recién al final lo renombra al nombre definitivo.

    Si algo falla a mitad (disco lleno, USB desconectado, cancelación) el
    nombre final nunca queda con un archivo truncado que el reintento daría
    por bueno. Modo `xb` (O_EXCL): no escribe a través de un symlink plantado.
    """
    part = dest.with_name(dest.name + ".part")
    try:
        with open(src, "rb") as fsrc, open(part, "xb") as fdst:
            _copy_stream(fsrc, fdst, should_stop)
        shutil.copystat(src, part)
        os.replace(part, dest)
    except BaseException:
        try:
            part.unlink()
        except OSError:
            pass
        raise


def _remove_orphan_parts(folder: Path, names: set[str]) -> None:
    """Borra los `.part` que dejó una copia anterior cortada de golpe (kill, USB).

    Solo los que este export va a volver a escribir: un `.part` ajeno (descarga a medias,
    otra app) en la misma carpeta no se toca.
    """
    for name in names:
        try:
            (folder / name).unlink()
        except OSError:
            pass


class ExportWorker(QThread):
    log         = Signal(str)
    progress    = Signal(int, int)        # (hechas, total)
    finished_ok = Signal(int, int, int, str)  # (copiadas, faltantes, saltadas, status)
    # status: "ok" | "cancelled" | "error"

    def __init__(self, playlists: list, output_root: Path) -> None:
        super().__init__()
        self._playlists = playlists
        self._output_root = output_root

    def _report_unreadable(self, pl, exc: Exception) -> None:
        self.log.emit(f"⚠ No se pudo leer la playlist {getattr(pl, 'Name', '?')}: {exc}")

    def run(self) -> None:
        copied_total = missing_total = skipped_total = 0
        missing_tracks: list[str] = []
        # T-008: agrupadas por carpeta de destino además de la lista plana de
        # arriba (que se mantiene igual para el log de la UI), para poder
        # escribir un "_no_exportados.txt" por playlist con las fallas de
        # esa playlist únicamente.
        missing_by_dest: dict[Path, list[str]] = {}

        # ── Pre-build: una sola query lazy por playlist ───────────────────
        playlist_songs: list[tuple] = []
        for pl in self._playlists:
            songs = _get_songs_list(pl, self._report_unreadable)
            if songs:
                playlist_songs.append((pl, order_playlist_songs(songs)))

        total_songs = sum(len(s) for _, s in playlist_songs)
        self.progress.emit(0, max(total_songs, 1))

        # ── Chequeo de espacio en disco ───────────────────────────────────
        folder_names = _unique_folder_names([pl.Name for pl, _ in playlist_songs])
        try:
            total_bytes = _estimate_size(playlist_songs, self._output_root, folder_names)
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
        for (pl, songs), folder in zip(playlist_songs, folder_names):
            self.log.emit(f"▶  {pl.Name}")
            dest_dir = self._output_root / folder
            if not _is_inside(dest_dir, self._output_root):
                self.log.emit(f"✗  Nombre de playlist no válido, no se exporta: {pl.Name}")
                _log.error("Export: %s resuelve fuera de %s", dest_dir, self._output_root)
                self.finished_ok.emit(copied_total, missing_total, skipped_total, "error")
                return

            sorted_songs = songs   # ya ordenadas al armar playlist_songs

            try:
                dest_dir.mkdir(parents=True, exist_ok=True)
            except OSError as e:
                # Disco de destino desconectado (/Volumes/<disco> desmontado),
                # sin permisos o solo lectura: se corta acá con un mensaje claro.
                self.log.emit(
                    f"✗  No se pudo crear la carpeta de destino:\n   {dest_dir}\n"
                    "   ¿Está conectado el disco y tenés permiso para escribir ahí?"
                )
                _log.error("Export: no se pudo crear %s: %s", dest_dir, e)
                self.finished_ok.emit(copied_total, missing_total, skipped_total, "error")
                return
            pad = len(str(len(sorted_songs)))
            _remove_orphan_parts(dest_dir, _part_names(sorted_songs, dest_dir, pad))

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

                if getattr(content, "streaming", False):
                    label = getattr(content, "Title", None) or "desconocido"
                    self.log.emit(f"   ♫  Es de streaming, no es un archivo: {label}")
                    missing_tracks.append(f"{pl.Name} → {label} (streaming)")
                    missing_by_dest.setdefault(dest_dir, []).append(
                        f"{label} — pista de streaming (no es un archivo que se pueda copiar)"
                    )
                    missing_total += 1
                    continue

                if src is None:
                    label = getattr(content, "Title", None) or raw_path or "desconocido"
                    self.log.emit(f"   ⚠  No se encontró: {label}")
                    missing_tracks.append(f"{pl.Name} → {label}")
                    missing_by_dest.setdefault(dest_dir, []).append(
                        f"{label} — no encontrado en disco (ruta original: {raw_path or 'desconocida'})"
                    )
                    missing_total += 1
                    continue

                dest = _planned_dest(dest_dir, idx, pad, content, src)
                long_warning = _long_path_warning(dest)
                if long_warning:
                    self.log.emit(long_warning)

                if _is_complete_copy(dest, src):
                    self.log.emit(f"   ⏭  Ya existe: {dest.name}")
                    skipped_total += 1
                else:
                    try:
                        _copy_atomic(src, dest, self.isInterruptionRequested)
                        self.log.emit(f"   ✓  {dest.name}")
                        copied_total += 1
                    except _CopyInterrupted:
                        self.log.emit("\n⏹  Exportación cancelada.")
                        self.finished_ok.emit(copied_total, missing_total, skipped_total, "cancelled")
                        return
                    except OSError as e:
                        if e.errno == 28:  # ENOSPC — disco lleno
                            self.log.emit(f"   ✗  Disco lleno al copiar {dest.name}")
                            self.log.emit("      Liberá espacio e intentá de nuevo.")
                            self.finished_ok.emit(copied_total, missing_total, skipped_total, "error")
                            return
                        self.log.emit(f"   ✗  Error copiando {dest.name}: {e}")
                        missing_tracks.append(f"{pl.Name} → {dest.name} (error de copia)")
                        missing_by_dest.setdefault(dest_dir, []).append(
                            f"{dest.name} — error de copia: {e}"
                        )
                        missing_total += 1
                    except Exception as e:
                        self.log.emit(f"   ✗  Error copiando {dest.name}: {e}")
                        missing_tracks.append(f"{pl.Name} → {dest.name} (error de copia)")
                        missing_by_dest.setdefault(dest_dir, []).append(
                            f"{dest.name} — error de copia: {e}"
                        )
                        missing_total += 1

        if missing_tracks:
            self.log.emit("\n─── Tracks no encontradas ───")
            for t in missing_tracks:
                self.log.emit(f"  ✗  {t}")

        # T-008: un "_no_exportados.txt" por playlist con fallas, dentro de
        # su propia dest_dir. Guion bajo a propósito para no mezclarse con
        # el naming numerado de los tracks ("001 - Artist - Title.mp3").
        # Solo se crea si esa playlist tuvo >=1 falla — no ensuciar carpetas
        # limpias. No afecta copied_total/missing_total/skipped_total.
        for dest_dir, lines in missing_by_dest.items():
            try:
                report_path = dest_dir / "_no_exportados.txt"
                if report_path.is_symlink():
                    self.log.emit(f"   ⚠  No se escribió _no_exportados.txt en {dest_dir}: es un acceso directo")
                    continue
                report_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
            except OSError as e:
                self.log.emit(f"   ⚠  No se pudo escribir _no_exportados.txt en {dest_dir}: {e}")

        self.finished_ok.emit(copied_total, missing_total, skipped_total, "ok")


# ── Helpers ───────────────────────────────────────────────────────────────

def _is_inside(path: Path, root: Path) -> bool:
    try:
        return path.resolve().is_relative_to(root.resolve())
    except (OSError, RuntimeError):
        return False


def _unique_folder_names(names: list[str]) -> list[str]:
    """Una carpeta por playlist: si dos colisionan (mismo nombre, otra carpeta de
    Rekordbox) la segunda en adelante lleva « (2)», « (3)»…

    Se compara sin distinguir mayúsculas porque APFS/NTFS tratan igual
    «Mix» y «mix»; si no, las dos pisarían la misma carpeta.
    """
    taken: set[str] = set()
    result: list[str] = []
    for name in names:
        base = sanitize(name) or "playlist"
        candidate, n = base, 1
        while candidate.casefold() in taken:
            n += 1
            candidate = f"{base} ({n})"
        taken.add(candidate.casefold())
        result.append(candidate)
    return result


def _is_complete_copy(dest: Path, src: Path) -> bool:
    """«Ya existe» solo si el archivo está y pesa lo mismo que el origen.

    Un symlink (incluso colgante) en el destino cuenta como existente: no se
    escribe a través de él (T-088, SEC-03).
    """
    if dest.is_symlink():
        return True
    try:
        return dest.stat().st_size == src.stat().st_size
    except OSError:
        return False


def _get_songs_list(pl, on_error=None) -> list:
    """Pistas de la playlist; si no se pueden leer, se loguea y se avisa (no desaparece en silencio)."""
    try:
        return list(get_songs(pl))
    except Exception as e:
        _log.exception("Export: no se pudo leer la playlist %s", getattr(pl, "Name", "?"))
        if on_error is not None:
            on_error(pl, e)
        return []


def _planned_dest(dest_dir: Path, idx: int, pad: int, content, src: Path) -> Path:
    """Ruta final de una pista en el destino (la usan el export y la estimación)."""
    artist = sanitize(get_artist(content))
    title = sanitize(getattr(content, "Title", None) or "") or "Sin título"
    return dest_dir / _safe_filename(str(idx).zfill(pad), artist, title, src.suffix)


def _part_names(sorted_songs: list, dest_dir: Path, pad: int) -> set[str]:
    """Nombres `<archivo>.part` que esta playlist va a crear al copiar."""
    names: set[str] = set()
    for idx, song in enumerate(sorted_songs, start=1):
        content = get_content(song)
        src = resolve_path(getattr(content, "FolderPath", None) if content else None)
        if src:
            names.add(_planned_dest(dest_dir, idx, pad, content, src).name + ".part")
    return names


def _estimate_size(playlist_songs: list[tuple], output_root: Path, folder_names: list[str]) -> int:
    """Bytes que faltan copiar: fuentes que existen, menos las que ya están completas en destino
    (misma regla de «Ya existe»), para que un re-export incremental no pida espacio de más."""
    total = 0
    for (_, songs), folder in zip(playlist_songs, folder_names):
        pad = len(str(len(songs)))
        for idx, song in enumerate(songs, start=1):
            content = get_content(song)
            raw = getattr(content, "FolderPath", None) if content else None
            src = resolve_path(raw)
            if not src:
                continue
            if _is_complete_copy(_planned_dest(output_root / folder, idx, pad, content, src), src):
                continue
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
