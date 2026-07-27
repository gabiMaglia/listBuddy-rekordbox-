"""
test_relocate_core.py
----------------------
Tests de las piezas puras compartidas de relocate_core.py (T-017/T-018).

Foco de este archivo: `check_disk_space_for_backup` (B-3, T-018) — el
chequeo de espacio libre ANTES de intentar el backup, mismo patrón que
worker.py ya usa para el export y que el write path sobre la librería del
usuario no tenía hasta este ticket. La otra mitad de B-3 (que un backup
interrumpido a mitad no deje un archivo parcial) se testea en
test_traktor_relocate.py / test_rekordbox_relocate.py, donde viven
backup_collection/backup_master_db.

Se evita instanciar BaseRelocateWorker (QThread) — se testean las
funciones puras, sin event loop de Qt (misma convención que el resto de
la suite).
"""
from __future__ import annotations

import shutil

import pytest

import relocate_core as rc


class TestCheckDiskSpaceForBackup:
    def test_raises_when_insufficient_free_space(self, tmp_path, monkeypatch):
        src = tmp_path / "collection.nml"
        src.write_bytes(b"x" * 1000)  # tamaño irrelevante, se mockea disk_usage

        class _Usage:
            free = 500  # menos que el tamaño del archivo → insuficiente

        monkeypatch.setattr(shutil, "disk_usage", lambda _path: _Usage())

        with pytest.raises(OSError) as exc_info:
            rc.check_disk_space_for_backup(src)
        # El mensaje debe ser legible y en GB, no un traceback crudo.
        assert "GB" in str(exc_info.value)

    def test_passes_when_enough_free_space(self, tmp_path):
        src = tmp_path / "collection.nml"
        src.write_bytes(b"x" * 10)
        # tmp_path real del runner: de sobra para 10 bytes. No debe lanzar.
        rc.check_disk_space_for_backup(src)

    def test_missing_source_does_not_raise_here(self, tmp_path):
        # Si el origen ni siquiera existe, este chequeo no es quien debe
        # fallar — se difiere al intento real de copia, que dará un error
        # más específico (archivo no encontrado, no "sin espacio").
        missing = tmp_path / "no_existe.nml"
        rc.check_disk_space_for_backup(missing)  # no debe lanzar
