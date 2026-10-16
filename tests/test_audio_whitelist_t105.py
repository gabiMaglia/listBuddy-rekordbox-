"""T-105 (SEC-18): solo extensiones de audio conocidas llegan al demuxer de FFmpeg."""
from __future__ import annotations

import pytest

from _qt_isolated import run_isolated


@pytest.mark.parametrize("ext", ["xyz", "m3u8", "ffconcat", "mov", "txt", ""])
def test_player_does_not_open_non_audio_extensions(ext: str) -> None:
    r = run_isolated(
        "from PySide6.QtCore import QCoreApplication\n"
        "app = QCoreApplication([])\n"
        "from audio_player import AudioPlayer\n"
        "p = AudioPlayer(); calls = []; errs = []\n"
        "orig = p._player.setSource\n"
        "p._player.setSource = lambda u: (calls.append(u), orig(u))\n"
        "p.error.connect(errs.append)\n"
        f"p.play('/tmp/pista.{ext}' if {ext!r} else '/tmp/pista')\n"
        "print(len(calls), len(errs), p.current_path() == '')\n"
    )
    assert r.returncode == 0, r.stderr[-2000:]
    assert r.stdout.strip().splitlines()[-1] == "0 1 True"


def test_player_still_opens_allowed_extensions() -> None:
    r = run_isolated(
        "from PySide6.QtCore import QCoreApplication\n"
        "app = QCoreApplication([])\n"
        "from audio_player import AudioPlayer\n"
        "p = AudioPlayer(); calls = []\n"
        "orig = p._player.setSource\n"
        "p._player.setSource = lambda u: (calls.append(u), orig(u))\n"
        "for e in ('MP3', 'mp4', 'm4a', 'aac', 'flac', 'wav', 'aif', 'aiff', 'ogg', 'opus', 'wma'):\n"
        "    p.play('/tmp/x.' + e)\n"
        "print(len(calls))\n"
    )
    assert r.returncode == 0, r.stderr[-2000:]
    assert r.stdout.strip().splitlines()[-1] == "11"


def test_waveform_worker_does_not_start_the_decoder_for_non_audio() -> None:
    r = run_isolated(
        "from PySide6.QtCore import QCoreApplication\n"
        "app = QCoreApplication([])\n"
        "import waveform_worker as ww\n"
        "started = []\n"
        "ww.QAudioDecoder = lambda *a, **k: started.append(1) or (_ for _ in ()).throw(RuntimeError)\n"
        "w = ww.WaveformWorker('/tmp/lista.m3u8', 1); w.run()\n"
        "print(len(started))\n"
    )
    assert r.returncode == 0, r.stderr[-2000:]
    assert r.stdout.strip().splitlines()[-1] == "0"
