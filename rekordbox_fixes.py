# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2025-2026 Gabriel Maglia
"""
rekordbox_fixes.py
------------------
Reparaciones de enlaces de Rekordbox hechas en List Buddy (T-081). Se guardan
en un archivo propio de la app — nunca en el XML ni en Rekordbox (ADR-004):
URI `Location` original del XML → ruta nueva en disco.
"""
from __future__ import annotations

import json
import logging
import os  # noqa: F401  (los tests parchean os.replace a través de este módulo: rf.os)
from pathlib import Path, PurePath

import file_access

_log = logging.getLogger("listBuddy")
_VERSION = 1
# Flavour de «ruta absoluta» = la del SO en curso; los tests lo cambian para simular Windows.
_PURE: type[PurePath] = PurePath


def fixes_path_for(settings_file: Path) -> Path:
    return settings_file.parent / "rekordbox_fixes.json"


class FixStore:
    def __init__(self, path: Path) -> None:
        self.path = path

    def load(self) -> dict[str, str]:
        """Lee las reparaciones; descarta entradas inválidas.

        Estricto: solo se aceptan rutas absolutas del SO actual. En Windows una ruta
        POSIX (`/x/y`) se descarta: el JSON es por máquina (vive en la carpeta de datos
        del usuario), así que no hace falta interpretar rutas de otro sistema.
        """
        try:
            data = json.loads(file_access.read_text(self.path))
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
            elif not isinstance(v, str) or not v or not _PURE(v).is_absolute():
                _log.warning("Reparación descartada para %s: se esperaba una ruta absoluta (%s)",
                             k, type(v).__name__)
            else:
                clean[k] = v
        return clean

    def save(self, mapping: dict[str, str]) -> None:
        file_access.ensure_dir(self.path.parent)
        # Privado (0600 desde el .tmp): lleva las rutas reales de la música del usuario (LEG-23/SEC-22).
        with file_access.atomic_write(self.path, private=True, encoding="utf-8") as f:
            json.dump({"version": _VERSION, "fixes": mapping}, f, ensure_ascii=False, indent=1)

    def merge(self, new: dict[str, str]) -> dict[str, str]:
        merged = self.load()
        merged.update(new)
        self.save(merged)
        return merged

    def clear(self) -> None:
        file_access.remove(self.path)

    def count(self) -> int:
        return len(self.load())
