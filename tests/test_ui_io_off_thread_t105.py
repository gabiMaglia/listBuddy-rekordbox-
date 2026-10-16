"""T-105 (TEC-31, TEC-15): mkdir/exists/resolve_path del destino y de la reproducción no corren en el hilo de UI."""
from __future__ import annotations

from _qt_isolated import run_isolated
from _window_boot import BOOT

_SPY = (
    "import threading, pathlib, tempfile\n"
    "MAIN = threading.main_thread()\n"
    "hits = []\n"
    "def spy(name, fn):\n"
    "    def inner(*a, **k):\n"
    "        if threading.current_thread() is MAIN and armed[0]: hits.append(name)\n"
    "        return fn(*a, **k)\n"
    "    return inner\n"
    "armed = [False]\n"
    "pathlib.Path.mkdir = spy('mkdir', pathlib.Path.mkdir)\n"
    "pathlib.Path.exists = spy('exists', pathlib.Path.exists)\n"
    "import rekordbox_export\n"
    "rekordbox_export.resolve_path = spy('resolve', rekordbox_export.resolve_path)\n"
    "def pump(ms=500):\n"
    "    end = time.time() + ms / 1000\n"
    "    while time.time() < end: app.processEvents()\n"
)


def _last(code: str) -> str:
    r = run_isolated(BOOT + _SPY + code, cold=True, timeout=60)
    assert r.returncode == 0, r.stderr[-2000:]
    return r.stdout.strip().splitlines()[-1]


def test_export_start_and_finish_do_not_touch_the_disk_from_the_ui_thread() -> None:
    out = _last(
        "import rekordbox_xml as rx\n"
        "src = pathlib.Path(tempfile.mkdtemp()) / 'a.mp3'; src.write_bytes(b'x' * 10)\n"
        "dest = pathlib.Path(tempfile.mkdtemp()) / 'sub' / 'out'\n"
        "pl = rx.RbxPlaylist(name='P', ID='1', tracks=[rx.RbxTrack(title='T', artist='A', file_path=src, TrackNo=1)])\n"
        "w, _ = make()\n"
        "w._footer.set_dest(str(dest)); w._selected_playlists = lambda: [pl]\n"
        "armed[0] = True\n"
        "w._start_export()\n"
        "end = time.time() + 20\n"
        "while (w._export_state != 'idle' or w._worker is None) and time.time() < end: app.processEvents()\n"
        "pump(300); armed[0] = False\n"
        "print(sorted(set(hits)), w._footer.finder_btn.isVisibleTo(w._footer), dest.exists())\n"
    )
    assert out == "[] True True"


def test_play_click_resolves_the_path_off_the_ui_thread_and_still_plays() -> None:
    out = _last(
        "from types import SimpleNamespace\n"
        "f = pathlib.Path(tempfile.mkdtemp()) / 'a.mp3'; f.write_bytes(b'x')\n"
        "w, _ = make()\n"
        "played = []\n"
        "w._audio = SimpleNamespace(play=lambda p: played.append(p), toggle=lambda: None, current_path=lambda: '')\n"
        "w._start_waveform = lambda p: None\n"
        "armed[0] = True\n"
        "w._play_file_row(None, str(f))\n"
        "pump(600); armed[0] = False\n"
        "print(sorted(set(hits)), len(played))\n"
    )
    assert out == "[] 1"


def test_clicking_a_non_audio_file_never_reaches_the_player() -> None:
    out = _last(
        "from types import SimpleNamespace\n"
        "f = pathlib.Path(tempfile.mkdtemp()) / 'lista.m3u8'; f.write_bytes(b'x')\n"
        "w, _ = make()\n"
        "played, warned = [], []\n"
        "ui.dialogs.warning = staticmethod(lambda *a, **k: warned.append(a[2]))\n"
        "w._audio = SimpleNamespace(play=lambda p: played.append(p), toggle=lambda: None, current_path=lambda: '', stop=lambda: None)\n"
        "w._start_waveform = lambda p: None\n"
        "w._play_file_row(None, str(f)); pump(600)\n"
        "print(len(played), len(warned))\n"
    )
    assert out == "0 1"


_LAST_CLICK = (
    "from types import SimpleNamespace\n"
    "import preview_worker\n"
    "from preview_worker import GroupData, TrackRow\n"
    "d = pathlib.Path(tempfile.mkdtemp())\n"
    "fa, fb = d / 'A.mp3', d / 'B.mp3'; fa.write_bytes(b'x'); fb.write_bytes(b'x')\n"
    "orig_run = preview_worker.PlayResolveWorker.run\n"
    "def slow_run(self):\n"
    "    if self._raw.endswith('A.mp3'): time.sleep(0.6)   # el primer click resuelve TARDE\n"
    "    orig_run(self)\n"
    "preview_worker.PlayResolveWorker.run = slow_run\n"
    "w, _ = make()\n"
    "w._queue_group(GroupData('P', 1, 2, [TrackRow('001', 'A', 'x', '.mp3', str(fa)), TrackRow('002', 'B', 'x', '.mp3', str(fb))]))\n"
    "pump(1500)\n"
    "played = []\n"
    "w._audio = SimpleNamespace(play=lambda p: played.append(pathlib.Path(p).name), toggle=lambda: None, current_path=lambda: '')\n"
    "w._start_waveform = lambda p: None\n"
    "w._play_file_row(w._row_for(str(fa)), str(fa)); w._play_file_row(w._row_for(str(fb)), str(fb))\n"
    "pump(1500)\n"
    "print(played, w._playing_path.endswith('B.mp3'), w._playing_row is not None and w._playing_row._raw_path.endswith('B.mp3'))\n"
)


def test_last_click_wins_when_the_first_one_resolves_late() -> None:
    assert _last(_LAST_CLICK) == "['B.mp3'] True True"


def test_last_click_test_goes_red_without_the_generation_guard() -> None:
    # Mutación: sin `gen != self._play_gen` la pista A (tardía) pisaría a B.
    out = _last(
        "import inspect, re, ui\n"
        "src = inspect.getsource(ui.MainWindow._on_play_resolved).replace('gen != self._play_gen or ', '')\n"
        "ns = {}; exec('from __future__ import annotations\\n' + __import__('textwrap').dedent(src), ui.__dict__, ns)\n"
        "ui.MainWindow._on_play_resolved = ns['_on_play_resolved']\n" + _LAST_CLICK
    )
    assert out != "['B.mp3'] True True"
