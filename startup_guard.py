# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2025-2026 Gabriel Maglia
"""Guarda de arranque: si Qt no carga, avisa con un diálogo nativo (sin Qt) y sale con 1.

Solo stdlib: tiene que funcionar justo cuando PySide6 está roto, p. ej. en un macOS
más viejo que el mínimo (14.4) que piden los frameworks de Qt 6.12.
"""
from __future__ import annotations

import subprocess
import sys
from typing import Callable, TypeVar

T = TypeVar("T")

RELEASES_URL = "https://github.com/gabiMaglia/listbuddy/releases"
TITLE = "List Buddy no pudo abrirse"
_MAX_DETAIL = 300


def build_message(exc: BaseException) -> str:
    # Solo la primera línea del error: el resto suele ser ruido de dyld.
    detail = (str(exc).strip().splitlines() or [type(exc).__name__])[0][:_MAX_DETAIL]
    return (
        "List Buddy necesita macOS 14.4 o posterior.\n\n"
        f"Error: {detail}\n\n"
        f"Si tu Mac es más vieja, bajá una versión compatible desde {RELEASES_URL}"
    )


def osascript_command(title: str, message: str) -> list[str]:
    def esc(s: str) -> str:
        return s.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n")

    script = f'display alert "{esc(title)}" message "{esc(message)}" as critical'
    return ["osascript", "-e", script]


def show_native_alert(title: str, message: str) -> None:
    """Diálogo nativo sin Qt; si no se puede, cae a stderr (sin traceback)."""
    try:
        if sys.platform == "darwin":
            subprocess.run(osascript_command(title, message), check=True, timeout=300,
                           capture_output=True)
            return
        if sys.platform == "win32":
            import ctypes
            ctypes.windll.user32.MessageBoxW(0, message, title, 0x10)  # MB_ICONERROR
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
