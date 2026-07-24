"""
rekordbox_relocate.py
----------------------
Motor de "relocate" para F-08 (ADR-002): repara links rotos de Rekordbox 6
buscando el archivo por nombre en una carpeta/disco indicado por el usuario,
y actualiza `DjmdContent.FolderPath` (+ ANLZ) vía pyrekordbox.

Envuelve `pyrekordbox.Rekordbox6Database` (no modifica rekordbox_export.py).
Corre en un QThread (RekordboxRelocateWorker) — nunca en el hilo de UI, igual
que ExportWorker/PreviewWorker/RelocateWorker (Traktor).

Diferencias clave con Traktor (ver ADR-002 en engram/02_architecture.md,
no rediseñar):
  1. NO hay sync de playlists: Rekordbox liga por `DjmdContent.ID`, no por
     path — reparar el FolderPath no toca ninguna FK de playlist. Por eso
     este módulo no tiene equivalente a `build_reverse_key_index` /
     `apply_relocation` (Fase B) de traktor_relocate.py.
  2. La atomicidad es la transacción SQLite de la propia librería, no un
     write-to-temp de archivo: se acumulan cambios con
     `update_content_path(..., commit=False)` por pista y se hace UN solo
     `db.commit()` al final (con `db.rollback()` si falla).
  3. Backup = copia binaria completa de `master.db` (retención N=5, menor
     al N=10 de Traktor porque el .db cifrado pesa mucho más que un NML).
  4. R-01 (Rekordbox cerrado) se chequea nosotros mismos, up-front, ANTES
     de backup o cualquier write — el guard propio de `db.commit()` queda
     como segunda línea de defensa (salta recién en el commit final,
     después de que los ANLZ ya se escribieron a disco).
  5. ANLZ no es transaccional (`update_content_path(save=True)` escribe los
     archivos ANLZ a disco ANTES del commit de la DB) — riesgo aceptado
     explícitamente por el PO. Por eso cada reparación va en un
     `try/except` propio: `AnalysisDataPath=None` da `AttributeError`,
     directorio ANLZ inexistente da `FileNotFoundError`. Un track así se
     loguea como no resuelto y el lote sigue.
  6. Matching + modal: se reusa **tal cual** el motor de ADR-001
     (`Candidate`, `RelocateRequest`, `build_basename_index`,
     `find_candidates` importados de traktor_relocate.py) — decisión
     explícita de ADR-002 punto 5, no una necesidad accidental. Ambos
     dataclasses son duck-typed (solo tocan `title`/`artist`/
     `original_path`/`path`/`size`/`matched_title`/`matched_artist`/
     `score`), así que el `BrokenTrack` propio de este módulo (con
     `content_id` en vez de `original_key`) encaja sin adaptar nada.
     Riesgo de este acoplamiento: un cambio futuro en traktor_relocate.py
     afecta también a Rekordbox — aceptable mientras el contrato de
     matching siga siendo el mismo (si diverge, extraer a un módulo común).
"""
from __future__ import annotations

import logging
import shutil
import threading
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from PyQt6.QtCore import QThread, pyqtSignal

from pyrekordbox import Rekordbox6Database
from pyrekordbox.utils import get_rekordbox_pid

from rekordbox_export import get_artist, resolve_path
from traktor_relocate import (
    Candidate,
    RelocateRequest,
    build_basename_index,
    find_candidates,
)

_BACKUP_DIR_NAME = "listBuddy_backups"
_BACKUP_RETENTION = 5  # ADR-002: PO aprobó N=5 (menor al N=10 de Traktor)

# Logger al archivo rotativo (app_logging.py): los self.log.emit() van al panel
# de la UI que se oculta al terminar; el log de archivo es lo único que queda
# para diagnosticar un relocate fallido sobre el master.db en producción.
_log = logging.getLogger("listBuddy")


# ─────────────────────────────────────────────── Data classes ────────────

@dataclass
class BrokenTrack:
    """
    Un DjmdContent cuyo FolderPath no resuelve a un archivo existente.
    Contraparte del BrokenTrack de Traktor: usa `content_id` (FK real de
    Rekordbox) en vez de `original_key` (Rekordbox no liga playlists por
    path, así que no hay "key" que recomputar). Duck-type compatible con
    RelocateDialog (ui_components.py) y con find_candidates/RelocateRequest
    de traktor_relocate.py: solo se leen title/artist/original_path.
    """
    title: str
    artist: str
    content_id: str
    original_path: Path


# ─────────────────────────────────────────────── R-01: proceso ───────────

def is_rekordbox_running() -> bool:
    """
    R-01: a diferencia de Traktor (R-03, last-writer-wins), acá SÍ hay lock
    de OS real sobre el `.db` SQLCipher. Reusa el mismo helper
    (`get_rekordbox_pid`) que ya usa `db.py::open_database` para el flujo
    de solo-lectura. Se chequea up-front (ADR-002 punto 4), ANTES de tocar
    backup o cualquier write — `db.commit()` de pyrekordbox repite este
    chequeo y lanza `RuntimeError` si Rekordbox está corriendo, pero ese
    guard salta recién en el commit final, después de que los ANLZ ya se
    escribieron a disco (ver `update_content_path`); por eso el chequeo
    propio up-front es obligatorio, no un extra.

    Si la detección falla, asumimos que NO está corriendo (mismo criterio
    conservador de UX que `is_traktor_running` en traktor_relocate.py): el
    guard de la librería en `commit()` sigue siendo el backstop real.
    """
    try:
        return bool(get_rekordbox_pid())
    except Exception:
        return False


# ─────────────────────────────────────────────── Broken tracks ───────────

def find_broken_content(db: Rekordbox6Database) -> list[tuple[Any, BrokenTrack]]:
    """
    Recorre `db.get_content()` y devuelve los DjmdContent cuyo FolderPath
    no resuelve a un archivo existente. Reusa `resolve_path` de
    rekordbox_export.py como criterio de "roto" (el mismo que ya usa
    preview_worker.py para marcar tracks "en rojo" con fuente Rekordbox) —
    no se reinventa el criterio. `resolve_path` devuelve None tanto si la
    ruta está vacía como si no existe; acá además necesitamos el Path
    normalizado (exista o no) para mostrarlo en el modal/log, así que se
    replica solo la normalización pura de esa función (sin el gate de
    existencia, que sigue siendo resolve_path quien lo decide).
    """
    broken: list[tuple[Any, BrokenTrack]] = []
    for content in db.get_content():
        raw = getattr(content, "FolderPath", None)
        if not raw:
            continue
        if resolve_path(raw) is not None:
            continue  # existe — mismo criterio que preview_worker, no roto
        path = _normalize_folder_path(raw)
        title = getattr(content, "Title", None) or path.name
        artist = get_artist(content)
        content_id = str(getattr(content, "ID", ""))
        broken.append((
            content,
            BrokenTrack(
                title=title, artist=artist,
                content_id=content_id, original_path=path,
            ),
        ))
    return broken


def _normalize_folder_path(raw_path: str) -> Path:
    """
    Misma normalización que `rekordbox_export.resolve_path()` (Rekordbox en
    Windows guarda `/C/Users/...` → se antepone la letra de unidad), pero
    sin el gate de `.exists()` — acá se necesita el Path aunque no exista,
    para mostrarlo en el modal/log de un track roto.
    """
    p = raw_path.strip()
    if p.startswith("/") and len(p) > 2 and p[2] == "/":
        p = p[1] + ":" + p[2:]
    return Path(p)


# ─────────────────────────────────────────────── Backup ──────────────────

def backup_master_db(master_db_path: Path) -> Path:
    """
    Copia binaria completa de master.db a
    <carpeta>/listBuddy_backups/master.TIMESTAMP.db antes del primer write
    de la sesión (ADR-002, punto 1). Una copia por sesión de relocate, no
    por pista. Retiene las últimas N=5 (PO aprobó, menor al N=10 de Traktor
    porque el .db cifrado pesa mucho más que un NML) y poda el resto. Si
    falla (permisos, disco lleno) propaga OSError — el llamador debe
    abortar sin escribir.
    """
    backups_dir = master_db_path.parent / _BACKUP_DIR_NAME
    backups_dir.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d-%H%M%S")
    dest = backups_dir / f"master.{ts}.db"
    shutil.copy2(master_db_path, dest)
    _prune_backups(backups_dir)
    return dest


def _prune_backups(backups_dir: Path, keep: int = _BACKUP_RETENTION) -> None:
    backups = sorted(
        backups_dir.glob("master.*.db"),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )
    for old in backups[keep:]:
        try:
            old.unlink()
        except OSError:
            pass  # poda es best-effort, no debe abortar la sesión


# ─────────────────────────────────────────────── QThread worker ──────────

class RekordboxRelocateWorker(QThread):
    log         = pyqtSignal(str)
    progress    = pyqtSignal(int, int)          # (hechas, total)
    ask_user    = pyqtSignal(object)            # RelocateRequest — bloquea el worker
    finished_ok = pyqtSignal(int, int, int, str)  # (reparadas, salteadas, sin_match, status)
    # status: "ok" | "cancelled" | "error" | "blocked"

    def __init__(
        self, db_path: Path | None, search_root: Path, auto_resolve: bool = False,
    ) -> None:
        super().__init__()
        self._db_path = db_path
        self._search_root = search_root
        self._auto_resolve = auto_resolve
        self._answer_event = threading.Event()
        self._answer: Path | None = None

    def provide_answer(self, choice: Path | None) -> None:
        """
        Slot llamado desde el hilo de UI con la decisión del modal.
        `choice` es un Path elegido, o None = SKIP (mismo contrato que
        RelocateWorker de Traktor: sin default silencioso).
        """
        self._answer = choice
        self._answer_event.set()

    def run(self) -> None:
        # R-01: chequeo de proceso en el hilo del worker, no en el de UI —
        # get_rekordbox_pid() no es garantizadamente liviano.
        _log.info("Relocate Rekordbox: inicio · db=%s · search_root=%s · auto=%s",
                  self._db_path or "(autodetect)", self._search_root, self._auto_resolve)
        if is_rekordbox_running():
            self.log.emit(
                "✗  Rekordbox está abierto. Cerralo antes de reparar enlaces: "
                "la base de datos queda bloqueada a nivel de sistema operativo "
                "mientras el programa está corriendo."
            )
            _log.warning("Relocate Rekordbox: bloqueado — Rekordbox está abierto (R-01).")
            self.finished_ok.emit(0, 0, 0, "blocked")
            return

        try:
            db = (
                Rekordbox6Database(str(self._db_path))
                if self._db_path else Rekordbox6Database()
            )
        except Exception as e:
            self.log.emit(
                f"✗  No se pudo abrir la base de datos de Rekordbox.\n   Detalle: {e}"
            )
            _log.error("Relocate Rekordbox: no se pudo abrir master.db (%s): %s",
                       self._db_path or "(autodetect)", e, exc_info=True)
            self.finished_ok.emit(0, 0, 0, "error")
            return

        try:
            broken = find_broken_content(db)
            total = len(broken)
            self.log.emit(f"🔍  {total} enlace(s) roto(s) en la librería.")
            if total == 0:
                self.finished_ok.emit(0, 0, 0, "ok")
                return

            self.log.emit(f"📂  Indexando archivos en: {self._search_root}")
            index = build_basename_index(
                self._search_root,
                should_stop=self.isInterruptionRequested,
                on_progress=lambda n: self.progress.emit(n, 0),
            )
            if self.isInterruptionRequested():
                self.log.emit(
                    "\n⏹  Relocate cancelado — master.db intacto, nada se escribió."
                )
                self.finished_ok.emit(0, 0, 0, "cancelled")
                return
            indexed_count = sum(len(v) for v in index.values())
            self.log.emit(f"   {indexed_count} archivo(s) indexado(s).")

            repaired = skipped = unresolved = 0
            for i, (content, broken_track) in enumerate(broken, start=1):
                if self.isInterruptionRequested():
                    self.log.emit(
                        "\n⏹  Relocate cancelado — master.db intacto, nada se escribió."
                    )
                    self.finished_ok.emit(repaired, skipped, unresolved, "cancelled")
                    return

                self.progress.emit(i, total)
                label = (
                    f"{broken_track.artist} - {broken_track.title}".strip(" -")
                    or broken_track.original_path.name
                )

                candidates = find_candidates(broken_track, index)
                if not candidates:
                    unresolved += 1
                    self.log.emit(f"   ✗  Sin coincidencias: {label}")
                    continue

                auto_resolved = False
                if len(candidates) == 1:
                    chosen: Path | None = candidates[0].path
                elif self._auto_resolve:
                    # Igual que Traktor: candidates[0] ya viene ordenado por
                    # score descendente (find_candidates) — no es azar.
                    chosen = candidates[0].path
                    auto_resolved = True
                else:
                    self._answer_event.clear()
                    self.ask_user.emit(
                        RelocateRequest(broken=broken_track, candidates=candidates)
                    )
                    self._answer_event.wait()
                    chosen = self._answer

                if chosen is None:
                    skipped += 1
                    self.log.emit(f"   ⏭  Salteado: {label}")
                    continue

                # ADR-002: no confiar en el `assert path.exists()` interno de
                # check_path=True (se strippea bajo `python -O`) — guard de
                # existencia propio antes de tocar la DB/ANLZ.
                if not chosen.exists():
                    unresolved += 1
                    self.log.emit(
                        f"   ✗  El archivo elegido ya no existe: {label} → {chosen}"
                    )
                    continue

                # Por pista: try/except (ADR-002 punto 6) — ANLZ inexistente
                # o AnalysisDataPath=None no debe abortar el lote entero.
                try:
                    db.update_content_path(
                        content, chosen, save=True, check_path=True, commit=False,
                    )
                except (AttributeError, FileNotFoundError, AssertionError, OSError) as e:
                    unresolved += 1
                    self.log.emit(
                        f"   ✗  Error al reparar ({type(e).__name__}): {label} → {e}"
                    )
                    continue

                repaired += 1
                if auto_resolved:
                    self.log.emit(f"   ✓  Reparado (auto): {label} → {chosen}")
                else:
                    self.log.emit(f"   ✓  Reparado: {label} → {chosen}")

            if repaired == 0:
                self.log.emit("\nSin cambios para escribir (0 reparaciones aplicadas).")
                self.finished_ok.emit(repaired, skipped, unresolved, "ok")
                return

            # Backup ANTES del único commit de la sesión (ADR-002 punto 1).
            # `update_content_path(commit=False)` no toca master.db en disco
            # todavía — el archivo solo cambia en el `db.commit()` de abajo,
            # así que este es el punto correcto de "antes del primer write".
            # Si se pasó un path explícito, se respalda ESE archivo (podría
            # no llamarse "master.db" en un entorno de prueba); si fue
            # autodetectado, se usa `db.db_directory / "master.db"` (nombre
            # fijo para Rekordbox 6/7 — verificado en pyrekordbox/config.py).
            master_db_path = self._db_path or (db.db_directory / "master.db")
            try:
                backup_path = backup_master_db(master_db_path)
                self.log.emit(f"💾  Backup creado: {backup_path}")
                _log.info("Relocate Rekordbox: backup creado en %s", backup_path)
            except OSError as e:
                self.log.emit(
                    f"✗  No se pudo crear el backup — abortando sin escribir.\n   Detalle: {e}"
                )
                _log.error("Relocate Rekordbox: backup FALLÓ (%s) — rollback, sin escribir: %s",
                           master_db_path, e, exc_info=True)
                db.rollback()
                self.finished_ok.emit(0, 0, 0, "error")
                return

            try:
                # SIEMPRE db.commit() (autoinc=True por default) — NUNCA
                # db.session.commit() crudo: saltearía el autoincremento del
                # USN local/por fila (ADR-002 punto 2). commit() repite acá
                # el chequeo de Rekordbox abierto (backstop, ver R-01).
                db.commit()
            except Exception as e:
                db.rollback()
                self.log.emit(
                    f"✗  Error al escribir la base de datos — rollback aplicado.\n   Detalle: {e}"
                )
                _log.error("Relocate Rekordbox: commit FALLÓ — rollback aplicado: %s",
                           e, exc_info=True)
                self.finished_ok.emit(0, 0, 0, "error")
                return

            self.log.emit(
                f"\n✓  {repaired} reparada(s) · {skipped} salteada(s) · "
                f"{unresolved} sin coincidencias."
            )
            _log.info("Relocate Rekordbox: OK · %d reparadas · %d salteadas · %d sin coincidencias",
                      repaired, skipped, unresolved)
            self.finished_ok.emit(repaired, skipped, unresolved, "ok")
        finally:
            try:
                db.close()
            except Exception:
                pass
