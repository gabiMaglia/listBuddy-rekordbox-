# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2025-2026 Gabriel Maglia
"""Instancia única (T-098): dos List Buddy abiertos se pisan `settings.ini` y el log.

Usa solo QtCore para poder correr antes de cargar la UI: la segunda instancia sale
rápido y sin tocar nada.
"""
from __future__ import annotations

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
    UNAVAILABLE = auto()   # no se pudo crear el lock: se arranca igual, sin guarda


@dataclass
class InstanceGuard:
    status: LockStatus
    lock: QLockFile | None = None
    detail: str = ""
    host: str = ""
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
        foreign = theirs != ours if theirs and ours else host != QSysInfo.machineHostName()
        if foreign:
            return InstanceGuard(LockStatus.FOREIGN_HOST, host=host, path=path)
        return InstanceGuard(LockStatus.ALREADY_RUNNING, path=path)

    # Vacío o ilegible: huérfano solo si se puede borrar. Una copia viva lo tiene tomado
    # (flock en macOS, archivo abierto en Windows) y ahí el borrado falla: nunca se pisa.
    if lock.removeStaleLockFile() and lock.tryLock(0):
        return InstanceGuard(LockStatus.ACQUIRED, lock, path=path)
    return InstanceGuard(LockStatus.ALREADY_RUNNING, path=path)


def acquire_in_data_dir() -> InstanceGuard:
    try:
        directory = data_dir()
    except OSError as exc:
        return InstanceGuard(LockStatus.UNAVAILABLE, detail=str(exc))
    return acquire(directory)
