# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2025-2026 Gabriel Maglia
"""
file_access.py
--------------
Único punto por el que la app lee la librería elegida (XML/NML) y escribe exports,
backups y archivos propios (T-120, ADR-008).

En la distribución directa no agrega nada: cada función hace exactamente lo que hacía
el código que reemplaza. Existe para que una versión con sandbox (Mac App Store, 1.2)
pueda pedir y renovar permisos en un solo lugar en vez de perseguir cada `open()` por
la app; `tests/test_file_access_ast_t120.py` impide abrir rutas por fuera de acá.

Capa L0 (ADR-007 D1): solo stdlib y `app_paths`, sin Qt.
"""
from __future__ import annotations

import contextlib
import os
import shutil
from collections.abc import Iterator
from pathlib import Path
from typing import IO, Any, BinaryIO

from app_paths import make_private


def open_read(path: Path) -> BinaryIO:
    """Abre en binario un archivo que eligió el usuario (XML de Rekordbox, NML, backup)."""
    return open(path, "rb")


def read_text(path: Path, *, encoding: str = "utf-8") -> str:
    return Path(path).read_text(encoding=encoding)


def write_text(path: Path, text: str, *, encoding: str = "utf-8") -> None:
    Path(path).write_text(text, encoding=encoding)


def ensure_dir(path: Path) -> None:
    """Crea la carpeta (y sus padres) si falta: destino del export, `listBuddy_backups/`."""
    Path(path).mkdir(parents=True, exist_ok=True)


def copy_file(src: Path, dest: Path) -> None:
    """Copia con metadatos. Si falla a mitad borra el destino parcial: un backup
    truncado no puede quedar haciéndose pasar por el más reciente."""
    try:
        shutil.copy2(src, dest)
    except OSError:
        with contextlib.suppress(OSError):
            Path(dest).unlink(missing_ok=True)
        raise


def remove(path: Path, *, missing_ok: bool = True) -> None:
    """Borra un archivo (`.part` cortado, backup podado, reparaciones)."""
    Path(path).unlink(missing_ok=missing_ok)


@contextlib.contextmanager
def atomic_write(
    dest: Path, *, tmp_suffix: str = ".tmp", private: bool = False, encoding: str | None = None,
    errors: str | None = None,
) -> Iterator[IO[Any]]:
    """Escribe en `<dest><tmp_suffix>` (misma carpeta), fsync y `os.replace`.

    Si algo falla, también una excepción del bloque `with`, el temporal se borra y
    `dest` queda como estaba. `private` crea el temporal ya en 0600 (sin ventana en la
    que otro usuario lo lea) y deja `dest` en 0600. Con `encoding` el archivo es de
    texto con los fines de línea de la plataforma (CRLF en Windows), igual que `open(..., "w")`;
    sin él, binario.
    """
    dest = Path(dest)
    tmp = dest.with_name(dest.name + tmp_suffix)
    mode = "w" if encoding else "wb"
    try:
        if private:
            fh: IO[Any] = os.fdopen(os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600),
                                    mode, encoding=encoding, errors=errors)
        else:
            fh = open(tmp, mode, encoding=encoding, errors=errors)
        with fh:
            yield fh
            fh.flush()
            os.fsync(fh.fileno())
        os.replace(tmp, dest)
        if private:
            make_private(dest)
    except BaseException:
        with contextlib.suppress(OSError):
            tmp.unlink(missing_ok=True)
        raise


def atomic_copy(src: Path, dest: Path, *, tmp_suffix: str = ".tmp") -> None:
    """Reemplaza `dest` por una copia de `src` sin pasar nunca por un `dest` a medio
    escribir (restaurar un backup sobre la colección)."""
    with open_read(src) as fsrc, atomic_write(dest, tmp_suffix=tmp_suffix) as fdst:
        shutil.copyfileobj(fsrc, fdst)
