# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2025-2026 Gabriel Maglia
"""Instancia única (T-098): dos List Buddy abiertos se pisan `settings.ini` y el log.

Usa solo QtCore para poder correr antes de cargar la UI: la segunda instancia sale
rápido y sin tocar nada.
"""
from __future__ import annotations

import sys
from dataclasses import dataclass
from enum import Enum, auto
from pathlib import Path

from PySide6.QtCore import QLockFile, QSysInfo

from app_paths import data_dir

LOCK_NAME = "listBuddy.lock"
TITLE = "List Buddy ya está abierto"


class LockStatus(Enum):
    ACQUIRED = auto()
    ALREADY_RUNNING = auto()
    UNAVAILABLE = auto()   # no se pudo crear el lock: se arranca igual, sin guarda


@dataclass
class InstanceGuard:
    status: LockStatus
    lock: QLockFile | None = None
    detail: str = ""

    def release(self) -> None:
        if self.lock is not None and self.lock.isLocked():
            self.lock.unlock()


def _owner_is_unknowable(lock: QLockFile, path: Path) -> bool:
    """El lock no se puede atribuir a un proceso de esta máquina: vacío, con basura o de otro host.

    Qt solo comprueba el PID si el lock es de esta máquina; si no, con `setStaleLockTime(0)`
    no lo considera viejo nunca y la app quedaría bloqueada para siempre (perfil roaming de
    Windows tras un crash, carpeta de datos copiada de otra Mac, archivo truncado)."""
    pid, host, _app = lock.getLockInfo()
    if pid <= 0 or not host:
        return True
    if host != QSysInfo.machineHostName():
        return True
    # La 4.ª línea es el id de máquina que escribe Qt 6: mismo hostname no es misma máquina.
    try:
        lines = path.read_bytes().splitlines()
    except OSError:
        return False
    theirs = lines[3].strip() if len(lines) > 3 else b""
    ours = bytes(QSysInfo.machineUniqueId()).strip()
    return bool(theirs and ours and theirs != ours)


def acquire(directory: Path) -> InstanceGuard:
    path = directory / LOCK_NAME
    lock = QLockFile(str(path))
    # Lock de toda la vida de la app, sin vencimiento por antigüedad: si no, otra instancia
    # podría robárselo a una ventana abierta hace horas. Un dueño muerto de esta máquina lo
    # detecta tryLock por PID; uno que no se puede atribuir lo resuelve _owner_is_unknowable.
    lock.setStaleLockTime(0)
    if lock.tryLock(0):
        return InstanceGuard(LockStatus.ACQUIRED, lock)
    if lock.error() != QLockFile.LockError.LockFailedError:
        return InstanceGuard(LockStatus.UNAVAILABLE, detail=f"{lock.error().name} en {lock.fileName()}")
    if not _owner_is_unknowable(lock, path):
        return InstanceGuard(LockStatus.ALREADY_RUNNING)
    # removeStaleLockFile no borra un lock que un proceso vivo tiene tomado (flock en
    # macOS, archivo abierto en Windows), así que no pisa a un dueño real.
    if lock.removeStaleLockFile() and lock.tryLock(0):
        return InstanceGuard(LockStatus.ACQUIRED, lock)
    # Mejor arrancar sin guarda que no poder abrir la app nunca.
    return InstanceGuard(LockStatus.UNAVAILABLE, detail=f"lock ilegible o ajeno que no se pudo reemplazar: {path}")


def acquire_in_data_dir() -> InstanceGuard:
    try:
        directory = data_dir()
    except OSError as exc:
        return InstanceGuard(LockStatus.UNAVAILABLE, detail=str(exc))
    return acquire(directory)


def already_running_message(platform: str = sys.platform) -> str:
    where = "en el Dock" if platform == "darwin" else "en la barra de tareas"
    return (
        "Ya hay una ventana de List Buddy abierta y no se pueden usar dos a la vez.\n\n"
        f"Buscala {where} y seguí ahí."
    )
