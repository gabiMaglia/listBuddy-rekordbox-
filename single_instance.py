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

from PySide6.QtCore import QLockFile

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


def acquire(directory: Path) -> InstanceGuard:
    lock = QLockFile(str(directory / LOCK_NAME))
    # Lock de toda la vida de la app: sin vencimiento por antigüedad. Si el dueño murió
    # (crash, kill), tryLock lo detecta por PID y lo reemplaza solo.
    lock.setStaleLockTime(0)
    if lock.tryLock(0):
        return InstanceGuard(LockStatus.ACQUIRED, lock)
    if lock.error() == QLockFile.LockError.LockFailedError:
        return InstanceGuard(LockStatus.ALREADY_RUNNING)
    return InstanceGuard(LockStatus.UNAVAILABLE, detail=f"{lock.error().name} en {lock.fileName()}")


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
