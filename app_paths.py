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
    make_private(d)
    return d


def default_settings_path(frozen: bool | None = None) -> Path:
    """Empaquetada: carpeta de datos (el bundle es de solo lectura y está firmado).
    Desde el código: `.rbe_settings.ini` junto al código, como siempre."""
    if frozen is None:
        frozen = bool(getattr(sys, "frozen", False))
    if frozen:
        return data_dir() / "settings.ini"
    return Path(__file__).parent / ".rbe_settings.ini"


def make_private(path: Path, *, create: bool = False) -> None:
    """Deja `path` legible solo por el usuario (0600; 0700 si es una carpeta) en POSIX; en Windows no hace nada
    (ahí el perfil del usuario ya es privado). `create` lo crea vacío si falta, para
    que Qt (QSaveFile) conserve el modo al reescribirlo. Es del propio usuario, así
    que un archivo viejo con 0644 se ajusta sin avisar."""
    if sys.platform.startswith("win"):
        return
    try:
        if create and not path.exists():
            os.close(os.open(path, os.O_CREAT | os.O_WRONLY, 0o600))
        if path.exists():
            path.chmod(0o700 if path.is_dir() else 0o600)
    except OSError:
        pass  # filesystem sin permisos POSIX (FAT/red): no es motivo para no arrancar
