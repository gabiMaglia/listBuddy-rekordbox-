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
