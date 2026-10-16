"""T-095: robustez de export y preview (TEC-08/09/10/18 y deudas D-16..D-22 de QA)."""
from __future__ import annotations

from _qt_isolated import run_isolated
from _window_boot import BOOT
from test_export_integrity import _PRE


def _run(body: str, pre: str = _PRE, timeout: float = 60.0) -> str:
    r = run_isolated(pre + body, timeout=timeout)
    assert r.returncode == 0, r.stderr[-3000:]
    return r.stdout.strip().splitlines()[-1]


def _win(body: str) -> str:
    r = run_isolated(BOOT + body)
    assert r.returncode == 0, r.stderr[-3000:]
    return r.stdout.strip().splitlines()[-1]


# ── TEC-08 ────────────────────────────────────────────────────────────────

def test_incremental_reexport_to_a_nearly_full_disk_does_not_abort() -> None:
    out = _run(
        "p = pl('Mix', [track(1, 1), track(2, 2)])\n"
        "logs, done = export([p])\n"
        "import collections\n"
        "free = 500_000\n"
        "worker.shutil.disk_usage = lambda _p: collections.namedtuple('U', 'total used free')(10**9, 10**9 - free, free)\n"
        "logs, done = export([p])\n"
        "print(done[3], done[0], done[2])\n"
    )
    assert out == "ok 0 2"


# ── TEC-09 ────────────────────────────────────────────────────────────────

def test_log_view_has_a_block_cap() -> None:
    out = _win(
        "w, _ = make()\n"
        "for i in range(6000): w._log(f'l{i}')\n"
        "print(w.log_view.blockCount() <= 5000, w.log_view.toPlainText().endswith('l5999'))\n"
    )
    assert out == "True True"


# ── TEC-10 ────────────────────────────────────────────────────────────────

def test_export_says_which_playlist_could_not_be_read() -> None:
    out = _run(
        "class Rota:\n"
        "    Name = 'Rota'\n"
        "    @property\n"
        "    def Songs(self): raise RuntimeError('boom')\n"
        "logs, done = export([Rota(), pl('Ok', [track(1, 1)])])\n"
        "print(any('⚠ No se pudo leer la playlist Rota: boom' in l for l in logs), done[0], done[3])\n"
    )
    assert out == "True 1 ok"


def test_preview_reports_unreadable_playlist_and_does_not_cache_the_empty_result() -> None:
    out = _win(
        "from types import SimpleNamespace\n"
        "from ui_components import PlaylistCard\n"
        "class Rota:\n"
        "    Name = 'Rota'; uuid = 'r1'\n"
        "    @property\n"
        "    def Songs(self): raise RuntimeError('boom')\n"
        "w, _ = make()\n"
        "card = PlaylistCard(Rota(), 3, 0)\n"
        "g = w._extract_preview_data([card])\n"
        "print(len(w._track_meta_cache), w.log_view.toPlainText().count('No se pudo leer la playlist Rota: boom'),\n"
        "      'No se pudo leer' in w.output_status.text())\n"
    )
    assert out == "0 1 True"


# ── D-16 ──────────────────────────────────────────────────────────────────

def test_close_waits_for_the_export_block_in_flight_instead_of_aborting() -> None:
    out = _run(
        "import time\n"
        "from PySide6.QtCore import QThread, QTimer\n"
        "from PySide6.QtWidgets import QApplication\n"
        "class Slow(QThread):\n"
        "    def run(self):\n"
        "        while not self.isInterruptionRequested(): self.msleep(10)\n"
        "        self.msleep(7000)   # un bloque de I/O colgado más que el viejo tope de 4 + 2 s\n"
        "w, _ = make()\n"
        "s = Slow(); w._retain_thread(s); w._worker = s; s.start(); time.sleep(0.2)\n"
        "seen = {}\n"
        "def look():\n"
        "    seen['msg'] = w.output_status.text(); seen['cur'] = QApplication.overrideCursor() is not None\n"
        "QTimer.singleShot(1000, look)\n"
        "t0 = time.monotonic(); w.close(); dt = time.monotonic() - t0\n"
        "print(dt >= 6.9, s.isRunning(), seen.get('msg'), seen.get('cur'), QApplication.overrideCursor() is None)\n",
        pre=BOOT, timeout=90,
    )
    assert out == "True False Esperando que termine la copia… True True"


# ── D-17 ──────────────────────────────────────────────────────────────────

def test_preview_titles_show_the_folder_name_the_export_will_create() -> None:
    out = _win(
        "import tempfile, pathlib\n"
        "from PySide6.QtCore import QEventLoop, QTimer\n"
        "import rekordbox_xml as rx, worker\n"
        "from ui_components import PlaylistCard\n"
        "def pump(ms=600):\n"
        "    loop = QEventLoop(); QTimer.singleShot(ms, loop.quit); loop.exec()\n"
        "f = pathlib.Path(tempfile.mkdtemp()) / 'a.mp3'; f.write_bytes(b'x')\n"
        "names = ['Set: A', 'set: a']\n"
        "base = worker._unique_folder_names(names)\n"
        "def mk(i): return rx.RbxPlaylist(name=names[i], ID=f'p{i}', tracks=[rx.RbxTrack(title='T', artist='A', file_path=f, TrackNo=1)])\n"
        "w, _ = make()\n"
        "cards = [PlaylistCard(mk(i), 1, i) for i in range(2)]\n"
        "w._all_cards.extend(cards)\n"
        "for c in cards: c.setChecked(True)\n"
        "w._start_preview_worker(); pump()\n"
        "def titles(): return sorted(c._title.text() for c in w._preview_cards.values())\n"
        "first = titles()\n"
        "cards[0].setChecked(False); w._start_preview_worker(); pump()\n"
        "second = titles()\n"
        "print(first == [f'01 {base[0]}', f'02 {base[1]}'], base[1].endswith('(2)'), second == [f'01 {base[1][:-4]}'])\n"
    )
    assert out == "True True True"


# ── D-18 ──────────────────────────────────────────────────────────────────

def test_foreign_part_files_survive_but_our_own_orphan_is_removed() -> None:
    out = _run(
        "(out / 'Mix').mkdir()\n"
        "(out / 'Mix' / '1 - A - T1.mp3.part').write_bytes(b'basura')\n"
        "(out / 'Mix' / 'descarga.part').write_bytes(b'ajeno')\n"
        "(out / 'Mix' / 'otra.mp3.part').write_bytes(b'ajeno')\n"
        "export([pl('Mix', [track(1, 1)])])\n"
        "print(sorted(f.name for f in (out / 'Mix').iterdir()))\n"
    )
    assert out == "['1 - A - T1.mp3', 'descarga.part', 'otra.mp3.part']"


# ── D-20 ──────────────────────────────────────────────────────────────────

_CORRUPT = (
    "import os, pathlib, tempfile, time\n"
    "bad = pathlib.Path(tempfile.mkdtemp()) / 'roto.mp3'; bad.write_bytes(os.urandom(5000))\n"
)


def test_waveform_worker_gives_up_at_once_on_a_file_that_does_not_open() -> None:
    out = _run(
        _CORRUPT +
        "from PySide6.QtCore import QCoreApplication\n"
        "app = QCoreApplication([])\n"
        "import waveform_worker as ww\n"
        "w = ww.WaveformWorker(str(bad), 1); t0 = time.monotonic(); w.start()\n"
        "while w.isRunning() and time.monotonic() - t0 < 20:\n"
        "    app.processEvents(); time.sleep(0.01)\n"
        "print(w.isRunning(), time.monotonic() - t0 < 2)\n",
        pre="", timeout=60,
    )
    assert out == "False True"


def test_closing_the_app_while_a_corrupt_file_decodes_does_not_abort() -> None:
    out = _run(
        _CORRUPT +
        "w, _ = make()\n"
        "w._start_waveform(str(bad)); time.sleep(0.3)\n"
        "ws = list(w._live_wave_workers)\n"
        "t0 = time.monotonic(); w.close()\n"
        "print(time.monotonic() - t0 < 4, any(x.isRunning() for x in ws))\n",
        pre=BOOT, timeout=60,
    )
    assert out == "True False"


# ── D-21 ──────────────────────────────────────────────────────────────────

def test_playing_changed_only_emits_real_changes_when_starting_and_switching_tracks() -> None:
    out = _run(
        "import wave, numpy as np\n"
        "from PySide6.QtCore import QEventLoop, QTimer\n"
        "def mkwav(n):\n"
        "    p = tmp / f'a{n}.wav'\n"
        "    with wave.open(str(p), 'wb') as f:\n"
        "        f.setnchannels(1); f.setsampwidth(2); f.setframerate(11025)\n"
        "        f.writeframes((np.sin(np.arange(11025 * 3) / 5) * 8000).astype('<i2').tobytes())\n"
        "    return str(p)\n"
        "def pump(ms):\n"
        "    loop = QEventLoop(); QTimer.singleShot(ms, loop.quit); loop.exec()\n"
        "from audio_player import AudioPlayer\n"
        "pl_ = AudioPlayer(); seen = []\n"
        "pl_.playing_changed.connect(seen.append)\n"
        "pl_.play(mkwav(1)); pump(700)\n"
        "pl_.play(mkwav(2)); pump(700)\n"
        "pl_.stop(); pump(300)\n"
        "print(seen)\n",
    )
    assert out == "[True, False]"


# ── D-22 ──────────────────────────────────────────────────────────────────

def test_pump_render_queue_after_the_window_is_destroyed_is_silent() -> None:
    r = run_isolated(
        BOOT +
        "from PySide6.QtCore import QCoreApplication, QEvent, QTimer\n"
        "from preview_worker import GroupData\n"
        "w, _ = make()\n"
        "w._render_queue.append(GroupData('X', 1, 0, [], card=None))\n"
        "QTimer.singleShot(0, w._pump_render_queue)\n"
        "w.deleteLater()\n"
        "QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)\n"
        "app.processEvents(); app.processEvents()\n"
        "print('fin')\n",
        cold=True,
    )
    assert r.returncode == 0 and "already deleted" not in r.stderr, r.stderr[-1500:]


# ── TEC-18 ────────────────────────────────────────────────────────────────

_REFOCUS = (
    "import tempfile, pathlib\n"
    "from PySide6.QtCore import QEvent, QEventLoop, QTimer\n"
    "import rekordbox_xml as rx\n"
    "from ui_components import PlaylistCard\n"
    "def pump(ms=700):\n"
    "    loop = QEventLoop(); QTimer.singleShot(ms, loop.quit); loop.exec()\n"
    "d = pathlib.Path(tempfile.mkdtemp())\n"
    "(d / 'a.mp3').write_bytes(b'x')\n"
    "tracks = [rx.RbxTrack(title=n, artist='A', file_path=d / f'{n}.mp3', TrackNo=i) for i, n in enumerate('ab', 1)]\n"
    "w, _ = make()\n"
    "card = PlaylistCard(rx.RbxPlaylist(name='P', ID='p', tracks=tracks), 2, 0)\n"
    "w._all_cards.append(card); card.setChecked(True)\n"
    "w._start_preview_worker(); pump()\n"
    "starts = []\n"
    "orig = ui.ExistenceRecheckWorker.start\n"
    "ui.ExistenceRecheckWorker.start = lambda self: (starts.append(1), orig(self))[1]\n"
    "def activate(): app.sendEvent(w, QEvent(QEvent.Type.WindowActivate))\n"
)


def test_regaining_focus_after_5s_rechecks_files_that_came_back() -> None:
    out = _win(
        _REFOCUS +
        "before = w._broken_total\n"
        "(d / 'b.mp3').write_bytes(b'x')\n"
        "w._last_exists_check -= 10\n"
        "activate(); pump(1500)\n"
        "print(before, w._broken_total, len(starts))\n"
    )
    assert out == "1 0 1"


def test_regaining_focus_within_5s_does_not_recheck() -> None:
    out = _win(
        _REFOCUS +
        "(d / 'b.mp3').write_bytes(b'x')\n"
        "activate(); activate(); pump(500)\n"
        "print(w._broken_total, len(starts))\n"
    )
    assert out == "1 0"
