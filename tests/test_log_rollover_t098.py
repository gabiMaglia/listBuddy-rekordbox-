# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2025-2026 Gabriel Maglia
"""T-098: el log no rompe la app si Windows no deja rotarlo (archivo abierto por otro proceso)."""
from __future__ import annotations

import logging
from pathlib import Path

import pytest

import app_logging


def _record(i: int) -> logging.LogRecord:
    return logging.LogRecord("listBuddy", logging.INFO, __file__, 1, "línea %d " + "x" * 80, (i,), None)


def test_handler_opens_the_file_lazily(tmp_path: Path) -> None:
    path = tmp_path / "listBuddy.log"
    h = app_logging.make_file_handler(path)
    try:
        assert not path.exists()
        h.emit(_record(1))
        assert path.exists()
    finally:
        h.close()


def test_rollover_permission_error_keeps_logging_to_the_same_file(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    path = tmp_path / "listBuddy.log"
    h = app_logging.make_file_handler(path, max_bytes=300)
    errors: list[logging.LogRecord] = []
    monkeypatch.setattr(h, "handleError", errors.append)

    def locked(source: str, dest: str) -> None:   # lo que hace Windows si otro proceso tiene el log abierto
        raise PermissionError(32, "El proceso no tiene acceso al archivo", source)

    monkeypatch.setattr(h, "rotate", locked)
    try:
        for i in range(20):
            h.emit(_record(i))
    finally:
        h.close()
    assert errors == []
    text = path.read_text(encoding="utf-8")
    assert all(f"línea {i} " in text for i in range(20))
    assert not path.with_name("listBuddy.log.1").exists()


def test_normal_rollover_still_rotates(tmp_path: Path) -> None:
    path = tmp_path / "listBuddy.log"
    h = app_logging.make_file_handler(path, max_bytes=300)
    try:
        for i in range(20):
            h.emit(_record(i))
    finally:
        h.close()
    assert path.with_name("listBuddy.log.1").exists()


def test_failed_rollover_is_not_retried_in_the_same_session(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    # D-3 (QA): reintentar en cada línea sería un rename fallido por registro y una nota repetida.
    path = tmp_path / "listBuddy.log"
    h = app_logging.make_file_handler(path, max_bytes=300)
    calls: list[str] = []

    def locked(source: str, dest: str) -> None:
        calls.append(dest)
        raise PermissionError(32, "El proceso no tiene acceso al archivo", source)

    monkeypatch.setattr(h, "rotate", locked)
    try:
        for i in range(20):
            h.emit(_record(i))
    finally:
        h.close()
    assert len(calls) == 1, calls
    assert path.read_text(encoding="utf-8").count("no se pudo rotar el log") == 1
