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

import os
from pathlib import Path, PureWindowsPath

import rekordbox_relocate as rr
from rekordbox_relocate import _normalize_folder_path


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
