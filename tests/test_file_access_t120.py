# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2025-2026 Gabriel Maglia
"""T-120: `file_access.py`, la costura de acceso a disco (no-op en la distribución directa).

Lo que importa acá es que la costura se porte igual que el código que reemplaza: escritura
atómica que no deja `.tmp` ni pisa el destino si falla, 0600 cuando el archivo es privado y
lectura binaria del XML/NML tal cual está en disco.
"""
from __future__ import annotations

import ast
import os
import stat
import sys
from pathlib import Path

import pytest

import file_access as fa

ROOT = Path(__file__).resolve().parents[1]


def test_open_read_returns_the_raw_bytes(tmp_path: Path) -> None:
    p = tmp_path / "c.nml"
    p.write_bytes(b"<NML>\r\n\xc3\xb1</NML>")
    with fa.open_read(p) as fh:
        assert fh.read() == b"<NML>\r\n\xc3\xb1</NML>"


def test_read_and_write_text_round_trip(tmp_path: Path) -> None:
    p = tmp_path / "r.txt"
    fa.write_text(p, "ñandú\n")
    assert fa.read_text(p) == "ñandú\n"


def test_ensure_dir_creates_parents_and_tolerates_existing(tmp_path: Path) -> None:
    d = tmp_path / "a" / "listBuddy_backups"
    fa.ensure_dir(d)
    fa.ensure_dir(d)
    assert d.is_dir()


def test_atomic_write_replaces_the_destination(tmp_path: Path) -> None:
    dest = tmp_path / "o.xml"
    dest.write_bytes(b"viejo")
    with fa.atomic_write(dest) as fh:
        fh.write(b"nuevo")
    assert dest.read_bytes() == b"nuevo"
    assert not list(tmp_path.glob("*.tmp"))


def test_atomic_write_uses_the_requested_temp_suffix(tmp_path: Path) -> None:
    dest = tmp_path / "collection.nml"
    seen: list[bool] = []
    with fa.atomic_write(dest, tmp_suffix=".restoretmp") as fh:
        fh.write(b"x")
        seen.append((tmp_path / "collection.nml.restoretmp").exists())
    assert seen == [True]


def test_atomic_write_failure_after_tmp_keeps_destination_and_removes_tmp(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    dest = tmp_path / "o.xml"
    dest.write_bytes(b"viejo")

    def boom(src: str, dst: str) -> None:
        assert Path(src).read_bytes() == b"nuevo"     # el .tmp ya está escrito cuando falla
        raise OSError("disco lleno")

    monkeypatch.setattr(os, "replace", boom)
    with pytest.raises(OSError, match="disco lleno"):
        with fa.atomic_write(dest) as fh:
            fh.write(b"nuevo")
    assert dest.read_bytes() == b"viejo"
    assert not (tmp_path / "o.xml.tmp").exists()


def test_atomic_write_exception_in_body_removes_tmp(tmp_path: Path) -> None:
    dest = tmp_path / "o.xml"
    with pytest.raises(KeyboardInterrupt):
        with fa.atomic_write(dest) as fh:
            fh.write(b"a medias")
            raise KeyboardInterrupt
    assert not dest.exists()
    assert not (tmp_path / "o.xml.tmp").exists()


def test_atomic_write_text_mode_writes_text(tmp_path: Path) -> None:
    dest = tmp_path / "f.json"
    with fa.atomic_write(dest, encoding="utf-8") as fh:
        fh.write('{"a": "ñ"}')
    assert dest.read_text(encoding="utf-8") == '{"a": "ñ"}'


@pytest.mark.skipif(sys.platform.startswith("win"), reason="permisos POSIX")
def test_private_atomic_write_creates_tmp_and_destination_0600(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    dest = tmp_path / "rekordbox_fixes.json"
    dest.write_text("{}")
    dest.chmod(0o644)
    modes: list[int] = []
    real_replace = os.replace

    def spy(src: str, dst: str) -> None:
        modes.append(stat.S_IMODE(os.stat(src).st_mode))
        real_replace(src, dst)

    monkeypatch.setattr(os, "replace", spy)
    with fa.atomic_write(dest, private=True, encoding="utf-8") as fh:
        fh.write("{}")
    assert modes == [0o600]                           # sin ventana en la que otro lo lea
    assert stat.S_IMODE(dest.stat().st_mode) == 0o600


def test_copy_file_copies_and_removes_a_partial_copy_on_failure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    import shutil

    src = tmp_path / "collection.nml"
    src.write_bytes(b"<NML/>")
    dest = tmp_path / "b" / "collection.x.nml"
    fa.ensure_dir(dest.parent)
    fa.copy_file(src, dest)
    assert dest.read_bytes() == b"<NML/>"

    broken = tmp_path / "b" / "collection.y.nml"

    def fake_copy2(_s: object, d: object) -> None:
        Path(str(d)).write_text("PARCIAL")
        raise OSError("disco lleno")

    monkeypatch.setattr(shutil, "copy2", fake_copy2)
    with pytest.raises(OSError):
        fa.copy_file(src, broken)
    assert not broken.exists()


def test_atomic_copy_failure_mid_copy_keeps_destination_and_removes_tmp(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    import shutil

    src = tmp_path / "backup.nml"
    src.write_bytes(b"BACKUP")
    dest = tmp_path / "collection.nml"
    dest.write_bytes(b"VIEJO")
    fa.atomic_copy(src, dest, tmp_suffix=".restoretmp")
    assert dest.read_bytes() == b"BACKUP"

    dest.write_bytes(b"VIEJO")

    def boom(fsrc: object, fdst: object) -> None:
        assert (tmp_path / "collection.nml.restoretmp").exists()
        raise OSError("disco lleno")

    monkeypatch.setattr(shutil, "copyfileobj", boom)
    with pytest.raises(OSError):
        fa.atomic_copy(src, dest, tmp_suffix=".restoretmp")
    assert dest.read_bytes() == b"VIEJO"
    assert not (tmp_path / "collection.nml.restoretmp").exists()


def test_file_access_is_pure_stdlib_without_qt() -> None:
    """Capa L0 (ADR-007 D1): sin Qt; de lo propio solo `app_paths` (L0)."""
    tree = ast.parse((ROOT / "file_access.py").read_text(encoding="utf-8"))
    local = {p.stem for p in ROOT.glob("*.py")}
    imported: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported |= {a.name.split(".")[0] for a in node.names}
        elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
            imported.add(node.module.split(".")[0])
    assert not {"PySide6", "PyQt6", "shiboken6"} & imported
    assert (imported & local) <= {"app_paths"}
    assert all(m in sys.stdlib_module_names or m in local or m == "__future__" for m in imported)
