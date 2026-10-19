# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2025-2026 Gabriel Maglia
"""T-098 (TEC-20): instancia única con QLockFile en la carpeta de datos.

Procesos reales: uno toma el lock y otro arranca `main.py` de verdad. Solo usan QtCore
(la guarda corre antes de importar la UI), así que también entran en el job de Windows.
"""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest

from _qt_isolated import PROJECT_ROOT, UTF8_ENV

# Primera instancia: toma el lock con el mismo código que usa la app y lo sostiene hasta que el test la suelte.
_HOLDER = """
import sys
from pathlib import Path
import single_instance
guard = single_instance.acquire(Path(sys.argv[1]))
print(guard.status.name, flush=True)
sys.stdin.read()
"""

# Segunda instancia: `main.py` real. Solo se reemplaza el diálogo nativo (bloquearía el test) por un archivo,
# y se simula el bundle para que settings.ini viva en la carpeta de datos (como en la app empaquetada).
_SECOND = """
import runpy, sys
import startup_guard
def fake(title, message, *args, **kwargs):
    open(sys.argv[1], 'w', encoding='utf-8').write(title + '\\n' + message)
startup_guard.show_native_alert = fake
sys.frozen = True
runpy.run_path('main.py', run_name='__main__')
"""

# Para el lock huérfano alcanza con ver que `main` pasa la guarda y llega a cargar Qt: ese paso se corta acá.
_STARTS = """
import importlib, sys
import startup_guard
def fake(title, message, *args, **kwargs):
    open(sys.argv[1], 'w', encoding='utf-8').write(title + '\\n' + message)
startup_guard.show_native_alert = fake
app_main = importlib.import_module('main')
def reached_qt():
    print('ARRANCA', flush=True)
    raise SystemExit(42)
app_main._load_qt_stack = reached_qt
app_main.main()
"""


def _user_env(home: Path) -> dict[str, str]:
    """Carpeta de datos y de logs dentro de `home` en macOS, Windows y Linux."""
    return {
        **os.environ, **UTF8_ENV,
        "HOME": str(home), "USERPROFILE": str(home),
        "APPDATA": str(home / "AppData" / "Roaming"),
        "LOCALAPPDATA": str(home / "AppData" / "Local"),
        "XDG_CONFIG_HOME": str(home / ".config"),
        "QT_QPA_PLATFORM": "offscreen",
        "PYTHONPATH": str(PROJECT_ROOT),
    }


def _data_dir(env: dict[str, str]) -> Path:
    r = subprocess.run([sys.executable, "-c", "import app_paths; print(app_paths.data_dir())"],
                       cwd=PROJECT_ROOT, env=env, capture_output=True, text=True, encoding="utf-8", timeout=60)
    assert r.returncode == 0, r.stderr
    return Path(r.stdout.strip())


def _log_dir_candidates(home: Path) -> list[Path]:
    return [home / "Library" / "Logs" / "listBuddy", home / "AppData" / "Local" / "listBuddy" / "logs",
            home / ".local" / "state" / "listBuddy"]


def _start_holder(data: Path, env: dict[str, str]) -> subprocess.Popen[str]:
    holder = subprocess.Popen([sys.executable, "-c", _HOLDER, str(data)], cwd=PROJECT_ROOT, env=env,
                              stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                              text=True, encoding="utf-8")
    assert holder.stdout is not None
    line = holder.stdout.readline().strip()
    assert line == "ACQUIRED", (line, holder.stderr.read() if holder.poll() is not None else "")
    return holder


def _stop(proc: subprocess.Popen[str]) -> None:
    if proc.poll() is None:
        proc.kill()
    proc.communicate(timeout=30)


def test_second_instance_warns_and_exits_without_touching_log_or_settings(tmp_path: Path) -> None:
    home = tmp_path / "home"
    env = _user_env(home)
    data = _data_dir(env)
    settings = data / "settings.ini"
    settings.write_text("[General]\nlast_dest=/destino\n", encoding="utf-8")
    before = (settings.read_bytes(), settings.stat().st_mtime_ns)
    alert = tmp_path / "alert.txt"

    holder = _start_holder(data, env)
    try:
        try:
            r = subprocess.run([sys.executable, "-c", _SECOND, str(alert)], cwd=PROJECT_ROOT, env=env,
                               capture_output=True, text=True, encoding="utf-8", timeout=30)
            rc, stderr = r.returncode, r.stderr
        except subprocess.TimeoutExpired:   # sin guarda la segunda instancia abre la ventana y no sale nunca
            rc, stderr = None, "la segunda instancia siguió corriendo"
    finally:
        _stop(holder)

    assert rc == 0, stderr
    text = alert.read_text(encoding="utf-8") if alert.exists() else ""
    assert "List Buddy ya está abierto" in text, text
    assert "Traceback" not in stderr
    logs = [p for d in _log_dir_candidates(home) if d.exists() for p in d.iterdir()]
    assert logs == [], logs
    assert (settings.read_bytes(), settings.stat().st_mtime_ns) == before
    assert sorted(p.name for p in data.iterdir()) == ["listBuddy.lock", "settings.ini"]


def test_orphan_lock_from_a_killed_process_does_not_block_startup(tmp_path: Path) -> None:
    home = tmp_path / "home"
    env = _user_env(home)
    data = _data_dir(env)
    holder = _start_holder(data, env)
    holder.kill()   # sin unlock: queda el archivo del lock con el PID de un proceso muerto
    holder.communicate(timeout=30)
    assert (data / "listBuddy.lock").exists()

    alert = tmp_path / "alert.txt"
    r = subprocess.run([sys.executable, "-c", _STARTS, str(alert)], cwd=PROJECT_ROOT, env=env,
                       capture_output=True, text=True, encoding="utf-8", timeout=60)
    assert r.returncode == 42 and "ARRANCA" in r.stdout, (r.returncode, r.stdout, r.stderr)
    assert not alert.exists()


def test_first_instance_releases_the_lock_on_exit(tmp_path: Path) -> None:
    env = _user_env(tmp_path / "home")
    data = _data_dir(env)
    holder = _start_holder(data, env)
    assert holder.stdin is not None
    holder.stdin.close()   # sale normal
    assert holder.wait(timeout=30) == 0
    _stop(_start_holder(data, env))


def test_unwritable_lock_folder_does_not_block_startup(tmp_path: Path) -> None:
    # Si el lock no se puede crear (carpeta inexistente o sin permisos) la app arranca igual: mejor
    # sin guarda que no poder abrirla.
    code = (
        "import sys\nfrom pathlib import Path\nimport single_instance\n"
        "print(single_instance.acquire(Path(sys.argv[1]) / 'no' / 'existe').status.name)\n"
    )
    r = subprocess.run([sys.executable, "-c", code, str(tmp_path)], cwd=PROJECT_ROOT,
                       env=_user_env(tmp_path / "home"), capture_output=True, text=True, encoding="utf-8", timeout=60)
    assert r.returncode == 0 and r.stdout.strip() == "UNAVAILABLE", (r.stdout, r.stderr)


@pytest.mark.parametrize("platform, where", [("darwin", "Dock"), ("win32", "barra de tareas")])
def test_message_is_rioplatense_and_says_where_to_look(platform: str, where: str) -> None:
    import single_instance
    msg = single_instance.already_running_message(platform)
    assert where in msg and "List Buddy" in msg
    assert single_instance.TITLE == "List Buddy ya está abierto"
