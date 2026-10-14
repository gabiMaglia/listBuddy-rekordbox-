"""Carpetas por usuario de la app (configuración y datos propios), por OS."""
from __future__ import annotations

import os
import sys
from pathlib import Path


def data_dir() -> Path:
    """Carpeta de datos de la app: fuera del bundle, escribible y por usuario."""
    if sys.platform == "darwin":
        d = Path.home() / "Library" / "Application Support" / "listBuddy"
    elif sys.platform.startswith("win"):
        d = Path(os.environ.get("APPDATA") or Path.home()) / "listBuddy"
    else:
        d = Path(os.environ.get("XDG_CONFIG_HOME") or Path.home() / ".config") / "listBuddy"
    d.mkdir(parents=True, exist_ok=True)
    return d


def default_settings_path(frozen: bool | None = None) -> Path:
    """Empaquetada: carpeta de datos (el bundle es de solo lectura y está firmado).
    Desde el código: `.rbe_settings.ini` junto al código, como siempre."""
    if frozen is None:
        frozen = bool(getattr(sys, "frozen", False))
    if frozen:
        return data_dir() / "settings.ini"
    return Path(__file__).parent / ".rbe_settings.ini"
