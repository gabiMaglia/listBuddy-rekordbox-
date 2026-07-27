"""
test_restore_backup.py
------------------------
Tests de la lógica de restauración de backups (B-4, T-019) — la mitad
"correctitud" del ticket, la única que es testeable de forma aislada sin
Qt (la UI — botón, RestoreBackupDialog, QMessageBox de confirmación — no
se testea acá, misma convención que el resto de la suite: solo lógica pura
que puede corromper datos del usuario).

Cubre:
  - `list_backups`: listado + parseo de timestamp desde el nombre de
    archivo + orden (más reciente primero) + robustez ante nombres que no
    matchean el formato esperado.
  - `restore_backup`: camino feliz (el archivo real termina con el
    contenido del backup), atomicidad ante fallo a mitad de copia (el
    archivo real queda INTACTO y no queda un `.tmp` colgado) y que el
    chequeo de espacio insuficiente aborta ANTES de tocar nada.
  - `check_disk_space_for_backup(..., write_dir=...)`: la generalización
    que reusa `restore_backup` para chequear espacio en la carpeta del
    archivo real, no en la del backup.
"""
from __future__ import annotations

import shutil

import pytest

import relocate_core as rc


class TestListBackups:
    def test_missing_backups_dir_returns_empty(self, tmp_path):
        target = tmp_path / "master.db"
        assert rc.list_backups(target, "master.*.db") == []

    def test_lists_sorted_newest_first_by_parsed_timestamp(self, tmp_path):
        target = tmp_path / "master.db"
        backups_dir = tmp_path / "listBuddy_backups"
        backups_dir.mkdir()
        (backups_dir / "master.20260101-000000.db").write_bytes(b"a")
        (backups_dir / "master.20260301-000000.db").write_bytes(b"bb")
        (backups_dir / "master.20260201-000000.db").write_bytes(b"ccc")

        result = rc.list_backups(target, "master.*.db")

        assert [b.path.name for b in result] == [
            "master.20260301-000000.db",
            "master.20260201-000000.db",
            "master.20260101-000000.db",
        ]
        assert result[0].size == 2  # b"bb"

    def test_glob_pattern_isolates_engine(self, tmp_path):
        # Traktor y Rekordbox comparten `_BACKUP_DIR_NAME` pero no deben
        # mezclar sus listados — el glob_pattern es lo que los separa.
        target = tmp_path / "master.db"
        backups_dir = tmp_path / "listBuddy_backups"
        backups_dir.mkdir()
        (backups_dir / "master.20260101-000000.db").write_bytes(b"a")
        (backups_dir / "collection.20260101-000000.nml").write_bytes(b"b")

        result = rc.list_backups(target, "master.*.db")

        assert len(result) == 1
        assert result[0].path.name == "master.20260101-000000.db"

    def test_unparseable_name_gets_none_timestamp_and_sorts_last(self, tmp_path):
        target = tmp_path / "master.db"
        backups_dir = tmp_path / "listBuddy_backups"
        backups_dir.mkdir()
        (backups_dir / "master.20260101-000000.db").write_bytes(b"a")
        (backups_dir / "master.weird-name.db").write_bytes(b"b")

        result = rc.list_backups(target, "master.*.db")

        assert result[0].timestamp is not None
        assert result[-1].timestamp is None
        assert result[-1].path.name == "master.weird-name.db"


class TestRestoreBackup:
    def test_happy_path_replaces_target_with_backup_content(self, tmp_path):
        target = tmp_path / "master.db"
        target.write_bytes(b"OLD-CONTENT")
        backups_dir = tmp_path / "listBuddy_backups"
        backups_dir.mkdir()
        backup = backups_dir / "master.20260101-000000.db"
        backup.write_bytes(b"BACKUP-CONTENT")

        rc.restore_backup(backup, target)

        assert target.read_bytes() == b"BACKUP-CONTENT"
        assert not (target.parent / (target.name + ".restoretmp")).exists()

    def test_failure_mid_copy_leaves_target_intact_and_no_tmp_leftover(
        self, tmp_path, monkeypatch,
    ):
        target = tmp_path / "master.db"
        target.write_bytes(b"OLD-CONTENT")
        backups_dir = tmp_path / "listBuddy_backups"
        backups_dir.mkdir()
        backup = backups_dir / "master.20260101-000000.db"
        backup.write_bytes(b"BACKUP-CONTENT")

        def _boom(*_args, **_kwargs):
            raise OSError("disco lleno simulado")

        monkeypatch.setattr(shutil, "copyfileobj", _boom)

        with pytest.raises(OSError):
            rc.restore_backup(backup, target)

        # El archivo real NUNCA se tocó in-place: sigue con su contenido
        # de antes de intentar restaurar.
        assert target.read_bytes() == b"OLD-CONTENT"
        assert not (target.parent / (target.name + ".restoretmp")).exists()

    def test_insufficient_space_aborts_before_touching_target(
        self, tmp_path, monkeypatch,
    ):
        target = tmp_path / "master.db"
        target.write_bytes(b"OLD-CONTENT")
        backups_dir = tmp_path / "listBuddy_backups"
        backups_dir.mkdir()
        backup = backups_dir / "master.20260101-000000.db"
        backup.write_bytes(b"x" * 1000)

        class _Usage:
            free = 10  # menos que el tamaño del backup

        monkeypatch.setattr(shutil, "disk_usage", lambda _path: _Usage())

        with pytest.raises(OSError) as exc_info:
            rc.restore_backup(backup, target)

        assert "restauración" in str(exc_info.value)
        assert "GB" in str(exc_info.value)
        assert target.read_bytes() == b"OLD-CONTENT"
        assert not (target.parent / (target.name + ".restoretmp")).exists()


class TestCheckDiskSpaceWriteDirOverride:
    def test_checks_free_space_at_write_dir_not_src_parent(self, tmp_path, monkeypatch):
        # El backup vive en listBuddy_backups/, pero lo que importa para
        # restaurar es el espacio libre en la carpeta del archivo REAL
        # (target_path.parent) — que puede, en principio, resolverse
        # distinto de src.parent.
        src = tmp_path / "listBuddy_backups" / "master.20260101-000000.db"
        src.parent.mkdir()
        src.write_bytes(b"x" * 1000)
        write_dir = tmp_path  # simula target_path.parent

        seen_paths: list[str] = []

        def _disk_usage(path):
            seen_paths.append(path)

            class _Usage:
                free = 10  # insuficiente a propósito

            return _Usage()

        monkeypatch.setattr(shutil, "disk_usage", _disk_usage)

        with pytest.raises(OSError) as exc_info:
            rc.check_disk_space_for_backup(
                src, write_dir=write_dir, action="la restauración",
            )

        assert seen_paths == [str(write_dir)]
        assert "la restauración" in str(exc_info.value)

    def test_default_write_dir_still_uses_src_parent(self, tmp_path):
        # Comportamiento histórico sin tocar (backup_collection/
        # backup_master_db siguen llamando sin write_dir).
        src = tmp_path / "collection.nml"
        src.write_bytes(b"x" * 10)
        rc.check_disk_space_for_backup(src)  # no debe lanzar
