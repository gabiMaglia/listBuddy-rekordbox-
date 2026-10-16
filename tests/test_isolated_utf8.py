from __future__ import annotations

import pytest

from _qt_isolated import run_isolated


def test_run_isolated_survives_a_legacy_console_encoding(monkeypatch: pytest.MonkeyPatch) -> None:
    # Windows (T-112): la consola cp1252 no puede imprimir «▶»; el subproceso debe forzar UTF-8.
    monkeypatch.setenv("PYTHONIOENCODING", "cp1252")
    monkeypatch.delenv("PYTHONUTF8", raising=False)
    r = run_isolated("print('▶ tildes: canción')", cold=True)
    assert r.returncode == 0, r.stderr
    assert r.stdout.strip() == "▶ tildes: canción"
