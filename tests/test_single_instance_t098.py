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
    # Los textos viven en startup_guard (solo stdlib): este test no carga Qt en el proceso de pytest.
    import startup_guard
    msg = startup_guard.already_running_message(platform)
    assert where in msg and "List Buddy" in msg
    assert startup_guard.ALREADY_RUNNING_TITLE == "List Buddy ya está abierto"


def test_foreign_host_message_names_the_host_and_the_full_lock_path() -> None:
    import startup_guard
    lock = Path("/Users/dj/Library/Application Support/listBuddy/listBuddy.lock")
    title, msg = startup_guard.ALREADY_RUNNING_TITLE, startup_guard.foreign_host_message("estudio-pc", lock, "darwin")
    assert "otra computadora" in startup_guard.FOREIGN_HOST_TITLE and title != startup_guard.FOREIGN_HOST_TITLE
    assert "estudio-pc" in msg and str(lock) in msg
    assert "borrá" in msg.lower() or "borrar" in msg.lower()


def test_windows_message_gives_the_folder_alone_on_the_line_after_the_instruction() -> None:
    # D-5 (QA): la ruta completa del lock ya contiene la carpeta; hay que mirar la línea de la instrucción.
    import startup_guard
    from pathlib import PureWindowsPath
    lock = PureWindowsPath(r"C:\Users\dj\AppData\Roaming\listBuddy\listBuddy.lock")
    lines = startup_guard.foreign_host_message("estudio-pc", lock, "win32").splitlines()  # type: ignore[arg-type]
    i = next(n for n, line in enumerate(lines) if "barra de direcciones" in line)
    assert lines[i + 1:i + 2] == [r"C:\Users\dj\AppData\Roaming\listBuddy"], lines


def test_mac_message_offers_a_short_path_to_type() -> None:
    # D-7: el texto de un `display alert` no siempre se puede copiar; la ruta corta se tipea en ⇧⌘G.
    import startup_guard
    lock = Path("/Users/dj/Library/Application Support/listBuddy/listBuddy.lock")
    msg = startup_guard.foreign_host_message("estudio-pc", lock, "darwin")
    how = next(line for line in msg.splitlines() if "⇧⌘G" in line)
    assert "~/Library/Application Support/listBuddy" in how, msg
    assert str(lock) in msg


@pytest.mark.parametrize("platform, lock, how", [
    ("darwin", Path("/Users/dj/Library/Application Support/listBuddy/listBuddy.lock"),
     ("Finder", "Ir a la carpeta", "⇧⌘G")),
    ("win32", Path("C:/Users/dj/AppData/Roaming/listBuddy/listBuddy.lock"),
     ("Explorador", "barra de direcciones", str(Path("C:/Users/dj/AppData/Roaming/listBuddy")))),
])
def test_foreign_host_message_explains_how_to_reach_the_hidden_folder(platform: str, lock: Path,
                                                                      how: tuple[str, ...]) -> None:
    # Addendum 2: la carpeta está oculta (~/Library, %APPDATA%); sin esto el DJ no llega al archivo.
    import startup_guard
    msg = startup_guard.foreign_host_message("estudio-pc", lock, platform)
    assert all(h in msg for h in how), msg
    assert str(lock) in msg
    assert "carpeta de datos" not in msg


# D-1 (QA) con la decisión del PO «Bloquear también en red» (plan T-098 §QUÉ 2-3). El PID es el de
# pytest (vivo): así lo que decide es el host/máquina del lock y no el chequeo de PID de Qt.
_WRITE_LOCK = """
import os, sys
from pathlib import Path
from PySide6.QtCore import QSysInfo
path, kind, pid = Path(sys.argv[1]), sys.argv[2], sys.argv[3]
host = QSysInfo.machineHostName()
uid = bytes(QSysInfo.machineUniqueId()).decode()
if kind == 'directory':
    path.mkdir()
else:
    path.write_bytes({
        'empty': b'',
        'junk': b'\\x00basura\\xff\\nzz',
        'foreign_host': f'{pid}\\nPython\\notra-maquina\\n11111111-2222-3333-4444-555555555555\\n'.encode(),
        'foreign_host_no_id': f'{pid}\\nPython\\notra-maquina\\n'.encode(),
        'foreign_machine': f'{pid}\\nPython\\n{host}\\n00000000-0000-0000-0000-000000000000\\n'.encode(),
    }[kind])
"""


def _write_lock(data: Path, kind: str, env: dict[str, str]) -> None:
    r = subprocess.run([sys.executable, "-c", _WRITE_LOCK, str(data / "listBuddy.lock"), kind, str(os.getpid())],
                       cwd=PROJECT_ROOT, env=env, capture_output=True, text=True, encoding="utf-8", timeout=60)
    assert r.returncode == 0, r.stderr


@pytest.mark.parametrize("kind", ["empty", "junk"])
def test_unreadable_orphan_lock_is_taken_over_and_the_app_starts(tmp_path: Path, kind: str) -> None:
    env = _user_env(tmp_path / "home")
    data = _data_dir(env)
    _write_lock(data, kind, env)
    alert = tmp_path / "alert.txt"
    r = subprocess.run([sys.executable, "-c", _STARTS, str(alert)], cwd=PROJECT_ROOT, env=env,
                       capture_output=True, text=True, encoding="utf-8", timeout=60)
    assert r.returncode == 42 and "ARRANCA" in r.stdout, (r.returncode, r.stdout, r.stderr)
    assert not alert.exists(), alert.read_text(encoding="utf-8")


_HOST = "import sys; from PySide6.QtCore import QSysInfo; print(QSysInfo.machineHostName())"


@pytest.mark.parametrize("kind", ["foreign_host", "foreign_host_no_id", "foreign_machine"])
def test_lock_from_another_computer_blocks_startup_and_names_host_and_path(tmp_path: Path, kind: str) -> None:
    env = _user_env(tmp_path / "home")
    data = _data_dir(env)
    _write_lock(data, kind, env)
    lock = data / "listBuddy.lock"
    before = lock.read_bytes()
    if kind in ("foreign_host", "foreign_host_no_id"):
        host = "otra-maquina"
    else:
        h = subprocess.run([sys.executable, "-c", _HOST], cwd=PROJECT_ROOT, env=env,
                           capture_output=True, text=True, encoding="utf-8", timeout=60)
        host = h.stdout.strip()
    alert = tmp_path / "alert.txt"
    r = subprocess.run([sys.executable, "-c", _STARTS, str(alert)], cwd=PROJECT_ROOT, env=env,
                       capture_output=True, text=True, encoding="utf-8", timeout=60)
    assert r.returncode == 0 and "ARRANCA" not in r.stdout, (r.returncode, r.stdout, r.stderr)
    text = alert.read_text(encoding="utf-8") if alert.exists() else ""
    assert "otra computadora" in text and host in text and str(lock) in text, text
    assert lock.read_bytes() == before   # nunca se toma ni se reescribe el lock ajeno


_RENAME_HOST = """
import sys
from pathlib import Path
p = Path(sys.argv[1])
lines = p.read_bytes().splitlines()
lines[2] = b'MacBook-renombrada-2.local'
p.write_bytes(b'\\n'.join(lines) + b'\\n')
"""


@pytest.mark.parametrize("owner_alive", [True, False])
def test_same_machine_after_a_hostname_change_is_this_computer(tmp_path: Path, owner_alive: bool) -> None:
    # Addendum 2: macOS cambia el hostname con la red (DHCP, «-2» de Bonjour). Mismo id de máquina =
    # esta Mac: con la copia viva es «ya está abierto» (nunca «otra computadora»: el aviso mandaría a
    # borrar el lock y quedarían dos copias); con el PID muerto es un huérfano y arranca.
    env = _user_env(tmp_path / "home")
    data = _data_dir(env)
    holder = _start_holder(data, env)
    try:
        if not owner_alive:
            holder.kill()
            holder.communicate(timeout=30)
        subprocess.run([sys.executable, "-c", _RENAME_HOST, str(data / "listBuddy.lock")], check=True, timeout=60)
        alert = tmp_path / "alert.txt"
        r = subprocess.run([sys.executable, "-c", _STARTS, str(alert)], cwd=PROJECT_ROOT, env=env,
                           capture_output=True, text=True, encoding="utf-8", timeout=60)
    finally:
        _stop(holder)
    text = alert.read_text(encoding="utf-8") if alert.exists() else ""
    if owner_alive:
        assert r.returncode == 0 and "ARRANCA" not in r.stdout, (r.returncode, r.stdout, r.stderr)
        assert "List Buddy ya está abierto" in text and "otra computadora" not in text, text
    else:
        assert r.returncode == 42 and "ARRANCA" in r.stdout, (r.returncode, r.stdout, r.stderr, text)


_DROP_MACHINE_ID = """
import sys
from pathlib import Path
p = Path(sys.argv[1])
p.write_bytes(b'\\n'.join(p.read_bytes().splitlines()[:3]) + b'\\n')
"""


def test_lock_without_machine_id_from_this_host_and_a_live_owner_is_already_running(tmp_path: Path) -> None:
    # D-4 (QA): sin id de máquina decide el hostname; si es este host y la copia vive, «ya está abierto».
    env = _user_env(tmp_path / "home")
    data = _data_dir(env)
    holder = _start_holder(data, env)
    try:
        subprocess.run([sys.executable, "-c", _DROP_MACHINE_ID, str(data / "listBuddy.lock")], check=True, timeout=60)
        assert len((data / "listBuddy.lock").read_bytes().splitlines()) == 3
        alert = tmp_path / "alert.txt"
        r = subprocess.run([sys.executable, "-c", _STARTS, str(alert)], cwd=PROJECT_ROOT, env=env,
                           capture_output=True, text=True, encoding="utf-8", timeout=60)
    finally:
        _stop(holder)
    assert r.returncode == 0 and "ARRANCA" not in r.stdout, (r.returncode, r.stdout, r.stderr)
    text = alert.read_text(encoding="utf-8") if alert.exists() else ""
    assert "List Buddy ya está abierto" in text and "otra computadora" not in text, text


_FLOCK_HOLDER = """
import fcntl, sys
f = open(sys.argv[1], 'r+')
fcntl.flock(f, fcntl.LOCK_EX | fcntl.LOCK_NB)
print('HELD', flush=True)
sys.stdin.read()
"""


def test_empty_lock_held_by_a_live_process_is_never_stolen(tmp_path: Path) -> None:
    # Un lock ilegible solo es huérfano si se puede borrar: si un proceso vivo lo tiene tomado (flock en
    # macOS/Linux; en Windows, archivo abierto) Qt no lo borra y la app avisa en vez de abrir otra copia.
    env = _user_env(tmp_path / "home")
    data = _data_dir(env)
    _write_lock(data, "empty", env)
    holder = subprocess.Popen([sys.executable, "-c", _FLOCK_HOLDER, str(data / "listBuddy.lock")],
                              stdin=subprocess.PIPE, stdout=subprocess.PIPE, text=True, encoding="utf-8")
    try:
        assert holder.stdout is not None and holder.stdout.readline().strip() == "HELD"
        alert = tmp_path / "alert.txt"
        r = subprocess.run([sys.executable, "-c", _STARTS, str(alert)], cwd=PROJECT_ROOT, env=env,
                           capture_output=True, text=True, encoding="utf-8", timeout=60)
    finally:
        _stop(holder)
    assert r.returncode == 0 and "ARRANCA" not in r.stdout, (r.returncode, r.stdout, r.stderr)
    assert "List Buddy ya está abierto" in alert.read_text(encoding="utf-8")


# D-2 (QA): si el lock no se puede crear, `main` arranca igual y lo deja como WARNING en el log.
_STARTS_WITH_LOG = """
import importlib, sys
from types import SimpleNamespace
import startup_guard
def fake(title, message, *args, **kwargs):
    open(sys.argv[1], 'w', encoding='utf-8').write(title + '\\n' + message)
startup_guard.show_native_alert = fake
app_main = importlib.import_module('main')
import app_logging
def reached_ui():
    print('ARRANCA', flush=True)
    raise SystemExit(42)
app_main._load_qt_stack = lambda: SimpleNamespace(
    setup_logging=lambda v: print('LOG=' + str(app_logging.setup_logging(v)), flush=True),
    version='t', install_excepthook=reached_ui)
app_main.main()
"""


@pytest.mark.parametrize("broken", ["lock_is_a_directory", "data_dir_is_a_file"])
def test_main_starts_and_logs_a_warning_when_the_lock_cannot_be_created(tmp_path: Path, broken: str) -> None:
    home = tmp_path / "home"
    env = _user_env(home)
    data = _data_dir(env)
    if broken == "lock_is_a_directory":
        _write_lock(data, "directory", env)
    else:
        data.rmdir()
        data.write_text("no soy una carpeta", encoding="utf-8")
    alert = tmp_path / "alert.txt"
    r = subprocess.run([sys.executable, "-c", _STARTS_WITH_LOG, str(alert)], cwd=PROJECT_ROOT, env=env,
                       capture_output=True, text=True, encoding="utf-8", timeout=60)
    assert r.returncode == 42 and "ARRANCA" in r.stdout, (r.returncode, r.stdout, r.stderr)
    assert not alert.exists()
    log = Path(next(l for l in r.stdout.splitlines() if l.startswith("LOG="))[4:])
    text = log.read_text(encoding="utf-8")
    assert "WARNING" in text and "Sin guarda de instancia única" in text, text
