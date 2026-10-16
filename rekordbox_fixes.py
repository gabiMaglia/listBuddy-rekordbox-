"""
rekordbox_fixes.py
------------------
Reparaciones de enlaces de Rekordbox hechas en List Buddy (T-081). Se guardan
en un archivo propio de la app — nunca en el XML ni en Rekordbox (ADR-004):
URI `Location` original del XML → ruta nueva en disco.
"""
from __future__ import annotations

import contextlib
import json
import logging
import os
from pathlib import Path

from app_paths import make_private

_log = logging.getLogger("listBuddy")
_VERSION = 1


def fixes_path_for(settings_file: Path) -> Path:
    return settings_file.parent / "rekordbox_fixes.json"


class FixStore:
    def __init__(self, path: Path) -> None:
        self.path = path

    def load(self) -> dict[str, str]:
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
        except FileNotFoundError:
            return {}
        except (OSError, ValueError) as e:
            _log.warning("Reparaciones de Rekordbox ilegibles (%s): %s", self.path, e)
            return {}
        fixes = data.get("fixes") if isinstance(data, dict) else None
        if not isinstance(fixes, dict):
            return {}
        # El JSON es editable por el usuario o por otro programa: un valor que no sea
        # una ruta absoluta en texto no se castea con str() (un `1` o una lista se
        # volverían "rutas" inventadas), se descarta y queda dicho en el log.
        clean: dict[str, str] = {}
        for k, v in fixes.items():
            if not isinstance(k, str) or not k:
                _log.warning("Reparación descartada: clave inválida (%r)", k)
            elif not isinstance(v, str) or not v or not Path(v).is_absolute():
                _log.warning("Reparación descartada para %s: se esperaba una ruta absoluta (%s)",
                             k, type(v).__name__)
            else:
                clean[k] = v
        return clean

    def save(self, mapping: dict[str, str]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_name(self.path.name + ".tmp")
        try:
            # Se crea ya en 0600: no hay ventana en la que otro usuario lo lea.
            fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                json.dump({"version": _VERSION, "fixes": mapping}, f, ensure_ascii=False, indent=1)
                f.flush()
                os.fsync(f.fileno())
            os.replace(tmp, self.path)
            # Lleva las rutas reales de la música del usuario (LEG-23/SEC-22).
            make_private(self.path)
        except BaseException:
            with contextlib.suppress(OSError):
                tmp.unlink(missing_ok=True)
            raise

    def merge(self, new: dict[str, str]) -> dict[str, str]:
        merged = self.load()
        merged.update(new)
        self.save(merged)
        return merged

    def clear(self) -> None:
        self.path.unlink(missing_ok=True)

    def count(self) -> int:
        return len(self.load())
