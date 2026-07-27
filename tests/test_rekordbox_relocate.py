"""
test_rekordbox_relocate.py
--------------------------
Tests de las piezas puras de rekordbox_relocate.py (ADR-002). El motor real
depende de un master.db SQLCipher y de que Rekordbox esté cerrado, así que acá
solo se cubren las funciones sin efectos de DB:

  - _normalize_folder_path: la normalización `/C/Users/...` → `C:/Users/...`
    que decide si un track está "roto"; un error acá marcaría material sano
    como roto (o al revés).
  - _prune_backups: retención N=5 del backup del master.db (única red de
    rollback de la sesión, ADR-002 punto 1).

No se importa ni abre Rekordbox6Database (no hay clave ni DB en el runner).
"""
from __future__ import annotations

import errno
import os
from pathlib import Path, PureWindowsPath

import pytest

import rekordbox_relocate as rr
from rekordbox_relocate import _normalize_folder_path, backup_master_db


class TestNormalizeFolderPath:
    def test_windows_unix_style_prefix_gets_drive_letter(self):
        # Rekordbox en Windows guarda "/C/Users/..." → "C:/Users/..."
        p = _normalize_folder_path("/C/Users/dj/Music/track.mp3")
        assert PureWindowsPath(p) == PureWindowsPath("C:/Users/dj/Music/track.mp3")

    def test_strips_whitespace(self):
        p = _normalize_folder_path("  /D/Music/t.mp3  ")
        assert str(p).startswith("D:")

    def test_posix_absolute_path_untouched(self):
        # macOS: "/Users/..." no matchea el patrón /X/ de drive → queda igual.
        p = _normalize_folder_path("/Users/dj/Music/track.mp3")
        assert p == Path("/Users/dj/Music/track.mp3")

    def test_already_windows_path_untouched(self):
        p = _normalize_folder_path("C:/Users/dj/t.mp3")
        assert PureWindowsPath(p) == PureWindowsPath("C:/Users/dj/t.mp3")


class TestPruneBackups:
    def test_keeps_only_five(self, tmp_path):
        backups = tmp_path / rr._BACKUP_DIR_NAME
        backups.mkdir()
        for i in range(rr._BACKUP_RETENTION + 4):
            f = backups / f"master.x{i:02d}.db"
            f.write_text("x")
            os.utime(f, (1000 + i, 1000 + i))
        rr._prune_backups(backups)
        assert len(list(backups.glob("master.*.db"))) == rr._BACKUP_RETENTION

    def test_retention_is_five_smaller_than_traktor(self):
        # ADR-002: PO aprobó N=5 (menor al N=10 de Traktor porque el .db
        # cifrado pesa mucho más que un NML).
        assert rr._BACKUP_RETENTION == 5

    def test_removes_oldest_first(self, tmp_path):
        backups = tmp_path / rr._BACKUP_DIR_NAME
        backups.mkdir()
        files = []
        for i in range(rr._BACKUP_RETENTION + 2):
            f = backups / f"master.x{i:02d}.db"
            f.write_text("x")
            os.utime(f, (1000 + i, 1000 + i))
            files.append(f)
        rr._prune_backups(backups)
        assert not files[0].exists()   # más viejo, borrado
        assert files[-1].exists()      # más nuevo, sobrevive


class TestBackupInterruptedByOSError:
    """
    B-3 (T-018): un `OSError` a mitad de `shutil.copy2` (ej. ENOSPC — un
    master.db real pesa decenas a cientos de MB) dejaba antes un
    `master.TIMESTAMP.db` PARCIAL en `listBuddy_backups/`, que
    `_prune_backups` contaba como el backup más reciente — el que el
    usuario elegiría restaurar, perdiendo la librería entera si lo hacía.
    """

    def test_partial_backup_removed_on_copy_failure(self, tmp_path, monkeypatch):
        db = tmp_path / "master.db"
        original = b"FAKE-SQLCIPHER-DB" + b"\x00" * 500
        db.write_bytes(original)

        def fake_copy2(_src, dst):
            # Simula una copia real interrumpida a mitad de camino: el
            # archivo destino existe (parcial, truncado) al fallar.
            Path(dst).write_bytes(b"PARTIAL-GARBAGE")
            raise OSError(errno.ENOSPC, "No space left on device")

        monkeypatch.setattr(rr.shutil, "copy2", fake_copy2)

        with pytest.raises(OSError):
            backup_master_db(db)

        backups_dir = tmp_path / rr._BACKUP_DIR_NAME
        # (b) ningún backup parcial sobrevive en el directorio.
        assert list(backups_dir.glob("master.*.db")) == []
        # (a) el master.db original no se tocó.
        assert db.read_bytes() == original

    def test_insufficient_disk_space_aborts_before_copying(self, tmp_path, monkeypatch):
        db = tmp_path / "master.db"
        db.write_bytes(b"x" * 1000)

        class _Usage:
            free = 0

        monkeypatch.setattr(rr.shutil, "disk_usage", lambda _p: _Usage())

        with pytest.raises(OSError):
            backup_master_db(db)

        backups_dir = tmp_path / rr._BACKUP_DIR_NAME
        assert not backups_dir.exists() or list(backups_dir.glob("master.*.db")) == []
