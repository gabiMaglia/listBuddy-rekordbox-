"""T-105 (verifier ciego): carreras de cierre, último click y latencia del log."""
from __future__ import annotations

from _qt_isolated import run_isolated
from _window_boot import BOOT

_PRE = (
    "import pathlib, tempfile, threading\n"
    "from types import SimpleNamespace\n"
    "from PySide6.QtCore import QThread, Signal\n"
    "import worker, preview_worker\n"
    "def pump(ms):\n"
    "    end = time.time() + ms / 1000\n"
    "    while time.time() < end: app.processEvents()\n"
    "def slow_check(delay):\n"
    "    orig = worker.DestinationCheck.run\n"
    "    def run(self): time.sleep(delay); orig(self)\n"
    "    worker.DestinationCheck.run = run\n"
    "started = []\n"
    "class FakeExport(QThread):\n"
    "    log = Signal(str); progress = Signal(int, int); finished_ok = Signal(int, int, int, str)\n"
    "    def __init__(self, *a, **k): super().__init__(); started.append(1)\n"
    "    def run(self): time.sleep(1)\n"
    "ui.ExportWorker = FakeExport\n"
)


def _go(code: str, timeout: int = 40):
    return run_isolated(BOOT + _PRE + code, cold=True, timeout=timeout)


def test_close_with_a_pending_destination_check_never_starts_the_export() -> None:  # V1
    r = _go(
        "slow_check(0.5)\n"
        "w, _ = make()\n"
        "w._footer.set_dest(tempfile.mkdtemp()); w._selected_playlists = lambda: [object()]\n"
        "w._start_export(); w.close(); pump(1500)\n"
        "print('started', len(started), flush=True)\n"
    )
    assert r.returncode == 0, r.stderr[-1500:]
    assert "Destroyed while thread" not in r.stderr
    assert r.stdout.strip().splitlines()[-1] == "started 0"


def test_close_right_after_a_play_click_plays_nothing_and_starts_no_waveform() -> None:  # V2
    r = _go(
        "f = pathlib.Path(tempfile.mkdtemp()) / 'a.mp3'; f.write_bytes(b'x')\n"
        "w, _ = make(); played, waves = [], []\n"
        "w._audio = SimpleNamespace(play=lambda p: played.append(p), toggle=lambda: None,\n"
        "                           current_path=lambda: '', stop=lambda: None)\n"
        "w._start_waveform = lambda p: waves.append(p)\n"
        "w._play_file_row(None, str(f)); w.close(); pump(800)\n"
        "print('played', len(played), len(waves), flush=True)\n"
    )
    assert r.returncode == 0, r.stderr[-1500:]
    assert r.stdout.strip().splitlines()[-1] == "played 0 0"


def test_clicking_the_track_that_is_already_playing_cancels_a_late_resolution() -> None:  # V3
    r = _go(
        "d = pathlib.Path(tempfile.mkdtemp()); fa, fb = d / 'A.mp3', d / 'B.mp3'\n"
        "fa.write_bytes(b'x'); fb.write_bytes(b'x')\n"
        "orig = preview_worker.PlayResolveWorker.run\n"
        "def slow(self):\n"
        "    if self._raw.endswith('B.mp3'): time.sleep(0.5)\n"
        "    orig(self)\n"
        "preview_worker.PlayResolveWorker.run = slow\n"
        "w, _ = make(); played, toggled = [], []\n"
        "w._audio = SimpleNamespace(play=lambda p: played.append(p), toggle=lambda: toggled.append(1),\n"
        "                           current_path=lambda: str(fa), stop=lambda: None)\n"
        "w._start_waveform = lambda p: None\n"
        "w._playing_path = str(fa)\n"
        "w._play_file_row(None, str(fb)); w._play_file_row(None, str(fa)); pump(1200)\n"
        "print('r', len(played), len(toggled), flush=True)\n"
    )
    assert r.returncode == 0, r.stderr[-1500:]
    assert r.stdout.strip().splitlines()[-1] == "r 0 1"


def test_close_does_not_hang_on_read_only_load_or_destination_threads() -> None:  # V4
    r = _go(
        "import library_load_worker\n"
        "class HungLoad(library_load_worker.LibraryLoadWorker):\n"
        "    def __init__(self): QThread.__init__(self)\n"
        "    def run(self): time.sleep(30)\n"
        "class HungDest(worker.DestinationCheck):\n"
        "    def __init__(self): QThread.__init__(self)\n"
        "    def run(self): time.sleep(30)\n"
        "w, _ = make()\n"
        "for cls in (HungLoad, HungDest):\n"
        "    t = cls(); w._retain_thread(t); t.start()\n"
        "pump(100); print('cierro', flush=True); w.close()\n",
        timeout=25,
    )
    assert r.returncode == 0, r.stderr[-1500:]
    assert "Destroyed while thread" not in r.stderr


def test_export_button_shows_status_while_the_destination_is_checked_and_relocate_still_blocks() -> None:  # V5
    r = _go(
        "slow_check(0.4)\n"
        "ui.dialogs.warning = staticmethod(lambda *a, **k: None)\n"
        "w, _ = make()\n"
        "w._footer.set_dest(tempfile.mkdtemp()); w._selected_playlists = lambda: [object()]\n"
        "w._start_export()\n"
        "status = w.output_status.text()\n"
        "w._relocate_worker = SimpleNamespace(isRunning=lambda: True)\n"
        "pump(1000)\n"
        "w._relocate_worker = None\n"
        "print(status, len(started), w._dest_check is None, flush=True)\n"
    )
    assert r.returncode == 0, r.stderr[-1500:]
    assert r.stdout.strip().splitlines()[-1] == "Verificando destino… 0 True"


def test_log_lines_do_not_wait_for_the_next_long_copy() -> None:  # V6
    r = run_isolated(
        "import pathlib, tempfile, time\n"
        "from PySide6.QtCore import QCoreApplication, QTimer\n"
        "app = QCoreApplication([])\n"
        "import rekordbox_xml as rx, worker\n"
        "tmp = pathlib.Path(tempfile.mkdtemp()); out = tmp / 'out'; out.mkdir()\n"
        "src = tmp / 's.mp3'; src.write_bytes(b'x' * 10)\n"
        "tracks = [rx.RbxTrack(title=f'T{i}', artist='A', file_path=src, TrackNo=i + 1) for i in range(3)]\n"
        "pl = rx.RbxPlaylist(name='Mix', ID='1', tracks=tracks)\n"
        "real = worker._copy_stream; n = [0]\n"
        "def slow(a, b, c):\n"
        "    n[0] += 1\n"
        "    if n[0] == 3:\n        for _ in range(15): time.sleep(0.1); c()\n"
        "    real(a, b, c)\n"
        "worker._copy_stream = slow\n"
        "w = worker.ExportWorker([pl], out); seen = []\n"
        "t0 = time.monotonic()\n"
        "w.log.connect(lambda t: seen.append((time.monotonic() - t0, t)))\n"
        "w.finished_ok.connect(lambda *a: app.quit())\n"
        "w.start(); app.exec(); w.wait()\n"
        "first = next(dt for dt, t in seen if 'Mix' in t)\n"
        "print('ok' if first < 0.8 else f'tarde {first:.2f}')\n",
        cold=True, timeout=40,
    )
    assert r.returncode == 0, r.stderr[-1500:]
    assert r.stdout.strip().splitlines()[-1] == "ok"


_CALLBACKS = [
    "w._on_relocate_finished(3, 0, 0, 'ok')",
    "w._on_restore_backup_finished(True, '', 'collection.nml')",
    "w._on_recheck_done(frozenset({'x'}))",
    "w._on_library_loaded(SimpleNamespace(token=w._load_generation))",
    "w._on_library_failed(w._load_generation, 'boom')",
    "w._on_relocate_ask(SimpleNamespace())",
    "w._on_track_finished()",
    "w._on_preview_done()",
]


import pytest  # noqa: E402


@pytest.mark.parametrize("call", _CALLBACKS)
def test_late_thread_callbacks_do_nothing_once_the_window_is_closing(call: str) -> None:  # V7
    r = _go(
        "starts, modals = [], []\n"
        "orig_start = QThread.start\n"
        "QThread.start = lambda self, *a: (starts.append(type(self).__name__), orig_start(self, *a))[1]\n"
        "for n in ('information', 'warning', 'critical', 'question'):\n"
        "    setattr(ui.dialogs, n, staticmethod(lambda *a, **k: modals.append(1)))\n"
        "ui.RelocateDialog = lambda *a, **k: modals.append(1)\n"
        "w, _ = make(); w._source = 'traktor'; w._closing = True\n"
        "w._relocate_worker = SimpleNamespace(isRunning=lambda: False, provide_answer=lambda a: None)\n"
        "w._reload_after_path_change = lambda: starts.append('reload')\n"
        f"try:\n    {call}\nexcept Exception as e:\n    print('exc', type(e).__name__)\n"
        "print('r', starts, len(modals), flush=True)\n"
    )
    assert r.returncode == 0, r.stderr[-1500:]
    assert r.stdout.strip().splitlines()[-1] == "r [] 0"


def test_relocate_finishing_during_close_does_not_start_a_library_load() -> None:  # V7, sonda del verifier
    r = _go(
        "import library_load_worker\n"
        "ui.MainWindow._load_playlists = load_async\n"
        "library_load_worker.LibraryLoadWorker._load = lambda self: time.sleep(3)\n"
        "class FakeRelocate(QThread):\n"
        "    finished_ok = Signal(int, int, int, str)\n"
        "    def run(self):\n"
        "        time.sleep(1.0); self.finished_ok.emit(3, 0, 0, 'ok')\n"
        "    def provide_answer(self, a): pass\n"
        "w, _ = make(); w._relocate_source = 'traktor'\n"
        "fr = FakeRelocate(); fr.finished_ok.connect(w._on_relocate_finished)\n"
        "w._relocate_worker = fr; w._retain_thread(fr); fr.start()\n"
        "from PySide6.QtCore import QTimer\n"
        "QTimer.singleShot(100, w.close)\n"
        "app.exec()\n"
        "print('fin', flush=True)\n",
        timeout=40,
    )
    assert r.returncode == 0, r.stderr[-1500:]
    assert "Destroyed while thread" not in r.stderr


def test_recheck_finishing_during_close_leaves_the_caches_alone() -> None:  # D3 de T-106
    r = _go(
        "w, _ = make(); w._closing = True; w._exists_cache['x'] = True\n"
        "w._on_recheck_done(frozenset({'x'}))\n"
        "print('x' in w._exists_cache, flush=True)\n"
    )
    assert r.returncode == 0, r.stderr[-1500:]
    assert r.stdout.strip().splitlines()[-1] == "True"
