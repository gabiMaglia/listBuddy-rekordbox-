"""T-105 (TEC-22): el log del export sale en lotes, no una señal por línea."""
from __future__ import annotations

from _qt_isolated import run_isolated

_PRE = (
    "import pathlib, tempfile\n"
    "from PySide6.QtCore import QCoreApplication\n"
    "app = QCoreApplication([])\n"
    "import rekordbox_xml as rx, worker\n"
    "tmp = pathlib.Path(tempfile.mkdtemp()); out = tmp / 'out'; out.mkdir()\n"
    "src = tmp / 's.mp3'; src.write_bytes(b'x' * 10)\n"
    "N = 300\n"
    "tracks = [rx.RbxTrack(title=f'T{i}', artist='A', file_path=src, TrackNo=i + 1) for i in range(N)]\n"
    "pl = rx.RbxPlaylist(name='Mix', ID='1', tracks=tracks)\n"
    "w = worker.ExportWorker([pl], out)\n"
    "events = []\n"
    "w.log.connect(lambda t: events.append(('log', t)))\n"
    "w.finished_ok.connect(lambda *a: events.append(('done', a)))\n"
    "w.run()\n"
)


def _run(body: str) -> str:
    r = run_isolated(_PRE + body)
    assert r.returncode == 0, r.stderr[-3000:]
    return r.stdout.strip().splitlines()[-1]


def test_log_lines_are_emitted_in_batches() -> None:
    out = _run("print(sum(1 for k, _ in events if k == 'log'))\n")
    assert int(out) < 60   # 300 pistas = ~300 líneas; antes una señal por línea


def test_batched_log_keeps_every_line_in_order_and_flushes_before_finished() -> None:
    out = _run(
        "text = '\\n'.join(t for k, t in events if k == 'log').split('\\n')\n"
        "names = [l.strip() for l in text if l.strip().startswith('✓') or l.strip().startswith('⏭')]\n"
        "print(events[-1][0], text[0], len(names), names[0].endswith('T0.mp3'), names[-1].endswith('T299.mp3'))\n"
    )
    assert out == "done ▶  Mix 300 True True"
