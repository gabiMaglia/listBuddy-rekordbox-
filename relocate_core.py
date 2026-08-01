"""
relocate_core.py
------------------
Orquestador y matching COMPARTIDOS entre `RelocateWorker` (Traktor,
traktor_relocate.py) y `RekordboxRelocateWorker` (Rekordbox,
rekordbox_relocate.py) — T-017 / D-05.

D-05 (engram/07_production_readiness.md): el loop `run()` de ambos workers
era ~90% idéntico (decidir 0/1/N candidatos, `ask_user`/modal, chequeo de
cancelación, progreso, logging), duplicado en dos archivos. El núcleo de
matching (`Candidate`/`RelocateRequest`/`build_basename_index`/
`find_candidates`) ya vivía compartido, pero importado por nombre de archivo
concreto (`rekordbox_relocate` -> `traktor_relocate`), acoplamiento que la
auditoría señaló como parte del mismo problema ("el módulo de Rekordbox
depende del de Traktor por el *nombre del archivo*, no por un módulo
compartido neutral"). Este módulo es ese punto neutral: ninguno de los dos
motores concretos lo importa al revés, y las piezas de matching se movieron
acá para evitar el import circular que hubiera resultado de dejarlas en
traktor_relocate.py mientras ese archivo pasa a heredar de acá.

Qué VIVE acá (no depende del formato de la librería, NML vs SQLCipher):
  - Matching puro: `Candidate`, `RelocateRequest`, `build_basename_index`,
    `find_candidates` (movidos tal cual desde traktor_relocate.py, sin
    cambios de lógica — `traktor_relocate.py` los re-exporta para no romper
    imports existentes, ver tests/test_traktor_relocate.py). T-028 agregó un
    fallback tolerante (`build_normalized_index`/`_normalize_key`): si el
    lookup exacto da 0, se reintenta por nombre sin prefijo numérico `NN - `
    y sin extensión — nunca reemplaza el match exacto, y el resultado queda
    marcado `Candidate.match_type="normalized"` para que ni la UI ni el
    auto-resolve lo traten como una decisión automática (ADR-001 p.3).
  - `BaseRelocateWorker`: la clase base QThread con el loop de resolución
    (`_run_resolution`) — indexar disco, recorrer `broken`, decidir 0/1/N
    candidatos, esperar `ask_user`, chequear interrupción, progreso y log.

Qué NO vive acá (sigue en cada motor, `traktor_relocate.py`/
`rekordbox_relocate.py`): chequeo R-0x de proceso corriendo, abrir/parsear la
librería, encontrar los tracks rotos, aplicar UNA reparación concreta
(`_apply_one`, override por subclase) y el paso final de backup + escritura
atómica/commit (sync de PLAYLISTS incluido, solo aplica a Traktor).

Esto es un refactor puro (T-017): el comportamiento observable (logs,
signals emitidos, orden) es idéntico al de antes de extraer este módulo. No
cambia matching, backup, escritura ni sync — eso queda para T-018/T-019/T-020.
"""
from __future__ import annotations

import logging
import os
import re
import shutil
import threading
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any

from PyQt6.QtCore import QThread, pyqtSignal

_BACKUP_DIR_NAME = "listBuddy_backups"

# Logger al archivo rotativo (app_logging.py). Los self.log.emit() van al panel
# de la UI, que se oculta al terminar el relocate; el log de archivo es lo
# único que sobrevive para diagnosticar un relocate fallido en producción.
_log = logging.getLogger("listBuddy")


# ─────────────────────────────────────────────── Backup (B-3, T-018) ─────

def check_disk_space_for_backup(
    src: Path, write_dir: Path | None = None, action: str = "el backup",
) -> None:
    """
    Chequeo de espacio libre ANTES de intentar copiar el backup — mismo
    patrón que `worker.py` ya usa para el export (`shutil.disk_usage`,
    comparar contra el tamaño estimado, abortar con mensaje en GB). El
    write path sobre la librería del usuario (NML/master.db) es MÁS
    riesgoso que copiar mp3s del export y hasta T-018 no tenía esta
    protección (B-3). Compara el tamaño de `src` contra el espacio libre
    en `write_dir` (por default `src.parent`: misma carpeta donde vive
    `listBuddy_backups/`, mismo filesystem). Lanza `OSError` — el llamador
    la trata igual que cualquier otro fallo de backup (abortar sin
    escribir, ver `backup_collection`/`backup_master_db`).

    Si no se puede ni siquiera `stat()` el origen, no aborta acá: deja que
    el intento de copia real falle con su propio error específico.

    T-019: `write_dir`/`action` generalizan este chequeo para reusarlo en
    sentido inverso — restaurar un backup SOBRE el archivo real
    (`restore_backup`, B-4) escribe en la carpeta del archivo real, no en
    la del backup, y el mensaje debe hablar de "la restauración", no "el
    backup". Los llamados existentes (`backup_collection`/
    `backup_master_db`) no pasan estos parámetros y mantienen el
    comportamiento exacto de antes.
    """
    try:
        size = src.stat().st_size
    except OSError:
        return
    check_dir = write_dir if write_dir is not None else src.parent
    free = shutil.disk_usage(str(check_dir)).free
    if size > free:
        needed_gb = size / 1_073_741_824
        avail_gb = free / 1_073_741_824
        raise OSError(
            f"Espacio insuficiente para {action}: necesitás ~{needed_gb:.2f} GB "
            f"y hay {avail_gb:.2f} GB disponibles. Liberá espacio e intentá de nuevo."
        )


# ─────────────────────────────────────────────── Data classes ────────────

@dataclass
class Candidate:
    """Un archivo candidato para reparar un BrokenTrack."""
    path: Path
    size: int
    matched_title: str | None
    matched_artist: str | None
    score: float
    # T-028: "exact" = matcheó por nombre de archivo completo (incluye
    # extensión); "normalized" = matcheó solo por la clave tolerante
    # (sin prefijo numérico `NN - ` y sin extensión, ver `_normalize_key`).
    # Default "exact" para no romper otros call sites que construyan
    # Candidate directamente (no los hay en el repo hoy, pero es la
    # convención más segura para un dataclass público).
    match_type: str = "exact"


@dataclass
class RelocateRequest:
    """
    Payload de `ask_user` — contrato del modal (ADR-001). `broken` es
    duck-typed a propósito: cada motor tiene su propio `BrokenTrack`
    (Traktor usa `original_key`, Rekordbox usa `content_id`), y acá solo se
    leen `title`/`artist`/`original_path`, comunes a ambos.
    """
    broken: Any
    candidates: list[Candidate] = field(default_factory=list)


@dataclass
class ResolutionResult:
    """Conteos que devuelve `BaseRelocateWorker._run_resolution` cuando el
    loop terminó sin cancelarse — la subclase sigue con su finalize propio
    (backup + escritura/commit)."""
    repaired: int
    skipped: int
    unresolved: int


# ─────────────────────────────────────────── Restaurar backup (B-4, T-019) ─
#
# Todo lo de acá abajo es un flujo NUEVO y separado del backup-al-escribir
# (`backup_collection`/`backup_master_db`, que siguen viviendo en cada motor
# concreto): esto es para cuando el USUARIO quiere volver atrás, no para
# cuando la app escribe. No se duplica el formato de nombre de archivo — se
# reusa tal cual (`collection.YYYYMMDD-HHMMSS.nml` / `master.YYYYMMDD-HHMMSS.db`,
# mismo `_BACKUP_DIR_NAME`), así que un backup creado por cualquiera de los
# dos motores aparece acá sin adaptar nada.

@dataclass
class BackupInfo:
    """Un backup listo para mostrarse/restaurarse (B-4). `timestamp` es la
    fecha/hora parseada del NOMBRE del archivo (no el mtime del filesystem,
    que `shutil.copy2` preserva del original y sería engañoso acá) — `None`
    si el nombre no matchea el formato esperado (algo ajeno colado en
    `listBuddy_backups/`, no debería pasar en uso normal pero no debe
    romper el listado)."""
    path: Path
    timestamp: datetime | None
    size: int


_BACKUP_TS_FORMAT = "%Y%m%d-%H%M%S"


def _parse_backup_timestamp(filename: str) -> datetime | None:
    """
    Los nombres son `{prefijo}.{timestamp}.{ext}` (`collection.<ts>.nml`,
    `master.<ts>.db`) — exactamente 3 partes separadas por '.' porque el
    timestamp usa '-' como separador interno, no '.'. Si no matchea ese
    shape o el timestamp no parsea, devuelve None en vez de lanzar: un
    archivo con nombre inesperado no debe romper el listado completo.
    """
    parts = filename.split(".")
    if len(parts) != 3:
        return None
    try:
        return datetime.strptime(parts[1], _BACKUP_TS_FORMAT)
    except ValueError:
        return None


def list_backups(target_path: Path, glob_pattern: str) -> list[BackupInfo]:
    """
    Lista los backups disponibles para `target_path` (el archivo real que la
    app repara: `collection.nml` o `master.db`), buscando en
    `<carpeta-de-target_path>/listBuddy_backups/` con el mismo patrón de
    nombre que ya usa `_prune_backups` en cada motor (`"collection.*.nml"` /
    `"master.*.db"`). Orden: más reciente primero (por timestamp parseado
    del nombre; los que no parsean van al final). Devuelve lista vacía si
    la carpeta de backups no existe todavía — es responsabilidad del
    llamador (UI) mostrar "no hay copias de seguridad" en ese caso, no de
    esta función lanzar o inventar un mensaje.
    """
    backups_dir = target_path.parent / _BACKUP_DIR_NAME
    if not backups_dir.is_dir():
        return []
    items: list[BackupInfo] = []
    for p in backups_dir.glob(glob_pattern):
        try:
            size = p.stat().st_size
        except OSError:
            continue
        items.append(BackupInfo(path=p, timestamp=_parse_backup_timestamp(p.name), size=size))
    items.sort(key=lambda b: b.timestamp or datetime.min, reverse=True)
    return items


def restore_backup(backup_path: Path, target_path: Path) -> None:
    """
    Restaura `backup_path` SOBRE `target_path` (B-4) — la dirección opuesta
    a `backup_collection`/`backup_master_db` (que copian el archivo real
    HACIA el backup). Mismas garantías de atomicidad que el resto del write
    path (ADR-001 punto 2, `write_atomic`): se copia a un `.tmp` en la
    MISMA carpeta que `target_path`, `flush + fsync`, y recién entonces
    `os.replace(tmp, target_path)`. Si la copia falla a mitad (disco lleno,
    permisos), el `.tmp` se descarta y `target_path` NO se toca — nunca hay
    un sobrescrito in-place que pueda dejar el archivo real a medio
    escribir.

    Decisión explícita: NO se crea un backup adicional de `target_path`
    antes de restaurar. Sobrescribir con un backup elegido YA ES el
    rollback que el usuario pidió, confirmado explícitamente en la UI antes
    de llegar acá (ver `ui.py::_confirm_restore_backup`); encadenar otro
    backup automático solo agregaría ruido a `listBuddy_backups/` sin red
    de seguridad real — si el usuario restauró la copia equivocada, el
    resto de los backups (N=10/N=5 según motor) siguen ahí para volver a
    intentar.

    Propaga `OSError` ante cualquier fallo (incluido espacio insuficiente,
    chequeado antes de copiar vía `check_disk_space_for_backup`) — el
    llamador (UI) debe mostrarlo, nunca asumir que restauró en silencio.
    """
    check_disk_space_for_backup(
        backup_path, write_dir=target_path.parent, action="la restauración",
    )
    tmp_path = target_path.parent / (target_path.name + ".restoretmp")
    try:
        with open(backup_path, "rb") as src, open(tmp_path, "wb") as dst:
            shutil.copyfileobj(src, dst)
            dst.flush()
            os.fsync(dst.fileno())
        os.replace(tmp_path, target_path)
    except OSError:
        try:
            tmp_path.unlink(missing_ok=True)
        except OSError:
            pass
        raise


class RestoreBackupWorker(QThread):
    """
    QThread mínimo para B-4: `restore_backup` copia un archivo binario
    completo (hasta cientos de MB para `master.db`, ver I-7) — igual que el
    resto de la app (ExportWorker, RelocateWorker/RekordboxRelocateWorker),
    nunca corre en el hilo de UI para no congelar la ventana durante la
    copia. Sin progreso incremental a propósito: es una copia de UN
    archivo (no un `os.walk` de una librería entera), la barra indeterminada
    que ya usa `progress_section` alcanza.
    """

    finished_ok = pyqtSignal(bool, str)  # (ok, mensaje_de_error_si_fallo)

    def __init__(self, backup_path: Path, target_path: Path) -> None:
        super().__init__()
        self._backup_path = backup_path
        self._target_path = target_path

    def run(self) -> None:
        try:
            restore_backup(self._backup_path, self._target_path)
        except OSError as exc:
            _log.error(
                "Restore de backup falló: %s -> %s (%s)",
                self._backup_path, self._target_path, exc,
            )
            self.finished_ok.emit(False, str(exc))
            return
        _log.info(
            "Restore de backup OK: %s -> %s", self._backup_path, self._target_path,
        )
        self.finished_ok.emit(True, "")


# ─────────────────────────────────────────────── Disk index ──────────────

_INDEX_PROGRESS_EVERY = 250  # T-007: cada cuántos archivos se reporta avance


def build_basename_index(
    search_root: Path,
    should_stop: Callable[[], bool] | None = None,
    on_progress: Callable[[int], None] | None = None,
    progress_every: int = _INDEX_PROGRESS_EVERY,
) -> dict[str, list[Path]]:
    """
    Índice {basename.lower(): [paths]} construido UNA sola vez por corrida
    (evita re-escanear disco por pista; un scan completo es caro en
    discos USB/red). Salta la carpeta de backups propia para no ofrecerla
    como candidato.

    T-007: el `os.walk` puede ser la fase más larga de un relocate (disco/
    carpeta con muchos archivos) y antes no era cancelable ni mostraba
    avance durante el recorrido. `should_stop` (ej. `worker.isInterruptionRequested`)
    se chequea por carpeta visitada y cada `progress_every` archivos, para
    cortar pronto sin esperar a que termine todo el walk. `on_progress` (ej.
    `worker.progress.emit`) se invoca con la cantidad de archivos indexados
    hasta el momento, cada `progress_every` archivos. Queda desacoplado de
    QThread a propósito (recibe callables, no una referencia al worker) para
    seguir siendo testeable sin Qt.
    """
    index: dict[str, list[Path]] = {}

    def _on_error(_exc: OSError) -> None:
        pass  # directorios sin permiso: se ignoran, no abortan el índice

    count = 0
    for root, dirs, files in os.walk(search_root, onerror=_on_error):
        if should_stop is not None and should_stop():
            break
        dirs[:] = [d for d in dirs if d != _BACKUP_DIR_NAME]
        for name in files:
            index.setdefault(name.lower(), []).append(Path(root) / name)
            count += 1
            if count % progress_every == 0:
                if on_progress is not None:
                    on_progress(count)
                if should_stop is not None and should_stop():
                    return index
    return index


# T-028: prefijo numérico que la propia app antepone al exportar
# (`worker.py::_safe_filename`, ej. `001 - Artist - Title.mp3`). 1 a 4
# dígitos (zfill del padding de la playlist, nunca más de 4 en uso real),
# espacios opcionales alrededor del guion.
_NUMERIC_PREFIX_RE = re.compile(r"^\d{1,4}\s*-\s*")


def _normalize_key(filename: str) -> str:
    """
    Clave tolerante (T-028) para el fallback de `find_candidates` cuando el
    lookup exacto por nombre completo da 0 resultados: stem sin extensión
    (tolera `X.aiff` en la DB vs `X.aif` truncado en disco por exFAT/
    Windows) y sin el prefijo numérico `NN - ` que agrega esta misma app al
    exportar, todo en minúsculas. Se aplica simétricamente al nombre del
    archivo roto (`find_candidates`) y a cada archivo indexado
    (`build_normalized_index`) para que ambos lados normalicen igual.
    """
    stem = Path(filename).stem
    stem = _NUMERIC_PREFIX_RE.sub("", stem)
    return stem.lower()


def build_normalized_index(index: dict[str, list[Path]]) -> dict[str, list[Path]]:
    """
    Índice tolerante (T-028) derivado del índice exacto ya construido por
    `build_basename_index` — NO vuelve a recorrer disco (el walk ya es la
    fase más cara del relocate, ver `_INDEX_PROGRESS_EVERY`). Agrupa cada
    Path ya indexado bajo su `_normalize_key`, así dos archivos con
    distinto nombre crudo (`001 - Artist - Title.wav` y
    `014 - Artist - Title.wav`, el caso real de un track exportado a
    varias playlists) pueden colisionar bajo la misma clave normalizada —
    intencional: es el escenario de colisión N-a-1 que `find_candidates`
    debe devolver como múltiples candidatos, no descartar.
    """
    normalized: dict[str, list[Path]] = {}
    for paths in index.values():
        for p in paths:
            normalized.setdefault(_normalize_key(p.name), []).append(p)
    return normalized


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
    track: Any,
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
    track: Any,
    index: dict[str, list[Path]],
    normalized_index: dict[str, list[Path]] | None = None,
) -> list[Candidate]:
    """
    Matching primario: nombre de archivo EXACTO (case-insensitive), contra
    el índice ya construido. El fuzzy por título/artista NO decide — solo
    rankea los candidatos que ya matchearon (ADR-001, punto 3): 0 matches =
    sin resolver, 1 = se aplica, >1 = modal.

    T-028: si el lookup exacto da 0 resultados Y se pasó `normalized_index`
    (construido una sola vez por corrida vía `build_normalized_index`), cae
    a un segundo lookup por `_normalize_key` — tolera el prefijo numérico
    `NN - ` que la propia app agrega al exportar y diferencias de extensión
    (`.aiff` vs `.aif`). Los candidatos resultantes quedan marcados
    `match_type="normalized"` para que la UI lo muestre (criterio 3) y para
    que el loop de resolución nunca los auto-resuelva (criterio 4,
    `BaseRelocateWorker._run_resolution`) — el matching laxo rankea, nunca
    decide solo. `normalized_index=None` (default) preserva el
    comportamiento exacto de antes tal cual, sin fallback.

    `track` es duck-typed (BrokenTrack de Traktor o de Rekordbox): solo se
    leen `original_path`/`title`/`artist`, comunes a ambos.
    """
    key = track.original_path.name.lower()
    paths = index.get(key, [])
    match_type = "exact"
    if not paths and normalized_index is not None:
        paths = normalized_index.get(_normalize_key(track.original_path.name), [])
        match_type = "normalized"
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
            match_type=match_type,
        ))
    candidates.sort(key=lambda c: c.score, reverse=True)
    return candidates


# ─────────────────────────────────────────────── QThread worker base ─────

class BaseRelocateWorker(QThread):
    """
    Orquestador COMÚN del loop de resolución (T-017/D-05): indexar disco,
    recorrer `broken`, decidir 0/1/N candidatos, esperar `ask_user`,
    chequear interrupción, emitir progreso y log. Ni sabe ni le importa si
    la librería es un NML o un master.db — eso lo maneja cada subclase.

    Contrato con la subclase (hooks a implementar, todos síncronos y
    livianos salvo `_apply_one`, que puede tocar disco/DB):
      - `_broken_scope_noun()`  -> "colección" | "librería" (texto del log
        de conteo inicial).
      - `_write_target_name()` -> "NML" | "master.db" (texto del log de
        cancelación).
      - `_engine_name()`       -> "Traktor" | "Rekordbox" (prefijo del log
        de archivo en el resumen final).
      - `_label_for(broken_track)` -> str (formato del label en los logs
        por pista; difiere entre motores).
      - `_apply_one(raw_entry, broken_track, chosen)` -> bool: aplica UNA
        reparación concreta. `True` = éxito (la base cuenta `repaired` y
        logea "✓ Reparado"); `False` = falló (la subclase ya logueó el
        detalle antes de devolver `False`; la base cuenta `unresolved`, sin
        loguear nada extra).

    Lo que la subclase sigue haciendo en su propio `run()`: chequeo R-0x de
    proceso corriendo, abrir/parsear la librería, encontrar los `broken`, y
    — después de que `_run_resolution` devuelva un `ResolutionResult` — el
    backup + escritura atómica/commit final (y, en Traktor, la sync de
    PLAYLISTS). Ninguno de esos pasos depende del formato de la librería
    de forma "neutral", así que quedan fuera de esta base a propósito.
    """

    log         = pyqtSignal(str)
    progress    = pyqtSignal(int, int)          # (hechas, total)
    ask_user    = pyqtSignal(object)            # RelocateRequest — bloquea el worker
    finished_ok = pyqtSignal(int, int, int, str)  # (reparadas, salteadas, sin_match, status)
    # status: "ok" | "cancelled" | "error" | "blocked"

    def __init__(self, search_root: Path, auto_resolve: bool = False) -> None:
        super().__init__()
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

    # ── Hooks que cada subclase debe implementar ───────────────────────

    def _broken_scope_noun(self) -> str:
        raise NotImplementedError

    def _write_target_name(self) -> str:
        raise NotImplementedError

    def _engine_name(self) -> str:
        raise NotImplementedError

    def _label_for(self, broken_track: Any) -> str:
        raise NotImplementedError

    def _apply_one(self, raw_entry: Any, broken_track: Any, chosen: Path) -> bool:
        raise NotImplementedError

    # ── Loop compartido ─────────────────────────────────────────────────

    def _run_resolution(
        self, broken: list[tuple[Any, Any]],
    ) -> ResolutionResult | None:
        """
        Fase de resolución compartida entre ambos motores: indexa el disco,
        recorre `broken`, decide 0/1/N candidatos (ask_user si corresponde),
        chequea cancelación y emite progreso/log — orden y mensajes
        idénticos a los que tenía cada `run()` antes de este refactor.

        Devuelve `None` si ya terminó todo (emitió `finished_ok` — 0 rotos
        o cancelado) y la subclase debe simplemente `return` sin tocar
        backup/escritura. Devuelve un `ResolutionResult` si hay que seguir
        con el finalize propio del motor (backup + escritura/commit).
        """
        total = len(broken)
        self.log.emit(f"🔍  {total} enlace(s) roto(s) en la {self._broken_scope_noun()}.")
        if total == 0:
            self.finished_ok.emit(0, 0, 0, "ok")
            return None

        self.log.emit(f"📂  Indexando archivos en: {self._search_root}")
        index = build_basename_index(
            self._search_root,
            should_stop=self.isInterruptionRequested,
            # T-007: sin total conocido de antemano (recién se sabe al
            # terminar el walk) — total=0 pone la barra de progreso en modo
            # indeterminado (Qt: min==max) en vez de mostrar un % falso.
            on_progress=lambda n: self.progress.emit(n, 0),
        )
        if self.isInterruptionRequested():
            self._emit_cancelled(0, 0, 0)
            return None
        indexed_count = sum(len(v) for v in index.values())
        self.log.emit(f"   {indexed_count} archivo(s) indexado(s).")
        # T-028: derivado del índice exacto ya construido, sin re-caminar
        # disco (ver build_normalized_index).
        normalized_index = build_normalized_index(index)

        repaired = skipped = unresolved = 0
        for i, (raw_entry, broken_track) in enumerate(broken, start=1):
            if self.isInterruptionRequested():
                self._emit_cancelled(repaired, skipped, unresolved)
                return None

            self.progress.emit(i, total)
            label = self._label_for(broken_track)

            candidates = find_candidates(broken_track, index, normalized_index)
            if not candidates:
                unresolved += 1
                self.log.emit(f"   ✗  Sin coincidencias: {label}")
                continue

            # T-028 (criterio 4): un candidato que matcheó solo por clave
            # normalizada (prefijo NN- y/o extensión tolerados) NUNCA
            # auto-resuelve — ni por ser el único candidato (el atajo de
            # "1 match = se aplica" de ADR-001 p.3 es solo para match
            # EXACTO) ni con el checkbox de auto-resolución (T-003)
            # activo. Es una ampliación de la garantía de ADR-001 p.3: el
            # matching laxo rankea, nunca decide solo.
            normalized_only = candidates[0].match_type == "normalized"

            auto_resolved = False
            if len(candidates) == 1 and not normalized_only:
                chosen: Path | None = candidates[0].path
            elif self._auto_resolve and not normalized_only:
                # Addendum ADR-001 (2026-07-24): opt-in, checkbox OFF por
                # default no pasa por acá. candidates[0] ya viene ordenado
                # por score descendente (find_candidates) — no es orden de
                # carpeta al azar. Sin modal, sin ask_user_event.
                chosen = candidates[0].path
                auto_resolved = True
            elif self._auto_resolve:  # auto_resolve ON + normalized_only
                # Con el checkbox activo la app nunca pregunta (ese es su
                # propósito) — así que acá no hay modal posible: se
                # loguea sin resolver en vez de auto-aplicar un candidato
                # que solo matcheó por tolerancia.
                unresolved += 1
                self.log.emit(
                    f"   ✗  Requiere confirmación manual (coincidencia "
                    f"tolerante, no exacta): {label}"
                )
                continue
            else:
                self._answer_event.clear()
                self.ask_user.emit(RelocateRequest(broken=broken_track, candidates=candidates))
                self._answer_event.wait()
                chosen = self._answer

            if chosen is None:
                skipped += 1
                self.log.emit(f"   ⏭  Salteado: {label}")
                continue

            if self._apply_one(raw_entry, broken_track, chosen):
                repaired += 1
                if auto_resolved:
                    self.log.emit(f"   ✓  Reparado (auto): {label} → {chosen}")
                else:
                    self.log.emit(f"   ✓  Reparado: {label} → {chosen}")
            else:
                unresolved += 1

        return ResolutionResult(repaired=repaired, skipped=skipped, unresolved=unresolved)

    def _cancel_extra_note(self, repaired: int) -> str:
        """
        Nota opcional agregada al log de cancelación cuando el motor
        concreto ya escribió algo a disco pese a que `_write_target_name()`
        sigue intacto (I-6): el mensaje base dice "nada se escribió", cierto
        para Traktor (todo vive en el `ElementTree` en memoria hasta
        `write_atomic`), pero FALSO para Rekordbox si `repaired > 0` — los
        ANLZ de las pistas ya procesadas se escriben a disco por pista,
        antes del commit final de `master.db` (ADR-002 punto 3). Vacío por
        default; Rekordbox lo overridea.
        """
        return ""

    def _emit_cancelled(self, repaired: int, skipped: int, unresolved: int) -> None:
        msg = (
            f"\n⏹  Relocate cancelado — {self._write_target_name()} intacto, "
            "nada se escribió."
        )
        note = self._cancel_extra_note(repaired)
        if note:
            msg += f"\n   {note}"
        self.log.emit(msg)
        self.finished_ok.emit(repaired, skipped, unresolved, "cancelled")

    def _log_final_success(self, repaired: int, skipped: int, unresolved: int) -> None:
        """Log + signal compartidos del cierre exitoso (idénticos en texto
        entre motores salvo el nombre del motor en el log de archivo)."""
        self.log.emit(
            f"\n✓  {repaired} reparada(s) · {skipped} salteada(s) · "
            f"{unresolved} sin coincidencias."
        )
        _log.info(
            "Relocate %s: OK · %d reparadas · %d salteadas · %d sin coincidencias",
            self._engine_name(), repaired, skipped, unresolved,
        )
        self.finished_ok.emit(repaired, skipped, unresolved, "ok")
