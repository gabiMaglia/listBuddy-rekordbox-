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
     `find_candidates`) — decisión explícita de ADR-002 punto 5, no una
     necesidad accidental. Ambos dataclasses son duck-typed (solo tocan
     `title`/`artist`/`original_path`/`path`/`size`/`matched_title`/
     `matched_artist`/`score`), así que el `BrokenTrack` propio de este
     módulo (con `content_id` en vez de `original_key`) encaja sin adaptar
     nada.

T-017 (D-05): el orquestador del loop de resolución (indexar disco, decidir
0/1/N candidatos, ask_user + espera, cancelación, progreso, log) vivía acá
duplicado con traktor_relocate.py — se extrajo a
`relocate_core.BaseRelocateWorker` (refactor puro, sin cambio de
comportamiento observable). `RekordboxRelocateWorker` ahora solo implementa
lo específico de Rekordbox: chequeo R-01, abrir la DB, encontrar los rotos
y aplicar UNA reparación (`update_content_path` + guard de existencia +
try/except de ANLZ). `Candidate`/`RelocateRequest`/`build_basename_index`/
`find_candidates` se importan ahora de `relocate_core` (módulo neutral)
en vez de `traktor_relocate` — resuelve el acoplamiento por nombre de
archivo que señalaba la auditoría (engram/07_production_readiness.md,
"Otras observaciones de arquitectura"): antes este módulo dependía de
traktor_relocate.py por dónde vivían esas piezas, no porque fueran
conceptualmente de Traktor.
"""
from __future__ import annotations

import logging
import shutil
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from pyrekordbox import Rekordbox6Database
from pyrekordbox.utils import get_rekordbox_pid

from rekordbox_export import get_artist, resolve_path
from relocate_core import (
    BaseRelocateWorker,
    Candidate,
    RelocateRequest,
    build_basename_index,
    check_disk_space_for_backup,
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
    de relocate_core.py: solo se leen title/artist/original_path.
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

    B-3 (T-018): chequea espacio libre ANTES de copiar
    (`check_disk_space_for_backup`) y, si `shutil.copy2` falla a mitad de
    camino (ej. `ENOSPC` con un master.db de cientos de MB), borra el
    destino parcial antes de re-lanzar — un backup truncado NO puede
    quedar en `listBuddy_backups/` haciéndose pasar por el más reciente
    (`_prune_backups` lo contaría como válido, y sería el que el usuario
    elegiría para restaurar).
    """
    check_disk_space_for_backup(master_db_path)
    backups_dir = master_db_path.parent / _BACKUP_DIR_NAME
    backups_dir.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d-%H%M%S")
    dest = backups_dir / f"master.{ts}.db"
    try:
        shutil.copy2(master_db_path, dest)
    except OSError:
        dest.unlink(missing_ok=True)
        raise
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

class RekordboxRelocateWorker(BaseRelocateWorker):
    def __init__(
        self, db_path: Path | None, search_root: Path, auto_resolve: bool = False,
    ) -> None:
        super().__init__(search_root, auto_resolve=auto_resolve)
        self._db_path = db_path
        self._db: Rekordbox6Database | None = None

    # ── Hooks de relocate_core.BaseRelocateWorker ──────────────────────

    def _broken_scope_noun(self) -> str:
        return "librería"

    def _write_target_name(self) -> str:
        return "master.db"

    def _engine_name(self) -> str:
        return "Rekordbox"

    def _label_for(self, broken_track: BrokenTrack) -> str:
        return (
            f"{broken_track.artist} - {broken_track.title}".strip(" -")
            or broken_track.original_path.name
        )

    def _cancel_extra_note(self, repaired: int) -> str:
        # I-6: "master.db intacto, nada se escribió" (mensaje base heredado
        # de relocate_core.BaseRelocateWorker) es cierto para la DB — pero
        # NO para todo lo que toca esta sesión. `update_content_path(...,
        # save=True)` ya escribió a disco los ANLZ de cada pista reparada
        # ANTES del commit final (ADR-002 punto 3), y el commit nunca llega
        # a correr si se cancela. El texto no puede prometer más de lo que
        # es cierto.
        if repaired == 0:
            return ""
        return (
            f"Ojo: los archivos de análisis (ANLZ) de {repaired} pista(s) ya "
            "procesada(s) antes de cancelar SÍ se escribieron a disco (no "
            "afecta tus playlists ni el resto de tu librería; Rekordbox "
            "puede regenerarlos re-analizando esas pistas)."
        )

    def _apply_one(self, content: Any, broken_track: BrokenTrack, chosen: Path) -> bool:
        label = self._label_for(broken_track)

        # ADR-002: no confiar en el `assert path.exists()` interno de
        # check_path=True (se strippea bajo `python -O`) — guard de
        # existencia propio antes de tocar la DB/ANLZ.
        if not chosen.exists():
            self.log.emit(f"   ✗  El archivo elegido ya no existe: {label} → {chosen}")
            return False

        # Por pista: try/except (ADR-002 punto 6) — ANLZ inexistente o
        # AnalysisDataPath=None no debe abortar el lote entero.
        assert self._db is not None
        try:
            self._db.update_content_path(
                content, chosen, save=True, check_path=True, commit=False,
            )
        except (AttributeError, FileNotFoundError, AssertionError, OSError) as e:
            # I-6: nada de nombre de clase de excepción de Python ni texto
            # crudo en pantalla (acá salía literal "AttributeError: 'NoneType'
            # object has no attribute 'strip'"). El detalle completo, con el
            # content_id para poder correlacionar, va SOLO al log de archivo.
            self.log.emit(
                f"   ✗  No se pudo reparar (archivo de análisis inaccesible "
                f"o pista nunca analizada): {label}"
            )
            _log.error(
                "Relocate Rekordbox: fallo al reparar content_id=%s (%s): %s",
                broken_track.content_id, type(e).__name__, e, exc_info=True,
            )
            return False

        return True

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
            # I-6: mensaje genérico en pantalla; el detalle técnico completo
            # (puede ser cualquier excepción de pyrekordbox/SQLCipher) va
            # solo al log de archivo.
            self.log.emit(
                "✗  No se pudo abrir la base de datos de Rekordbox — puede "
                "estar dañada, en un formato inesperado, o la clave de "
                "desencriptado no está disponible."
            )
            _log.error("Relocate Rekordbox: no se pudo abrir master.db (%s): %s",
                       self._db_path or "(autodetect)", e, exc_info=True)
            self.finished_ok.emit(0, 0, 0, "error")
            return

        self._db = db
        try:
            broken = find_broken_content(db)

            result = self._run_resolution(broken)
            if result is None:
                return
            repaired, skipped, unresolved = (
                result.repaired, result.skipped, result.unresolved,
            )

            if repaired == 0:
                self.log.emit("\nSin cambios para escribir (0 reparaciones aplicadas).")
                self.finished_ok.emit(repaired, skipped, unresolved, "ok")
                return

            # I-4: re-chequear que Rekordbox siga cerrado JUSTO ANTES de
            # escribir. El chequeo de arriba corrió al principio de run() —
            # entre eso y este punto puede haber pasado el indexado de disco
            # entero más minutos/horas de modales de desambiguación
            # (auto_resolve=False es el default). `db.commit()` ya repite
            # este chequeo (backstop, R-01), pero recién en el commit final,
            # DESPUÉS de que los ANLZ de este lote ya se escribieron a disco
            # — re-chequear acá, antes del backup, es la primera línea de
            # defensa real. Mismo mensaje/status "blocked" que el chequeo
            # inicial — se aborta SIN backupear ni comitear.
            if is_rekordbox_running():
                self.log.emit(
                    "✗  Rekordbox está abierto. Cerralo antes de reparar enlaces: "
                    "la base de datos queda bloqueada a nivel de sistema operativo "
                    "mientras el programa está corriendo."
                )
                _log.warning(
                    "Relocate Rekordbox: bloqueado en el re-chequeo previo a "
                    "escribir (R-01) — %d reparación(es) sin comitear.", repaired,
                )
                db.rollback()
                self.finished_ok.emit(0, 0, 0, "blocked")
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
                # I-6: mensaje genérico en pantalla; puede ser un OSError de
                # disco lleno tipo "[Errno 28] No space left on device: ...".
                self.log.emit(
                    "✗  No se pudo crear el backup — abortando sin escribir. "
                    "Puede ser falta de espacio en disco o de permisos sobre la carpeta."
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
                # I-6: mensaje genérico en pantalla; el rollback ya garantiza
                # que la base de datos no quedó modificada (los ANLZ de este
                # lote sí se escribieron antes del commit — riesgo residual
                # 1 de ADR-002, ya aceptado, no se promete su reversión acá).
                self.log.emit(
                    "✗  No se pudo escribir la base de datos — se revirtieron "
                    "los cambios (rollback). master.db no quedó modificado."
                )
                _log.error("Relocate Rekordbox: commit FALLÓ — rollback aplicado: %s",
                           e, exc_info=True)
                self.finished_ok.emit(0, 0, 0, "error")
                return

            self._log_final_success(repaired, skipped, unresolved)
        finally:
            try:
                db.close()
            except Exception:
                pass
