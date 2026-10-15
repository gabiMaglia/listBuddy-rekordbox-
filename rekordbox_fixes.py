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
        return {str(k): str(v) for k, v in fixes.items()}

    def save(self, mapping: dict[str, str]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_name(self.path.name + ".tmp")
        try:
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump({"version": _VERSION, "fixes": mapping}, f, ensure_ascii=False, indent=1)
                f.flush()
                os.fsync(f.fileno())
            os.replace(tmp, self.path)
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
