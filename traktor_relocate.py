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

T-017 (D-05): el orquestador del loop de resolución (indexar disco, decidir
0/1/N candidatos, ask_user + espera, cancelación, progreso, log) vivía acá
duplicado con rekordbox_relocate.py — se extrajo a
`relocate_core.BaseRelocateWorker` (refactor puro, sin cambio de
comportamiento observable). `RelocateWorker` ahora solo implementa lo
específico de Traktor: chequeo R-03, parseo/escritura del NML, encontrar
los rotos y aplicar UNA reparación (mutar el ElementTree + sync de
PLAYLISTS). `Candidate`/`RelocateRequest`/`build_basename_index`/
`find_candidates` también se movieron a relocate_core.py (evita el import
circular que resultaría de dejarlos acá mientras este módulo pasa a heredar
de esa base) y se re-exportan acá tal cual, sin cambio de lógica, para no
romper imports existentes (tests/test_traktor_relocate.py,
rekordbox_relocate.py).
"""
from __future__ import annotations

import logging
import os
import platform
import shutil
import subprocess
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from xml.etree import ElementTree as ET

from relocate_core import (
    BaseRelocateWorker,
    Candidate,
    RelocateRequest,
    build_basename_index,
    check_disk_space_for_backup,
    find_candidates,
)
from traktor_db import (
    _WINDOWS_DRIVE_RE,
    _location_to_key,
    _location_to_path,
    path_to_location,
)

__all__ = [
    "BrokenTrack",
    "Candidate",
    "RelocateRequest",
    "RelocateWorker",
    "apply_relocation",
    "backup_collection",
    "build_basename_index",
    "build_reverse_key_index",
    "find_broken_entries",
    "find_candidates",
    "is_traktor_running",
    "write_atomic",
]

_BACKUP_DIR_NAME = "listBuddy_backups"
_BACKUP_RETENTION = 10

# Logger al archivo rotativo (app_logging.py). Los self.log.emit() van al panel
# de la UI, que se oculta al terminar el relocate; el log de archivo es lo único
# que sobrevive para diagnosticar un relocate fallido en producción.
_log = logging.getLogger("listBuddy")


# ─────────────────────────────────────────────── Data classes ────────────

@dataclass
class BrokenTrack:
    """Un ENTRY de COLLECTION cuyo LOCATION no resuelve a un archivo existente."""
    title: str
    artist: str
    original_key: str
    original_path: Path


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

_DETECT_PROGRESS_EVERY = 250  # T-020: mismo throttle que build_basename_index (T-007)


def find_broken_entries(
    collection_el: ET.Element,
    should_stop: Callable[[], bool] | None = None,
    on_progress: Callable[[int, int], None] | None = None,
    progress_every: int = _DETECT_PROGRESS_EVERY,
) -> list[tuple[ET.Element, BrokenTrack]]:
    """
    Recorre <COLLECTION><ENTRY> y devuelve los que no resuelven a un archivo
    existente. Reutiliza el mismo criterio "en rojo" que preview_worker.py
    (Path(...).exists()). Usa `_location_to_path(volume, dir_attr, file_attr)`
    (T-004: honra VOLUME en Windows) — antes de ese fix esta función heredaba
    el bug de detectar como "roto" cualquier archivo en un disco distinto al
    de la unidad del proceso; ya corregido, no rediseñar el chequeo en sí.

    T-020 (I-2/I-3, engram/07_production_readiness.md): T-007 hizo cancelable
    e incremental al walk de disco (`build_basename_index`), pero esta fase
    -anterior en el flujo- había quedado afuera. Acá lo caro NO es recorrer
    la lista de ENTRY (ya está en memoria, es barata) sino el `.exists()` por
    track: si LOCATION apunta a un disco de red o USB desconectado, cada
    `.exists()` puede tardar decenas de segundos (timeout del SO). Por eso
    `should_stop` se chequea ANTES de cada `.exists()` (cada ENTRY, no cada
    `progress_every`) — es el equivalente acá a lo que build_basename_index
    hace por carpeta visitada: chequear justo antes de la unidad de trabajo
    cara, no después de acumular un lote. Chequear cada `progress_every`
    tracks dejaría la cancelación esperando potencialmente horas si hay
    cientos de rutas muertas encadenadas, que es exactamente el escenario que
    este ticket ataca. `on_progress` sí se throttlea cada `progress_every`
    (mismo valor por default que build_basename_index) para no saturar la UI
    con señales — a diferencia del walk, acá el total SÍ se conoce de
    entrada (cantidad de ENTRY), así que se reporta como (hechos, total) en
    vez de un conteo indeterminado.
    """
    broken: list[tuple[ET.Element, BrokenTrack]] = []
    entries = collection_el.findall("ENTRY")
    total = len(entries)
    for i, entry in enumerate(entries, start=1):
        if should_stop is not None and should_stop():
            break
        loc = entry.find("LOCATION")
        if loc is not None:
            volume = loc.get("VOLUME", "")
            dir_attr = loc.get("DIR", "")
            file_attr = loc.get("FILE", "")
            file_path = _location_to_path(volume, dir_attr, file_attr)
            if not file_path.exists():
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
        if on_progress is not None and i % progress_every == 0:
            on_progress(i, total)
    return broken


# ─────────────────────────────────────────────── Sync PLAYLISTS ──────────

def build_reverse_key_index(playlists_el: ET.Element) -> dict[str, list[ET.Element]]:
    """
    Índice inverso old_key -> [elementos PRIMARYKEY], construido UNA sola
    vez antes de aplicar el lote (ADR-001, punto 4): una pista puede estar
    en varias playlists, cada reparación se vuelve O(1) sobre sus refs.

    T-022 (hallazgo adversarial, engram/07_production_readiness.md): este
    dict se queda desactualizado a mitad del loop si dos ENTRY DISTINTAS de
    COLLECTION comparten el mismo LOCATION original (mismo old_key) — pasa
    en librerías fusionadas/duplicadas por reimportación. `apply_relocation`
    CONSUME (`dict.pop`) el bucket de cada old_key al usarlo en vez de solo
    leerlo (`dict.get`), así que si una segunda ENTRY con el mismo old_key
    se procesa después, encuentra el bucket ya vacío en vez de volver a
    reescribir (y pisar) las PRIMARYKEY que la primera ENTRY ya dejó
    apuntando a su archivo correcto. Confirmado con un test que el bug era
    real antes de este fix — ver
    tests/test_traktor_relocate.py::TestApplyRelocationAliasing.
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

    T-022: `key_index.pop(old_key, [])` en vez de `.get` — CONSUME el
    bucket al usarlo (ver docstring de `build_reverse_key_index`). Evita que
    una segunda ENTRY que comparta el mismo old_key (LOCATION original
    duplicado entre dos pistas) vuelva a reescribir las mismas PRIMARYKEY
    y pise la reparación que la primera ENTRY ya aplicó correctamente.

    T-023 (B-5, criterio 2): en macOS el NML real del PO confirma
    VOLUMEID == VOLUME en las 5764 ENTRY existentes (Macintosh HD/MUSIC/
    NO NAME, todas coincidentes) — se sincroniza VOLUMEID junto con VOLUME
    para no dejar un VOLUMEID viejo apuntando al volumen anterior si la
    reparación mueve la pista a un disco distinto del original. Solo se
    toca para rutas macOS (VOLUME no es una letra de unidad estilo "D:"):
    no hay NML real de Windows disponible para confirmar qué representa
    VOLUMEID ahí (P-3, cero asunciones), y ese write path ya está validado
    en producción (T-002/T-004) sin tocar este atributo — no introducir
    comportamiento nuevo sin evidencia.
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
    if not _WINDOWS_DRIVE_RE.match(volume):
        loc.set("VOLUMEID", volume)
    new_key = _location_to_key(volume, dir_attr, file_attr)

    for pk in key_index.pop(old_key, []):
        pk.set("KEY", new_key)

    return new_key


# ─────────────────────────────────────────────── Backup ──────────────────

def backup_collection(nml_path: Path) -> Path:
    """
    Copia el NML a <carpeta>/listBuddy_backups/collection.TIMESTAMP.nml
    antes del primer write de la sesión. Retiene las últimas N=10 y poda el
    resto. Si falla (permisos, disco lleno) propaga OSError — el llamador
    debe abortar sin escribir (ADR-001, punto 1).

    B-3 (T-018): chequea espacio libre ANTES de copiar
    (`check_disk_space_for_backup`) y, si `shutil.copy2` falla a mitad de
    camino (ej. `ENOSPC`), borra el destino parcial antes de re-lanzar — un
    backup truncado NO puede quedar en `listBuddy_backups/` haciéndose
    pasar por el más reciente (`_prune_backups` lo contaría como válido).
    """
    check_disk_space_for_backup(nml_path)
    backups_dir = nml_path.parent / _BACKUP_DIR_NAME
    backups_dir.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d-%H%M%S")
    dest = backups_dir / f"collection.{ts}.nml"
    try:
        shutil.copy2(nml_path, dest)
    except OSError:
        dest.unlink(missing_ok=True)
        raise
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

class RelocateWorker(BaseRelocateWorker):
    def __init__(
        self, nml_path: Path, search_root: Path, auto_resolve: bool = False,
    ) -> None:
        super().__init__(search_root, auto_resolve=auto_resolve)
        self._nml_path = nml_path
        self._key_index: dict[str, list[ET.Element]] = {}

    # ── Hooks de relocate_core.BaseRelocateWorker ──────────────────────

    def _broken_scope_noun(self) -> str:
        return "colección"

    def _write_target_name(self) -> str:
        return "NML"

    def _engine_name(self) -> str:
        return "Traktor"

    def _label_for(self, broken_track: BrokenTrack) -> str:
        return broken_track.title or broken_track.original_path.name

    def _apply_one(
        self, raw_entry: ET.Element, broken_track: BrokenTrack, chosen: Path,
    ) -> bool:
        # Sync de PLAYLISTS (Fase B, ADR-001 punto 4) — específico de
        # Traktor, no tiene equivalente en Rekordbox (liga por Content.ID).
        apply_relocation(raw_entry, chosen, self._key_index)
        return True

    def run(self) -> None:
        # R-03: chequeo de proceso en el hilo del worker, no en el de UI —
        # subprocess.run() (tasklist/pgrep) no es trabajo garantizadamente
        # liviano; nunca debe correr en el hilo de eventos de Qt.
        _log.info("Relocate Traktor: inicio · nml=%s · search_root=%s · auto=%s",
                  self._nml_path, self._search_root, self._auto_resolve)
        if is_traktor_running():
            self.log.emit(
                "✗  Traktor está abierto. Cerralo antes de reparar enlaces: "
                "reescribe collection.nml entero al salir/guardar y pisaría "
                "las reparaciones (last-writer-wins)."
            )
            _log.warning("Relocate Traktor: bloqueado — Traktor está abierto (R-03).")
            self.finished_ok.emit(0, 0, 0, "blocked")
            return

        try:
            tree = ET.parse(str(self._nml_path))
        except ET.ParseError as e:
            # I-6: nada de texto crudo de excepción en pantalla (acá iba un
            # ET.ParseError tipo "not well-formed (invalid token): line 4212,
            # column 33" — ilegible para un usuario no técnico). El detalle
            # técnico completo queda en el log de archivo (_log.error abajo).
            self.log.emit(
                "✗  No se pudo leer la librería de Traktor — el archivo puede "
                "estar dañado o en un formato inesperado."
            )
            _log.error("Relocate Traktor: NML ilegible (%s): %s", self._nml_path, e)
            self.finished_ok.emit(0, 0, 0, "error")
            return

        root = tree.getroot()
        collection_el = root.find("COLLECTION")
        playlists_el = root.find("PLAYLISTS")
        if collection_el is None:
            self.log.emit("✗  El NML no tiene sección COLLECTION.")
            _log.error("Relocate Traktor: NML sin sección COLLECTION (%s).", self._nml_path)
            self.finished_ok.emit(0, 0, 0, "error")
            return

        # T-020 (I-2/I-3): fase de detección cancelable + con progreso. El
        # log de "N enlace(s) roto(s)" que sigue lo emite _run_resolution
        # apenas arranca — este mensaje previo es a propósito distinto
        # ("Detectando" vs "Indexando archivos en disco…", que es la fase
        # siguiente dentro de _run_resolution) para que quede claro en qué
        # paso está la app si tarda.
        self.log.emit("🔎  Detectando enlaces rotos…")
        broken = find_broken_entries(
            collection_el,
            should_stop=self.isInterruptionRequested,
            on_progress=lambda done, total: self.progress.emit(done, total),
        )
        if self.isInterruptionRequested():
            self._emit_cancelled(0, 0, 0)
            return

        self._key_index = (
            build_reverse_key_index(playlists_el) if playlists_el is not None else {}
        )

        result = self._run_resolution(broken)
        if result is None:
            return
        repaired, skipped, unresolved = result.repaired, result.skipped, result.unresolved

        if repaired == 0:
            self.log.emit("\nSin cambios para escribir (0 reparaciones aplicadas).")
            self.finished_ok.emit(repaired, skipped, unresolved, "ok")
            return

        # I-4: re-chequear que Traktor siga cerrado JUSTO ANTES de escribir.
        # El chequeo de arriba corrió al principio de run() — entre eso y
        # este punto puede haber pasado el indexado de disco entero más
        # minutos/horas de modales de desambiguación (auto_resolve=False es
        # el default). Si el usuario abrió Traktor mientras tanto, escribir
        # ahora sería exactamente el escenario que R-03 quiere evitar
        # (last-writer-wins al cerrar Traktor). Mismo mensaje/status
        # "blocked" que el chequeo inicial — se aborta SIN escribir.
        if is_traktor_running():
            self.log.emit(
                "✗  Traktor está abierto. Cerralo antes de reparar enlaces: "
                "reescribe collection.nml entero al salir/guardar y pisaría "
                "las reparaciones (last-writer-wins)."
            )
            _log.warning(
                "Relocate Traktor: bloqueado en el re-chequeo previo a "
                "escribir (R-03) — %d reparación(es) en memoria descartada(s).",
                repaired,
            )
            self.finished_ok.emit(0, 0, 0, "blocked")
            return

        try:
            backup_path = backup_collection(self._nml_path)
            self.log.emit(f"💾  Backup creado: {backup_path}")
            _log.info("Relocate Traktor: backup creado en %s", backup_path)
        except OSError as e:
            # I-6: sin texto crudo de excepción en pantalla — puede ser un
            # OSError de disco lleno tipo "[Errno 28] No space left on
            # device: ...". El detalle completo queda en el log de archivo.
            self.log.emit(
                "✗  No se pudo crear el backup — abortando sin escribir. "
                "Puede ser falta de espacio en disco o de permisos sobre la carpeta."
            )
            _log.error("Relocate Traktor: backup FALLÓ (%s) — abortado sin escribir: %s",
                       self._nml_path, e, exc_info=True)
            self.finished_ok.emit(0, 0, 0, "error")
            return

        try:
            write_atomic(tree, self._nml_path)
        except OSError as e:
            # I-6: mensaje genérico en pantalla; write_atomic ya garantiza que
            # el original queda intacto ante cualquier fallo (escribe a .tmp
            # + os.replace, nunca in-place — ADR-001 punto 2).
            self.log.emit(
                "✗  No se pudo escribir la colección — puede ser falta de "
                "espacio en disco o de permisos. El archivo original no se modificó."
            )
            _log.error("Relocate Traktor: escritura del NML FALLÓ (%s): %s",
                       self._nml_path, e, exc_info=True)
            self.finished_ok.emit(0, 0, 0, "error")
            return

        self._log_final_success(repaired, skipped, unresolved)
