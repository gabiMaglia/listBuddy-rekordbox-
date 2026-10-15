"""T-088 (TEC-02/TEC-03): ningún QThread se destruye corriendo.

Qt aborta el proceso (SIGABRT, exit 134) si se destruye un QThread cuyo run()
sigue en ejecución. Estos tests miran el código de salida del intérprete, por
eso corren en un proceso nuevo (cold=True).
"""
from __future__ import annotations

from _qt_isolated import run_isolated
from _window_boot import BOOT

_SLOW_PREVIEW = (
    "import time, preview_worker\n"
    "orig = preview_worker.PreviewWorker._check\n"
    "def slow(self, raw):\n"
    "    time.sleep(0.05); return orig(self, raw)\n"
    "preview_worker.PreviewWorker._check = slow\n"
    "class FakeCard:\n"
    "    def isChecked(self): return True\n"
    "def groups():\n"
    "    rows = [preview_worker.TrackRow(num='%03d' % i, title='t', artist='a', ext='.mp3',\n"
    "            raw_path='/no/existe/%d.mp3' % i) for i in range(30)]\n"
    "    return [preview_worker.GroupData(name='G', order=0, total_count=30, tracks=rows)]\n"
    "def pump(ms):\n"
    "    import time as t\n"
    "    end = t.time() + ms / 1000\n"
    "    while t.time() < end: app.processEvents()\n"
)


def test_retoggling_while_preview_stats_are_slow_does_not_destroy_the_thread() -> None:
    r = run_isolated(
        BOOT + _SLOW_PREVIEW +
        "w, _ = make()\n"
        "w._all_cards = [FakeCard()]\n"
        "w._extract_preview_data = lambda sel: groups()\n"
        "w._start_preview_worker(); pump(200)\n"
        "assert w._preview_worker.isRunning()\n"
        "w._start_preview_worker(); pump(200)\n"
        "w._start_preview_worker(); pump(3500)\n"
        "print('vivo')\n",
        cold=True, timeout=60,
    )
    assert r.returncode == 0, r.stderr[-2000:]
    assert "vivo" in r.stdout


def test_cancelled_preview_worker_does_not_paint_stale_groups() -> None:
    r = run_isolated(
        BOOT + _SLOW_PREVIEW +
        "w, _ = make()\n"
        "w._all_cards = [FakeCard()]\n"
        "w._extract_preview_data = lambda sel: groups()\n"
        "seen = []\n"
        "w._queue_group = lambda g: seen.append(g)\n"
        "w._start_preview_worker(); pump(120)\n"
        "w._all_cards = []\n"
        "w._start_preview_worker(); pump(3000)\n"
        "print('stale', len(seen))\n",
        cold=True, timeout=60,
    )
    assert r.returncode == 0, r.stderr[-2000:]
    assert r.stdout.strip().splitlines()[-1] == "stale 0"


def test_preview_worker_does_not_shadow_qthread_finished() -> None:
    r = run_isolated(
        "from PySide6.QtCore import QThread\n"
        "from preview_worker import PreviewWorker\n"
        "print(PreviewWorker.finished is QThread.finished)\n",
        cold=True,
    )
    assert r.returncode == 0, r.stderr[-2000:]
    assert r.stdout.strip() == "True"


def test_closing_the_window_with_the_update_check_in_flight_exits_cleanly() -> None:
    # `urlopen` simulado lento (DNS colgado): el hilo sigue vivo al cerrar.
    r = run_isolated(
        "import sys, time, urllib.request\n"
        "def slow(*a, **k):\n"
        "    time.sleep(3); raise OSError('sin red')\n"
        "urllib.request.urlopen = slow\n"
        "from PySide6.QtCore import QTimer\n"
        "from PySide6.QtWidgets import QApplication\n"
        "import pathlib, tempfile, styles, ui\n"
        "app = QApplication([]); styles.register_fonts(); styles.apply_theme(app, 'dark')\n"
        "ui.MainWindow._load_playlists = lambda self: None\n"
        "ui.MainWindow._maybe_show_disclaimer = lambda self: None\n"
        "win = ui.MainWindow(settings_path=pathlib.Path(tempfile.mkdtemp()) / 's.ini')\n"
        "win.show()\n"
        "QTimer.singleShot(300, win.close); QTimer.singleShot(400, app.quit)\n"
        "rc = app.exec(); print('exec', rc, flush=True)\n"
        "sys.exit(rc)\n",
        cold=True, timeout=60,
    )
    assert r.returncode == 0, r.stderr[-2000:]
    assert "exec 0" in r.stdout


def test_closing_the_window_while_the_preview_worker_is_running_exits_cleanly() -> None:
    r = run_isolated(
        BOOT + _SLOW_PREVIEW +
        "import sys\n"
        "w, _ = make()\n"
        "w._all_cards = [FakeCard()]\n"
        "w._extract_preview_data = lambda sel: groups()\n"
        "w._start_preview_worker(); pump(150)\n"
        "assert w._preview_worker.isRunning()\n"
        "w._start_preview_worker(); pump(100)\n"   # uno cancelado + uno vivo
        "w.close()\n"
        "print('cerrada', flush=True)\n",
        cold=True, timeout=60,
    )
    assert r.returncode == 0, r.stderr[-2000:]
    assert "cerrada" in r.stdout
