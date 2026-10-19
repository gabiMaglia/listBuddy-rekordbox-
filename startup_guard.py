# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2025-2026 Gabriel Maglia
"""Guarda de arranque: si Qt no carga, avisa con un diálogo nativo (sin Qt) y sale con 1.

Solo stdlib: tiene que funcionar justo cuando PySide6 está roto, p. ej. en un macOS
más viejo que el mínimo (14.4) que piden los frameworks de Qt 6.12.
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path
from typing import Callable, TypeVar

T = TypeVar("T")

RELEASES_URL = "https://github.com/gabiMaglia/listbuddy/releases"
TITLE = "List Buddy no pudo abrirse"
_MAX_DETAIL = 300


# Instancia única (T-098). Viven acá porque se muestran con el diálogo nativo, antes de cargar la UI.
ALREADY_RUNNING_TITLE = "List Buddy ya está abierto"
FOREIGN_HOST_TITLE = "List Buddy figura abierto en otra computadora"


def already_running_message(platform: str = sys.platform) -> str:
    where = "en el Dock" if platform == "darwin" else "en la barra de tareas"
    return (
        "Ya hay una ventana de List Buddy abierta y no se pueden usar dos a la vez.\n\n"
        f"Buscala {where} y seguí ahí."
    )


def foreign_host_message(host: str, lock_path: Path) -> str:
    return (
        f"List Buddy figura abierto en otra computadora ({host}) que usa esta misma carpeta de datos. "
        "Para no pisar tu configuración, acá no se abre.\n\n"
        "Si en esa computadora no está abierto, borrá este archivo y volvé a abrir List Buddy:\n"
        f"{lock_path}"
    )


def build_message(exc: BaseException) -> str:
    # Solo la primera línea del error: el resto suele ser ruido de dyld.
    detail = (str(exc).strip().splitlines() or [type(exc).__name__])[0][:_MAX_DETAIL]
    return (
        "List Buddy necesita macOS 14.4 o posterior.\n\n"
        f"Error: {detail}\n\n"
        f"Si tu Mac es más vieja, bajá una versión compatible desde {RELEASES_URL}"
    )


# Íconos del aviso: nombre de AppleScript y su MB_ICON* de Windows.
_WIN_ICONS = {"critical": 0x10, "warning": 0x30, "informational": 0x40}


def osascript_command(title: str, message: str, icon: str = "critical") -> list[str]:
    def esc(s: str) -> str:
        return s.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n")

    script = f'display alert "{esc(title)}" message "{esc(message)}" as {icon}'
    return ["osascript", "-e", script]


def show_native_alert(title: str, message: str, icon: str = "critical") -> None:
    """Diálogo nativo sin Qt; si no se puede, cae a stderr (sin traceback)."""
    try:
        if sys.platform == "darwin":
            subprocess.run(osascript_command(title, message, icon), check=True, timeout=300,
                           capture_output=True)
            return
        if sys.platform == "win32":
            import ctypes
            ctypes.windll.user32.MessageBoxW(0, message, title, _WIN_ICONS[icon])
            return
    except Exception:
        pass
    print(f"{title}\n{message}", file=sys.stderr)


def guarded_import(loader: Callable[[], T], show: Callable[[str, str], None] | None = None) -> T:
    """Corre `loader` (los imports de Qt); ante ImportError/OSError avisa y sale con 1."""
    try:
        return loader()
    except (ImportError, OSError) as exc:
        # Se busca en el módulo al llamar, así un test puede reemplazar show_native_alert.
        (show or show_native_alert)(TITLE, build_message(exc))
        raise SystemExit(1) from None
