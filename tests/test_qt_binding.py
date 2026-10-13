"""T-033: el código propio usa PySide6 (LGPL), nunca PyQt6 (GPL) — ADR-003."""
from __future__ import annotations

import ast
from pathlib import Path

import pytest

from _qt_isolated import PROJECT_ROOT, run_isolated

# .claude guarda worktrees de agentes con copias viejas del código: no son del proyecto.
_EXCLUDED_DIRS = {".venv", "venv", "build", "dist", ".git", "__pycache__", ".claude"}


def _project_py_files() -> list[Path]:
    return [
        p for p in PROJECT_ROOT.rglob("*.py")
        if not _EXCLUDED_DIRS.intersection(p.relative_to(PROJECT_ROOT).parts)
        and not p.relative_to(PROJECT_ROOT).parts[0].startswith(".venv")  # .venv-1 etc.: ruido del entorno
    ]


def _imported_roots(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    roots: set[str] = set()
    # ast.walk incluye imports diferidos dentro de funciones (app_logging, ui).
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            roots.update(a.name.split(".")[0] for a in node.names)
        elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
            roots.add(node.module.split(".")[0])
    return roots


def test_no_project_file_imports_pyqt6() -> None:
    offenders = sorted(
        str(p.relative_to(PROJECT_ROOT))
        for p in _project_py_files()
        if "PyQt6" in _imported_roots(p)
    )
    assert offenders == []


# (módulo, clase, señal) — una por cada archivo que declara señales.
_SIGNAL_OWNERS = [
    ("worker", "ExportWorker", "log"),
    ("preview_worker", "PreviewWorker", "group_ready"),
    ("relocate_core", "RestoreBackupWorker", "finished_ok"),
    ("relocate_core", "BaseRelocateWorker", "ask_user"),
    ("update_checker", "UpdateCheckWorker", "update_available"),
    ("audio_player", "AudioPlayer", "position_changed"),
    ("waveform_worker", "WaveformWorker", "ready"),
    ("ui_components", "SeekBar", "seek_requested"),
    ("ui_components", "WaveformSeek", "seek_requested"),
    ("footer", "FooterBar", "export_clicked"),
]


@pytest.mark.parametrize(("module", "cls", "signal"), _SIGNAL_OWNERS)
def test_project_signals_are_pyside6(module: str, cls: str, signal: str) -> None:
    proc = run_isolated(f"""
        import sys
        import {module} as m
        from PySide6.QtCore import Signal
        sig = getattr(m.{cls}, "{signal}")
        print("PYQT6_LOADED" if "PyQt6" in sys.modules else "PYQT6_ABSENT")
        print("IS_PYSIDE_SIGNAL" if isinstance(sig, Signal) else type(sig).__module__)
    """)
    assert proc.returncode == 0, proc.stderr
    assert proc.stdout.split() == ["PYQT6_ABSENT", "IS_PYSIDE_SIGNAL"]
