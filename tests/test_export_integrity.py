"""T-088: la exportación no deja archivos truncados, no mezcla playlists
homónimas y no escribe fuera de la carpeta de destino ni a través de symlinks.

Todo corre en un subproceso (worker.py importa PySide6).
"""
from __future__ import annotations

from _qt_isolated import run_isolated

_PRE = (
    "import errno, os, pathlib, tempfile\n"
    "from PySide6.QtCore import QCoreApplication\n"
    "app = QCoreApplication([])\n"
    "import rekordbox_xml as rx, worker\n"
    "tmp = pathlib.Path(tempfile.mkdtemp())\n"
    "out = tmp / 'out'; out.mkdir()\n"
    "def mk(n, size=1_000_000):\n"
    "    p = tmp / f'src{n}.mp3'; p.write_bytes(bytes([n]) * size); return p\n"
    "def track(n, no, title=None):\n"
    "    return rx.RbxTrack(title=title or f'T{n}', artist='A', file_path=mk(n), TrackNo=no)\n"
    "def pl(name, tracks, ID=None):\n"
    "    return rx.RbxPlaylist(name=name, ID=ID or name, tracks=tracks)\n"
    "def export(pls, dest=None):\n"
    "    w = worker.ExportWorker(pls, dest or out)\n"
    "    logs, done = [], []\n"
    "    w.log.connect(logs.append); w.finished_ok.connect(lambda *a: done.append(a))\n"
    "    w.run()\n"
    "    return logs, done[-1]\n"
)


def _run(body: str) -> str:
    r = run_isolated(_PRE + body)
    assert r.returncode == 0, r.stderr[-3000:]
    return r.stdout.strip().splitlines()[-1]


_FAIL_MID_COPY = (
    "real = worker._copy_stream\n"
    "def broken(fsrc, fdst, should_stop):\n"
    "    fdst.write(fsrc.read(300_000)); fdst.flush()\n"
    "    raise OSError(errno.ENOSPC, 'No space left on device')\n"
)


def test_interrupted_copy_leaves_no_truncated_file_and_retry_copies_it_whole() -> None:
    out = _run(
        _FAIL_MID_COPY +
        "p = pl('Mix', [track(1, 1)])\n"
        "worker._copy_stream = broken\n"
        "export([p])\n"
        "left = sorted(f.name for f in (out / 'Mix').iterdir())\n"
        "worker._copy_stream = real\n"
        "logs, done = export([p])\n"
        "f = next((out / 'Mix').glob('*.mp3'))\n"
        "print(left, f.stat().st_size, done[0], done[2])\n"
    )
    assert out == "[] 1000000 1 0"


def test_orphan_part_files_are_removed_before_copying() -> None:
    out = _run(
        "(out / 'Mix').mkdir()\n"
        "(out / 'Mix' / '1 - A - T1.mp3.part').write_bytes(b'basura')\n"
        "export([pl('Mix', [track(1, 1)])])\n"
        "print(sorted(f.name for f in (out / 'Mix').iterdir()))\n"
    )
    assert out == "['1 - A - T1.mp3']"


def test_existing_file_with_a_different_size_is_recopied_but_equal_size_is_skipped() -> None:
    out = _run(
        "p = pl('Mix', [track(1, 1)])\n"
        "(out / 'Mix').mkdir()\n"
        "dest = out / 'Mix' / '1 - A - T1.mp3'\n"
        "dest.write_bytes(b'x' * 300_000)\n"
        "logs, done = export([p])\n"
        "a = (done[0], done[2], dest.stat().st_size)\n"
        "logs, done = export([p])\n"
        "print(a, (done[0], done[2]))\n"
    )
    assert out == "(1, 0, 1000000) (0, 1)"


def test_cancelling_in_the_middle_of_a_file_removes_the_partial_copy() -> None:
    out = _run(
        "calls = []\n"
        "worker.ExportWorker.isInterruptionRequested = lambda self: calls.append(1) or len(calls) > 1\n"
        "logs, done = export([pl('Mix', [track(1, 1)])])\n"
        "print(done[3], sorted(f.name for f in (out / 'Mix').iterdir()))\n"
    )
    assert out == "cancelled []"
