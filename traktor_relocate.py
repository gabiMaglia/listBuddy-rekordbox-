"""
traktor_relocate.py
--------------------
Motor de "relocate" para F-07 (ADR-001): repara links rotos en playlists de
Traktor buscando el archivo por nombre en una carpeta/disco indicado por el
usuario, y sincroniza COLLECTION <-> PLAYLISTS en el NML.

Envuelve traktor_db.py (no lo modifica); no toca rekordbox_export.py.
Corre en un QThread (RelocateWorker) — nunca en el hilo de UI, igual que
ExportWorker/PreviewWorker.

Decisiones (ver ADR-001 en engram/02_architecture.md, no rediseñar):
  1. Backup del NML antes de cualquier escritura (retención N=10).
  2. Escritura atómica: todo se acumula en memoria sobre el ElementTree y se
     serializa UNA sola vez a .tmp + fsync + os.replace.
  3. Matching: nombre de archivo exacto (case-insensitive) vía un índice
     basename -> [paths] construido una sola vez. >1 candidato => decisión
     del usuario (modal) por default; el fuzzy score NUNCA autoelige salvo
     que el usuario tilde el checkbox opt-in "auto_resolve" (Addendum
     ADR-001, 2026-07-24 / T-003), en cuyo caso se aplica candidates[0]
     (ya ordenado por score) sin modal.
  4. Sync: índice inverso old_key -> [PRIMARYKEY elements], reescritos todos
     los que matcheen al reparar una ENTRY.
  5. R-03: Traktor debe estar cerrado (is_traktor_running()).
"""
from __future__ import annotations

import os
import platform
import shutil
import subprocess
import threading
from dataclasses import dataclass, field
from datetime import datetime
from difflib import SequenceMatcher
from pathlib import Path
from xml.etree import ElementTree as ET

from PyQt6.QtCore import QThread, pyqtSignal

from traktor_db import _location_to_key, _location_to_path, path_to_location

_BACKUP_DIR_NAME = "listBuddy_backups"
_BACKUP_RETENTION = 10


# ─────────────────────────────────────────────── Data classes ────────────

@dataclass
class BrokenTrack:
    """Un ENTRY de COLLECTION cuyo LOCATION no resuelve a un archivo existente."""
    title: str
    artist: str
    original_key: str
    original_path: Path


@dataclass
class Candidate:
    """Un archivo candidato para reparar un BrokenTrack."""
    path: Path
    size: int
    matched_title: str | None
    matched_artist: str | None
    score: float


@dataclass
class RelocateRequest:
    """Payload de RelocateWorker.ask_user — contrato del modal (ADR-001)."""
    broken: BrokenTrack
    candidates: list[Candidate] = field(default_factory=list)


# ─────────────────────────────────────────────── R-03: proceso ───────────

def is_traktor_running() -> bool:
    """
    Detecta si Traktor está corriendo (chequeo de proceso por nombre).
    No es un lock de OS (ver R-03) — Traktor reescribe el NML entero al
    salir/guardar, así que si está abierto pisaría nuestras reparaciones.

    Si la detección falla (herramienta no disponible, timeout, permisos),
    asumimos que NO está corriendo en vez de bloquear el flujo entero:
    es un fallback conservador de UX, no de seguridad de datos — el riesgo
    real (last-writer-wins) solo se materializa si el usuario efectivamente
    tiene Traktor abierto y no lo cierra pese al aviso.
    """
    system = platform.system()
    try:
        if system == "Windows":
            flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
            out = subprocess.run(
                ["tasklist", "/FI", "IMAGENAME eq Traktor.exe"],
                capture_output=True, text=True, timeout=5,
                creationflags=flags,
            )
            return "traktor.exe" in out.stdout.lower()
        elif system == "Darwin":
            out = subprocess.run(
                ["pgrep", "-ix", "Traktor"],
                capture_output=True, text=True, timeout=5,
            )
            return out.returncode == 0 and bool(out.stdout.strip())
        else:
            return False
    except (OSError, subprocess.SubprocessError):
        return False


# ─────────────────────────────────────────────── Broken tracks ───────────

def find_broken_entries(collection_el: ET.Element) -> list[tuple[ET.Element, BrokenTrack]]:
    """
    Recorre <COLLECTION><ENTRY> y devuelve los que no resuelven a un archivo
    existente. Reutiliza el mismo criterio "en rojo" que preview_worker.py
    (Path(...).exists()). Usa `_location_to_path(volume, dir_attr, file_attr)`
    (T-004: honra VOLUME en Windows) — antes de ese fix esta función heredaba
    el bug de detectar como "roto" cualquier archivo en un disco distinto al
    de la unidad del proceso; ya corregido, no rediseñar el chequeo en sí.
    """
    broken: list[tuple[ET.Element, BrokenTrack]] = []
    for entry in collection_el.findall("ENTRY"):
        loc = entry.find("LOCATION")
        if loc is None:
            continue
        volume = loc.get("VOLUME", "")
        dir_attr = loc.get("DIR", "")
        file_attr = loc.get("FILE", "")
        file_path = _location_to_path(volume, dir_attr, file_attr)
        if file_path.exists():
            continue
        original_key = _location_to_key(volume, dir_attr, file_attr)
        title = entry.get("TITLE", "") or file_attr
        artist = entry.get("ARTIST", "") or ""
        broken.append((
            entry,
            BrokenTrack(
                title=title, artist=artist,
                original_key=original_key, original_path=file_path,
            ),
        ))
    return broken


# ─────────────────────────────────────────────── Disk index ──────────────

def build_basename_index(search_root: Path) -> dict[str, list[Path]]:
    """
    Índice {basename.lower(): [paths]} construido UNA sola vez por corrida
    (evita re-escanear disco por pista; un scan completo es caro en
    discos USB/red). Salta la carpeta de backups propia para no ofrecerla
    como candidato.
    """
    index: dict[str, list[Path]] = {}

    def _on_error(_exc: OSError) -> None:
        pass  # directorios sin permiso: se ignoran, no abortan el índice

    for root, dirs, files in os.walk(search_root, onerror=_on_error):
        dirs[:] = [d for d in dirs if d != _BACKUP_DIR_NAME]
        for name in files:
            index.setdefault(name.lower(), []).append(Path(root) / name)
    return index


# ─────────────────────────────────────────────── Matching ────────────────

def _guess_title_artist(stem: str) -> tuple[str | None, str | None]:
    """
    Best-effort: intenta partir 'Artist - Title' (convención de nombre que
    esta misma app usa al exportar, ver worker.py::_safe_filename). Solo se
    usa para anotar/rankear candidatos en el modal — nunca decide sola.
    """
    parts = stem.split(" - ", 1)
    if len(parts) == 2:
        return parts[1].strip() or None, parts[0].strip() or None
    return None, None


def _sim(a: str | None, b: str | None) -> float:
    if not a or not b:
        return 0.0
    return SequenceMatcher(None, a.lower(), b.lower()).ratio()


def _fuzzy_score(
    track: BrokenTrack,
    path: Path,
    matched_title: str | None,
    matched_artist: str | None,
) -> float:
    expected = f"{track.artist} - {track.title}".strip(" -")
    scores = [_sim(path.stem, expected)]
    if matched_title:
        scores.append(_sim(matched_title, track.title))
    if matched_artist:
        scores.append(_sim(matched_artist, track.artist))
    return max(scores) if scores else 0.0


def find_candidates(
    track: BrokenTrack,
    index: dict[str, list[Path]],
) -> list[Candidate]:
    """
    Matching primario: nombre de archivo EXACTO (case-insensitive), contra
    el índice ya construido. El fuzzy por título/artista NO decide — solo
    rankea los candidatos que ya matchearon por nombre exacto (ADR-001,
    punto 3): 0 matches = sin resolver, 1 = se aplica, >1 = modal.
    """
    key = track.original_path.name.lower()
    paths = index.get(key, [])
    candidates: list[Candidate] = []
    for p in paths:
        try:
            size = p.stat().st_size
        except OSError:
            size = 0
        m_title, m_artist = _guess_title_artist(p.stem)
        score = _fuzzy_score(track, p, m_title, m_artist)
        candidates.append(Candidate(
            path=p, size=size,
            matched_title=m_title, matched_artist=m_artist, score=score,
        ))
    candidates.sort(key=lambda c: c.score, reverse=True)
    return candidates


# ─────────────────────────────────────────────── Sync PLAYLISTS ──────────

def build_reverse_key_index(playlists_el: ET.Element) -> dict[str, list[ET.Element]]:
    """
    Índice inverso old_key -> [elementos PRIMARYKEY], construido UNA sola
    vez antes de aplicar el lote (ADR-001, punto 4): una pista puede estar
    en varias playlists, cada reparación se vuelve O(1) sobre sus refs.
    """
    index: dict[str, list[ET.Element]] = {}
    for pk in playlists_el.iter("PRIMARYKEY"):
        key = pk.get("KEY")
        if key:
            index.setdefault(key, []).append(pk)
    return index


def apply_relocation(
    entry: ET.Element,
    chosen_path: Path,
    key_index: dict[str, list[ET.Element]],
) -> str:
    """
    Aplica la reparación sobre el árbol en memoria (no escribe a disco):
    Fase A (COLLECTION) — reescribe LOCATION VOLUME/DIR/FILE de la ENTRY.
    Fase B (PLAYLISTS)  — reescribe KEY de cada PRIMARYKEY que apuntaba al
                          old_key (FILE puede cambiar de basename; new_key
                          se recomputa entero, no se asume estable).
    Devuelve el new_key aplicado.
    """
    loc = entry.find("LOCATION")
    if loc is None:
        raise ValueError("ENTRY sin LOCATION — no se puede reparar.")

    old_key = _location_to_key(
        loc.get("VOLUME", ""), loc.get("DIR", ""), loc.get("FILE", ""),
    )
    volume, dir_attr, file_attr = path_to_location(chosen_path)
    loc.set("VOLUME", volume)
    loc.set("DIR", dir_attr)
    loc.set("FILE", file_attr)
    new_key = _location_to_key(volume, dir_attr, file_attr)

    for pk in key_index.get(old_key, []):
        pk.set("KEY", new_key)

    return new_key


# ─────────────────────────────────────────────── Backup ──────────────────

def backup_collection(nml_path: Path) -> Path:
    """
    Copia el NML a <carpeta>/listBuddy_backups/collection.TIMESTAMP.nml
    antes del primer write de la sesión. Retiene las últimas N=10 y poda el
    resto. Si falla (permisos, disco lleno) propaga OSError — el llamador
    debe abortar sin escribir (ADR-001, punto 1).
    """
    backups_dir = nml_path.parent / _BACKUP_DIR_NAME
    backups_dir.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d-%H%M%S")
    dest = backups_dir / f"collection.{ts}.nml"
    shutil.copy2(nml_path, dest)
    _prune_backups(backups_dir)
    return dest


def _prune_backups(backups_dir: Path, keep: int = _BACKUP_RETENTION) -> None:
    backups = sorted(
        backups_dir.glob("collection.*.nml"),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )
    for old in backups[keep:]:
        try:
            old.unlink()
        except OSError:
            pass  # poda es best-effort, no debe abortar la sesión


# ─────────────────────────────────────────────── Escritura atómica ───────

def write_atomic(tree: ET.ElementTree, nml_path: Path) -> None:
    """
    Serializa el árbol completo UNA sola vez a un .tmp en la MISMA carpeta,
    flush + fsync, y os.replace (atómico en el mismo filesystem tanto en
    Windows como en macOS). Si algo falla, el .tmp se descarta y el
    original queda intacto (ADR-001, punto 2).
    """
    tmp_path = nml_path.parent / (nml_path.name + ".tmp")
    try:
        with open(tmp_path, "wb") as f:
            tree.write(f, encoding="UTF-8", xml_declaration=True)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp_path, nml_path)
    except OSError:
        try:
            tmp_path.unlink(missing_ok=True)
        except OSError:
            pass
        raise


# ─────────────────────────────────────────────── QThread worker ──────────

class RelocateWorker(QThread):
    log         = pyqtSignal(str)
    progress    = pyqtSignal(int, int)          # (hechas, total)
    ask_user    = pyqtSignal(object)            # RelocateRequest — bloquea el worker
    finished_ok = pyqtSignal(int, int, int, str)  # (reparadas, salteadas, sin_match, status)
    # status: "ok" | "cancelled" | "error"

    def __init__(
        self, nml_path: Path, search_root: Path, auto_resolve: bool = False,
    ) -> None:
        super().__init__()
        self._nml_path = nml_path
        self._search_root = search_root
        self._auto_resolve = auto_resolve
        self._answer_event = threading.Event()
        self._answer: Path | None = None

    def provide_answer(self, choice: Path | None) -> None:
        """
        Slot llamado desde el hilo de UI con la decisión del modal.
        `choice` es un Path elegido, o None = SKIP (ADR-001, contrato del
        modal: sin default silencioso; cerrar el modal sin elegir = SKIP).
        """
        self._answer = choice
        self._answer_event.set()

    def run(self) -> None:
        # R-03: chequeo de proceso en el hilo del worker, no en el de UI —
        # subprocess.run() (tasklist/pgrep) no es trabajo garantizadamente
        # liviano; nunca debe correr en el hilo de eventos de Qt.
        if is_traktor_running():
            self.log.emit(
                "✗  Traktor está abierto. Cerralo antes de reparar enlaces: "
                "reescribe collection.nml entero al salir/guardar y pisaría "
                "las reparaciones (last-writer-wins)."
            )
            self.finished_ok.emit(0, 0, 0, "blocked")
            return

        try:
            tree = ET.parse(str(self._nml_path))
        except ET.ParseError as e:
            self.log.emit(f"✗  No se pudo leer la librería de Traktor.\n   Detalle: {e}")
            self.finished_ok.emit(0, 0, 0, "error")
            return

        root = tree.getroot()
        collection_el = root.find("COLLECTION")
        playlists_el = root.find("PLAYLISTS")
        if collection_el is None:
            self.log.emit("✗  El NML no tiene sección COLLECTION.")
            self.finished_ok.emit(0, 0, 0, "error")
            return

        broken = find_broken_entries(collection_el)
        total = len(broken)
        self.log.emit(f"🔍  {total} enlace(s) roto(s) en la colección.")
        if total == 0:
            self.finished_ok.emit(0, 0, 0, "ok")
            return

        self.log.emit(f"📂  Indexando archivos en: {self._search_root}")
        index = build_basename_index(self._search_root)
        indexed_count = sum(len(v) for v in index.values())
        self.log.emit(f"   {indexed_count} archivo(s) indexado(s).")

        key_index = build_reverse_key_index(playlists_el) if playlists_el is not None else {}

        repaired = skipped = unresolved = 0
        for i, (entry, broken_track) in enumerate(broken, start=1):
            if self.isInterruptionRequested():
                self.log.emit("\n⏹  Relocate cancelado — NML intacto, nada se escribió.")
                self.finished_ok.emit(repaired, skipped, unresolved, "cancelled")
                return

            self.progress.emit(i, total)
            label = broken_track.title or broken_track.original_path.name

            candidates = find_candidates(broken_track, index)
            if not candidates:
                unresolved += 1
                self.log.emit(f"   ✗  Sin coincidencias: {label}")
                continue

            auto_resolved = False
            if len(candidates) == 1:
                chosen: Path | None = candidates[0].path
            elif self._auto_resolve:
                # Addendum ADR-001 (2026-07-24): opt-in, checkbox OFF por
                # default no pasa por acá. candidates[0] ya viene ordenado
                # por _fuzzy_score descendente (find_candidates) — no es
                # orden de carpeta al azar. Sin modal, sin ask_user_event.
                chosen = candidates[0].path
                auto_resolved = True
            else:
                self._answer_event.clear()
                self.ask_user.emit(RelocateRequest(broken=broken_track, candidates=candidates))
                self._answer_event.wait()
                chosen = self._answer

            if chosen is None:
                skipped += 1
                self.log.emit(f"   ⏭  Salteado: {label}")
                continue

            apply_relocation(entry, chosen, key_index)
            repaired += 1
            if auto_resolved:
                self.log.emit(f"   ✓  Reparado (auto): {label} → {chosen}")
            else:
                self.log.emit(f"   ✓  Reparado: {label} → {chosen}")

        if repaired == 0:
            self.log.emit("\nSin cambios para escribir (0 reparaciones aplicadas).")
            self.finished_ok.emit(repaired, skipped, unresolved, "ok")
            return

        try:
            backup_path = backup_collection(self._nml_path)
            self.log.emit(f"💾  Backup creado: {backup_path}")
        except OSError as e:
            self.log.emit(
                f"✗  No se pudo crear el backup — abortando sin escribir.\n   Detalle: {e}"
            )
            self.finished_ok.emit(0, 0, 0, "error")
            return

        try:
            write_atomic(tree, self._nml_path)
        except OSError as e:
            self.log.emit(f"✗  Error al escribir la colección.\n   Detalle: {e}")
            self.finished_ok.emit(0, 0, 0, "error")
            return

        self.log.emit(
            f"\n✓  {repaired} reparada(s) · {skipped} salteada(s) · {unresolved} sin coincidencias."
        )
        self.finished_ok.emit(repaired, skipped, unresolved, "ok")
