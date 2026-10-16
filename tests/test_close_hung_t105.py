"""T-105 (TEC-24): cerrar con un hilo de solo lectura colgado no aborta el proceso."""
from __future__ import annotations

from _qt_isolated import run_isolated
from _window_boot import BOOT

_HUNG_PREVIEW = (
    "import time, preview_worker\n"
    "def hang(self, raw):\n"
    "    time.sleep(5); return False\n"
    "preview_worker.PreviewWorker._check = hang\n"
    "class FakeCard:\n"
    "    playlist = type('P', (), {'Name': 'G'})()\n"
    "    def isChecked(self): return True\n"
    "rows = [preview_worker.TrackRow(num='001', title='t', artist='a', ext='.mp3', raw_path='/no/1.mp3')]\n"
    "def pump(ms):\n"
    "    end = time.time() + ms / 1000\n"
    "    while time.time() < end: app.processEvents()\n"
)


def test_closing_with_a_stat_blocked_for_5s_exits_clean() -> None:
    r = run_isolated(
        BOOT + _HUNG_PREVIEW +
        "w, _ = make()\n"
        "w._all_cards = [FakeCard()]\n"
        "w._extract_preview_data = lambda sel: [preview_worker.GroupData(name='G', order=0, total_count=1, tracks=rows)]\n"
        "w._start_preview_worker(); pump(200)\n"
        "assert w._preview_worker.isRunning()\n"
        "print('cerrando', flush=True)\n"
        "w.close()\n"
        "print('sigue', flush=True)\n",
        cold=True, timeout=60,
    )
    assert r.returncode == 0, r.stderr[-2000:]
    assert "cerrando" in r.stdout
    assert "Destroyed while thread" not in r.stderr


def test_closing_with_the_waveform_decoder_blocked_exits_clean() -> None:
    r = run_isolated(
        BOOT + _HUNG_PREVIEW +
        "import waveform_worker\n"
        "waveform_worker.WaveformWorker._decode = lambda self: time.sleep(5)\n"
        "w, _ = make()\n"
        "w._start_waveform('/tmp/x.mp3'); pump(200)\n"
        "assert w._wave_worker.isRunning()\n"
        "print('cerrando', flush=True)\n"
        "w.close()\n"
        "print('sigue', flush=True)\n",
        cold=True, timeout=60,
    )
    assert r.returncode == 0, r.stderr[-2000:]
    assert "cerrando" in r.stdout
    assert "Destroyed while thread" not in r.stderr


def test_closing_waits_for_a_writing_thread_instead_of_exiting_under_it() -> None:
    # Un relocate que escribe (NML/JSON) no se corta con os._exit: se espera como el export.
    r = run_isolated(
        BOOT +
        "import pathlib, tempfile\n"
        "from PySide6.QtCore import QThread\n"
        "out = pathlib.Path(tempfile.mkdtemp()) / 'collection.nml'\n"
        "class FakeRelocate(QThread):\n"
        "    def run(self):\n"
        "        time.sleep(9); out.write_text('COMPLETO')\n"
        "    def provide_answer(self, a): pass\n"
        "w, _ = make()\n"
        "fr = FakeRelocate(); w._relocate_worker = fr; w._retain_thread(fr); fr.start()\n"
        "w.close()\n"
        "print('tras cerrar:', out.read_text() if out.exists() else 'FALTA', flush=True)\n",
        cold=True, timeout=60,
    )
    assert r.returncode == 0, r.stderr[-2000:]
    assert "tras cerrar: COMPLETO" in r.stdout
