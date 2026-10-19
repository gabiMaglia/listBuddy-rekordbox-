# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2025-2026 Gabriel Maglia
"""Instancia única (T-098): dos List Buddy abiertos se pisan `settings.ini` y el log.

Usa solo QtCore para poder correr antes de cargar la UI: la segunda instancia sale
rápido y sin tocar nada.
"""
from __future__ import annotations

import os
import stat
import sys
import time
from dataclasses import dataclass
from enum import Enum, auto
from pathlib import Path

from PySide6.QtCore import QLockFile, QSysInfo

from app_paths import data_dir

LOCK_NAME = "listBuddy.lock"


class LockStatus(Enum):
    ACQUIRED = auto()
    ALREADY_RUNNING = auto()
    FOREIGN_HOST = auto()  # lock de otra computadora (carpeta en red, perfil roaming): no se arranca
    STUCK_LOCK = auto()    # huérfano que no se puede borrar (solo lectura, «Bloqueado», de root): no se arranca
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
        lines = path.read_bytes().splitlines()
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
_ERROR_SHARING_VIOLATION = 32


def acquire(directory: Path) -> InstanceGuard:
    path = directory / LOCK_NAME
    lock = QLockFile(str(path))
    # Lock de toda la vida de la app, sin vencimiento por antigüedad. Qt solo lo da por
    # huérfano si el dueño era de esta máquina y su PID ya no existe; uno de otra máquina
    # no se puede verificar y se respeta aunque deje la app sin abrir (decisión del PO).
    lock.setStaleLockTime(0)
    structural_in_a_row = 0
    stuck_every_pass = True   # en cada pasada: existía, nadie lo tenía y no se pudo borrar
    owner_unknown = False
    for _ in range(_PASSES):
        if lock.tryLock(0):
            return InstanceGuard(LockStatus.ACQUIRED, lock, path=path)
        if _structurally_impossible(directory, path):
            structural_in_a_row += 1
            if structural_in_a_row >= 2:
                return InstanceGuard(LockStatus.UNAVAILABLE, detail=f"{lock.error().name} en {path}", path=path)
            stuck_every_pass = False
            time.sleep(_PAUSE_S)
            continue
        structural_in_a_row = 0
        if lock.error() != QLockFile.LockError.LockFailedError:
            stuck_every_pass = False   # transitorio: se reintenta
            time.sleep(_PAUSE_S)
            continue

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

    if stuck_every_pass:
        # Nunca sin guarda: la próxima vez tampoco la tendría. El aviso dice qué archivo destrabar.
        return InstanceGuard(LockStatus.STUCK_LOCK, path=path, owner_unknown=owner_unknown)
    return InstanceGuard(LockStatus.ALREADY_RUNNING, path=path)


def _structurally_impossible(directory: Path, path: Path) -> bool:
    """La ruta del lock no es un archivo, o no hay lock y la carpeta no deja crearlo. Un solo
    lstat: dos chequeos separados ven estados a medias mientras otra instancia lo borra."""
    try:
        st = os.lstat(path)
    except FileNotFoundError:
        st = None
    except OSError:
        return False
    if st is not None:
        return not stat.S_ISREG(st.st_mode)
    return not directory.is_dir() or not os.access(directory, os.W_OK)


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
        path.unlink()
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
