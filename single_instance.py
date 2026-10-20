# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2025-2026 Gabriel Maglia
"""Instancia única (T-098): dos List Buddy abiertos se pisan `settings.ini` y el log.

Usa solo QtCore para poder correr antes de cargar la UI: la segunda instancia sale
rápido y sin tocar nada.
"""
from __future__ import annotations

import errno
import os
import stat
import sys
import time
from dataclasses import dataclass
from enum import Enum, auto
from pathlib import Path

from PySide6.QtCore import QLockFile, QSysInfo

import file_access
from app_paths import data_dir

LOCK_NAME = "listBuddy.lock"


class LockStatus(Enum):
    ACQUIRED = auto()
    ALREADY_RUNNING = auto()
    FOREIGN_HOST = auto()  # lock de otra computadora (carpeta en red, perfil roaming): no se arranca
    STUCK_LOCK = auto()    # huérfano que no se puede borrar (solo lectura, «Bloqueado», de root): no se arranca
    NO_SPACE = auto()      # no hay lugar en el disco (o la cuota) para crear el lock: no se arranca
    CANT_CREATE = auto()   # el lock no se pudo crear por otro motivo, en todas las pasadas: no se arranca
    UNAVAILABLE = auto()   # no se pudo crear el lock: se arranca igual, sin guarda


@dataclass
class InstanceGuard:
    status: LockStatus
    lock: QLockFile | None = None
    detail: str = ""
    host: str = ""
    same_name: bool = False   # otra máquina con el mismo hostname que esta
    owner_unknown: bool = False   # STUCK_LOCK que ni se pudo abrir: no se sabe si hay una copia viva
    path: Path | None = None

    def release(self) -> None:
        if self.lock is not None and self.lock.isLocked():
            self.lock.unlock()


def _machine_id_in(path: Path) -> bytes:
    # 4.ª línea del lock de Qt 6: id de máquina. Mismo hostname no garantiza misma máquina.
    try:
        with file_access.open_read(path) as f:
            lines = f.read().splitlines()
    except OSError:
        return b""
    return lines[3].strip() if len(lines) > 3 else b""


class Owner(Enum):
    """Lo que dice el lock sobre su dueño, sondeado sin tomarlo."""
    HELD = auto()        # una copia viva lo tiene tomado (flock)
    FREE = auto()        # existe y nadie lo tiene
    UNREADABLE = auto()  # no se puede abrir para sondear: no se sabe
    MISSING = auto()     # desapareció entre medio (otra instancia lo borró)
    UNKNOWN = auto()     # Windows: no hay flock; se sabe recién al intentar borrarlo


# Plan T-098, Addendum 4: la adquisición es un bucle acotado. Con lanzamientos simultáneos el lock
# cambia mientras se lo mira (otra instancia lo borra o lo recrea); ningún estado visto una sola vez
# alcanza para abrir sin guarda, y lo que no se estabiliza se resuelve sin abrir.
_PASSES = 10
_PAUSE_S = 0.02
_CONFIRM_PASSES = 2   # un estado que decide el desenlace tiene que repetirse al menos en dos pasadas
_ERROR_SHARING_VIOLATION = 32


def acquire(directory: Path) -> InstanceGuard:
    path = directory / LOCK_NAME
    lock = QLockFile(str(path))
    # Lock de toda la vida de la app, sin vencimiento por antigüedad. Qt solo lo da por
    # huérfano si el dueño era de esta máquina y su PID ya no existe; uno de otra máquina
    # no se puede verificar y se respeta aunque deje la app sin abrir (decisión del PO).
    lock.setStaleLockTime(0)
    structural_in_a_row = 0
    stuck_every_pass = True          # en cada pasada: existía, nadie lo tenía y no se pudo borrar
    # Racha de las ÚLTIMAS pasadas en que el lock no existía y Qt no lo pudo crear (Addendum 5). Una
    # pasada de otro tipo la corta: un huérfano borrado al principio no puede tapar un disco lleno
    # después (verificador 3).
    create_fail_streak = 0
    streak_no_space = True
    create_detail = ""
    owner_unknown = False
    for _ in range(_PASSES):
        if lock.tryLock(0):
            return InstanceGuard(LockStatus.ACQUIRED, lock, path=path)
        kind = _entry_kind(path)
        if _structurally_impossible(directory, path, kind):
            structural_in_a_row += 1
            if structural_in_a_row >= 2:
                return InstanceGuard(LockStatus.UNAVAILABLE, detail=f"{lock.error().name} en {path}", path=path)
            stuck_every_pass = False
            create_fail_streak = 0
            time.sleep(_PAUSE_S)
            continue
        structural_in_a_row = 0
        if kind is Entry.SYMLINK:
            # Qt no lo reemplaza y no es algo que haya creado la app: trabado, con la ruta en el aviso.
            create_fail_streak = 0
            owner_unknown = True
            time.sleep(_PAUSE_S)
            continue
        if lock.error() != QLockFile.LockError.LockFailedError:
            stuck_every_pass = False
            if kind is Entry.MISSING:
                problem = _creation_problem(directory)
                no_space = problem is not None and _is_no_space(problem)
                streak_no_space = no_space if create_fail_streak == 0 else streak_no_space and no_space
                create_fail_streak += 1
                create_detail = problem.strerror or str(problem) if problem is not None else lock.error().name
            else:
                create_fail_streak = 0   # existe y Qt falla: ambiguo, se reintenta
            time.sleep(_PAUSE_S)
            continue
        create_fail_streak = 0

        foreign = _foreign_owner(lock, path)
        if foreign is not None:
            return foreign

        # De esta máquina, vacío o ilegible. Qt da LockFailedError tanto con un dueño vivo como
        # con un huérfano que no pudo borrar: lo que distingue a una copia viva es que tiene
        # tomado el lock (flock en macOS, archivo abierto en Windows).
        owner = _probe_owner(path)
        if owner is Owner.HELD:
            return InstanceGuard(LockStatus.ALREADY_RUNNING, path=path)
        if owner is Owner.MISSING:
            stuck_every_pass = False
            continue
        owner_unknown = owner_unknown or owner is Owner.UNREADABLE
        if lock.removeStaleLockFile():
            stuck_every_pass = False
            continue   # huérfano borrado: la próxima pasada lo toma (o ve quién le ganó)
        if sys.platform == "win32":
            verdict = _delete_on_windows(path)
            if verdict is Owner.HELD:
                return InstanceGuard(LockStatus.ALREADY_RUNNING, path=path)
            if verdict is not Owner.FREE:
                stuck_every_pass = False
                continue
        time.sleep(_PAUSE_S)

    # Ningún desenlace abre sin guarda, y ninguno dice «ya está abierto» si se sabe que no hay copia viva.
    if create_fail_streak >= _CONFIRM_PASSES:
        if streak_no_space:
            return InstanceGuard(LockStatus.NO_SPACE, path=path)
        return InstanceGuard(LockStatus.CANT_CREATE, detail=create_detail, path=path)
    if stuck_every_pass:
        # La próxima vez tampoco tendría guarda. El aviso dice qué archivo destrabar.
        return InstanceGuard(LockStatus.STUCK_LOCK, path=path, owner_unknown=owner_unknown)
    return InstanceGuard(LockStatus.ALREADY_RUNNING, path=path)


class Entry(Enum):
    MISSING = auto()
    REGULAR = auto()
    SYMLINK = auto()
    OTHER = auto()     # carpeta, FIFO, dispositivo
    UNKNOWN = auto()   # lstat falló por otro motivo


def _entry_kind(path: Path) -> Entry:
    try:
        st = os.lstat(path)
    except FileNotFoundError:
        return Entry.MISSING
    except OSError:
        return Entry.UNKNOWN
    if stat.S_ISLNK(st.st_mode):
        return Entry.SYMLINK
    return Entry.REGULAR if stat.S_ISREG(st.st_mode) else Entry.OTHER


_NO_SPACE_ERRNOS = {errno.ENOSPC} | ({errno.EDQUOT} if hasattr(errno, "EDQUOT") else set())
# ERROR_HANDLE_DISK_FULL, ERROR_DISK_FULL, ERROR_DISK_QUOTA_EXCEEDED
_NO_SPACE_WINERRORS = {39, 112, 1295}


def _is_no_space(exc: OSError) -> bool:
    return exc.errno in _NO_SPACE_ERRNOS or getattr(exc, "winerror", None) in _NO_SPACE_WINERRORS


# APFS reserva lugar para metadatos: con el disco lleno un archivo vacío todavía se crea y
# recién escribir contenido da ENOSPC (QA intento 6).
_PROBE_BYTES = 512


def _creation_problem(directory: Path) -> OSError | None:
    """Qt solo dice «UnknownError»: se intenta escribir un archivo al lado para saber por qué
    (sin espacio, cuota, E/S). No es el lock: otra instancia nunca lo confunde con uno."""
    probe = directory / f".{LOCK_NAME}.{os.getpid()}.probe"
    problem: OSError | None = None
    try:
        file_access.write_text(probe, "x" * _PROBE_BYTES)
    except OSError as exc:
        problem = exc
    try:
        file_access.remove(probe)   # también si la escritura falló a mitad: no dejar basura
    except OSError:
        pass
    return problem


def _structurally_impossible(directory: Path, path: Path, kind: Entry | None = None) -> bool:
    """En la ruta del lock hay una carpeta (u otra cosa que no es archivo ni symlink), o no hay
    lock y la carpeta no deja crearlo. Un solo lstat: dos chequeos separados ven estados a medias
    mientras otra instancia lo borra."""
    kind = _entry_kind(path) if kind is None else kind
    if kind is Entry.OTHER:
        return True
    if kind is Entry.MISSING:
        return not directory.is_dir() or not os.access(directory, os.W_OK)
    return False


def _foreign_owner(lock: QLockFile, path: Path) -> InstanceGuard | None:
    pid, host, _app = lock.getLockInfo()
    if pid <= 0 or not host:
        return None
    ours = bytes(QSysInfo.machineUniqueId()).strip()
    theirs = _machine_id_in(path)
    # El id de máquina manda: macOS cambia el hostname con la red y la copia viva quedaría
    # como «otra computadora». El hostname decide solo si falta el id.
    local_host = QSysInfo.machineHostName()
    foreign = theirs != ours if theirs and ours else host != local_host
    if not foreign:
        return None
    return InstanceGuard(LockStatus.FOREIGN_HOST, host=host, same_name=host == local_host, path=path)


def _probe_owner(path: Path) -> Owner:
    """POSIX: QLockFile mantiene un flock mientras su dueño vive. Se prueba sobre un descriptor
    de solo lectura para que funcione aunque el archivo no tenga permiso de escritura."""
    if sys.platform == "win32":
        return Owner.UNKNOWN
    import fcntl

    try:
        fd = os.open(path, os.O_RDONLY)
    except FileNotFoundError:
        return Owner.MISSING
    except OSError:
        return Owner.UNREADABLE
    try:
        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        return Owner.HELD
    except OSError:
        return Owner.UNREADABLE
    finally:
        os.close(fd)   # cerrar el descriptor suelta el flock de prueba
    return Owner.FREE


def _delete_on_windows(path: Path) -> Owner:
    """Windows: una copia viva tiene el archivo abierto y el borrado falla por «archivo en uso»;
    si falla por permiso (atributo Solo lectura) es un huérfano trabado (FREE)."""
    try:
        file_access.remove(path, missing_ok=False)
    except FileNotFoundError:
        return Owner.MISSING
    except PermissionError as exc:
        if getattr(exc, "winerror", None) == _ERROR_SHARING_VIOLATION:
            return Owner.HELD
        return Owner.FREE
    except OSError:
        return Owner.FREE
    return Owner.MISSING   # lo borramos: la próxima pasada lo toma


def acquire_in_data_dir() -> InstanceGuard:
    try:
        directory = data_dir()
    except OSError:
        # Que la carpeta de datos no se pueda crear se confirma en una segunda pasada (Addendum 4.3).
        time.sleep(_PAUSE_S)
        try:
            directory = data_dir()
        except OSError as exc:
            return InstanceGuard(LockStatus.UNAVAILABLE, detail=str(exc))
    return acquire(directory)
