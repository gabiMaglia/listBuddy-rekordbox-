"""Corre snippets Qt en un intérprete aparte.

Mientras PyQt6 siga instalado, importar un módulo del proyecto y PySide6 en el
mismo proceso cargaría dos copias de las DLL de Qt 6.12.0: el subproceso lo evita
y además mantiene limpio el proceso de pytest.
"""
from __future__ import annotations

import os
import re
import atexit
import json
import select
import subprocess
import sys
import textwrap
from pathlib import Path

from _window_boot import BOOT

PROJECT_ROOT = Path(__file__).resolve().parent.parent

# Módulos del proyecto que importan QtWidgets/QtGui/QtMultimedia/QtSvg: arrancan GUI real. Los que solo usan
# QtCore (worker, preview_worker, library_load_worker...) corren en cualquier plataforma con PySide6 instalado.
# tests/test_windows_subset.py exige que esta lista cubra todos los módulos GUI del repo.
GUI_MODULES = ("about_dialog", "app_logging", "audio_decode", "audio_player", "dialogs", "footer", "icons", "main",
               "preview_card", "styles", "ui", "ui_components", "waveform_worker")
GUI_SNIPPET = re.compile(
    r"\bBOOT\b|\bQApplication\b|\bQt(Widgets|Gui|Multimedia|Svg)\b"
    r"|\bfrom\s+(" + "|".join(GUI_MODULES) + r")\b"
    # `import json, styles`: el módulo GUI puede ir en cualquier posición de la lista del import
    r"|\bimport\s+(?:[\w.]+(?:\s+as\s+\w+)?\s*,\s*)*(" + "|".join(GUI_MODULES) + r")\b"
)


def looks_like_gui(code: str) -> bool:
    return GUI_SNIPPET.search(code) is not None


_warm: subprocess.Popen[str] | None = None


def _kill_warm() -> None:
    global _warm
    if _warm is not None:
        _warm.kill()
        _warm.wait()
        _warm = None


atexit.register(_kill_warm)


def _run_warm(code: str, timeout: float) -> subprocess.CompletedProcess[str]:
    """Snippet de ventana en el intérprete Qt reutilizable (ver _qt_warm_worker)."""
    global _warm
    if _warm is None or _warm.poll() is not None:
        env = {**os.environ, "QT_QPA_PLATFORM": "offscreen", "PYTHONPATH": str(PROJECT_ROOT)}
        _warm = subprocess.Popen(
            [sys.executable, str(Path(__file__).with_name("_qt_warm_worker.py"))],
            cwd=PROJECT_ROOT, env=env, text=True, bufsize=1,
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=None,
        )
    assert _warm.stdin is not None and _warm.stdout is not None
    try:
        _warm.stdin.write(json.dumps({"code": textwrap.dedent(code)}) + "\n")
        _warm.stdin.flush()
    except BrokenPipeError:
        pass
    ready, _, _ = select.select([_warm.stdout], [], [], timeout)
    if not ready:
        _kill_warm()
        raise subprocess.TimeoutExpired("qt-warm-worker", timeout)
    line = _warm.stdout.readline()
    if not line:  # el worker murió (p. ej. SIGSEGV): igual que un subproceso que cae
        rc = _warm.wait()
        _warm = None
        return subprocess.CompletedProcess([], rc, "", f"el intérprete Qt murió con código {rc}")
    msg = json.loads(line)
    return subprocess.CompletedProcess([], msg["rc"], msg["stdout"], msg["stderr"])


def run_isolated(code: str, timeout: float = 60.0, cold: bool = False) -> subprocess.CompletedProcess[str]:
    """`cold=True` fuerza un proceso nuevo (tests que miran stderr/crash del arranque)."""
    if os.environ.get("LISTBUDDY_NO_QT") == "1" and looks_like_gui(code):   # job de Windows (T-108)
        raise RuntimeError("LISTBUDDY_NO_QT=1: este test abre GUI de Qt y debería estar marcado `qt` (tests/conftest.py)")
    if not cold and code.startswith(BOOT):
        return _run_warm(code, timeout)
    env = {
        **os.environ,
        "QT_QPA_PLATFORM": "offscreen",
        "PYTHONPATH": str(PROJECT_ROOT),
    }
    return subprocess.run(
        [sys.executable, "-c", textwrap.dedent(code)],
        cwd=PROJECT_ROOT,
        env=env,
        capture_output=True,
        text=True,
        timeout=timeout,
    )
