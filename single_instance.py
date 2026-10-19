# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2025-2026 Gabriel Maglia
"""Instancia única (T-098): dos List Buddy abiertos se pisan `settings.ini` y el log.

Usa solo QtCore para poder correr antes de cargar la UI: la segunda instancia sale
rápido y sin tocar nada.
"""
from __future__ import annotations

import os
import sys
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


def acquire(directory: Path) -> InstanceGuard:
    path = directory / LOCK_NAME
    lock = QLockFile(str(path))
    # Lock de toda la vida de la app, sin vencimiento por antigüedad. Qt solo lo da por
    # huérfano si el dueño era de esta máquina y su PID ya no existe; uno de otra máquina
    # no se puede verificar y se respeta aunque deje la app sin abrir (decisión del PO).
    lock.setStaleLockTime(0)
    if lock.tryLock(0):
        return InstanceGuard(LockStatus.ACQUIRED, lock, path=path)
    if lock.error() != QLockFile.LockError.LockFailedError or (path.exists() and not path.is_file()):
        # Sin permisos, o en la ruta hay una carpeta: mejor arrancar sin guarda que no arrancar.
        return InstanceGuard(LockStatus.UNAVAILABLE, detail=f"{lock.error().name} en {path}", path=path)

    pid, host, _app = lock.getLockInfo()
    if pid > 0 and host:
        ours = bytes(QSysInfo.machineUniqueId()).strip()
        theirs = _machine_id_in(path)
        # El id de máquina manda: macOS cambia el hostname con la red y la copia viva quedaría
        # como «otra computadora». El hostname decide solo si falta el id.
        local_host = QSysInfo.machineHostName()
        foreign = theirs != ours if theirs and ours else host != local_host
        if foreign:
            return InstanceGuard(LockStatus.FOREIGN_HOST, host=host, same_name=host == local_host, path=path)

    # De esta máquina, vacío o ilegible. Qt da LockFailedError tanto con un dueño vivo como con
    # un huérfano que no pudo borrar (solo lectura, «Bloqueado», de root): lo que distingue a
    # una copia viva es que tiene tomado el lock (flock en macOS, archivo abierto en Windows).
    if sys.platform != "win32" and _held_by_live_copy(path):
        return InstanceGuard(LockStatus.ALREADY_RUNNING, path=path)
    if lock.removeStaleLockFile() and lock.tryLock(0):
        return InstanceGuard(LockStatus.ACQUIRED, lock, path=path)
    if sys.platform == "win32":
        return _after_failed_delete_on_windows(lock, path)
    # Nunca sin guarda: la próxima vez tampoco la tendría. El aviso dice qué archivo destrabar.
    return InstanceGuard(LockStatus.STUCK_LOCK, path=path)


def _held_by_live_copy(path: Path) -> bool:
    """POSIX: QLockFile mantiene un flock mientras su dueño vive. Se prueba sobre un descriptor
    de solo lectura para que funcione aunque el archivo no tenga permiso de escritura."""
    import fcntl

    try:
        fd = os.open(path, os.O_RDONLY)
    except OSError:
        return False   # ni Qt lo puede abrir: no es de una copia viva de este usuario
    try:
        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        return True
    except OSError:
        return False
    finally:
        os.close(fd)   # cerrar el descriptor suelta el flock de prueba
    return False


_ERROR_SHARING_VIOLATION = 32


def _after_failed_delete_on_windows(lock: QLockFile, path: Path) -> InstanceGuard:
    """Windows: una copia viva tiene el archivo abierto y el borrado falla por «archivo en uso»;
    si falla por permiso (atributo Solo lectura) es un huérfano trabado."""
    try:
        path.unlink()
    except PermissionError as exc:
        if getattr(exc, "winerror", None) == _ERROR_SHARING_VIOLATION:
            return InstanceGuard(LockStatus.ALREADY_RUNNING, path=path)
        return InstanceGuard(LockStatus.STUCK_LOCK, path=path)
    except FileNotFoundError:
        pass
    except OSError:
        return InstanceGuard(LockStatus.STUCK_LOCK, path=path)
    if lock.tryLock(0):
        return InstanceGuard(LockStatus.ACQUIRED, lock, path=path)
    return InstanceGuard(LockStatus.ALREADY_RUNNING, path=path)   # otra copia lo tomó recién


def acquire_in_data_dir() -> InstanceGuard:
    try:
        directory = data_dir()
    except OSError as exc:
        return InstanceGuard(LockStatus.UNAVAILABLE, detail=str(exc))
    return acquire(directory)
