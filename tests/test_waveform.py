"""T-063: picos de la onda, alturas de barras y WaveformSeek."""
from __future__ import annotations

import numpy as np

from _qt_isolated import run_isolated

# Estos importan numpy puro: corren en el proceso de pytest sin Qt.
import waveform_worker as ww


def test_window_peaks_is_invariant_to_chunking() -> None:
    rng = np.random.default_rng(7)
    y = (rng.random(5000).astype(np.float32) * 2 - 1)
    whole, _ = ww.window_peaks(y, np.empty(0, np.float32), win=100)
    carry = np.empty(0, np.float32)
    parts: list[np.ndarray] = []
    for a, b in ((0, 730), (730, 1063), (1063, 5000)):  # cortes que NO caen en múltiplos de 100
        p, carry = ww.window_peaks(y[a:b], carry, win=100)
        parts.append(p)
    assert np.array_equal(np.concatenate(parts), whole)
    assert whole.size == 50


def test_window_peaks_returns_the_leftover_as_carry() -> None:
    p, carry = ww.window_peaks(np.ones(250, np.float32), np.empty(0, np.float32), win=100)
    assert p.size == 2 and carry.size == 50


def test_window_peaks_uses_absolute_value() -> None:
    p, _ = ww.window_peaks(-np.ones(100, np.float32) * 0.5, np.empty(0, np.float32), win=100)
    assert p.tolist() == [0.5]


def test_normalize_silence_is_zeros_not_nan() -> None:
    assert ww.normalize_peaks(np.zeros(10, np.float32)) == [0.0] * 10
    assert ww.normalize_peaks(np.empty(0, np.float32)) == []


def test_normalize_keeps_quiet_and_loud_apart_and_clips_spikes() -> None:
    peaks = np.concatenate([np.full(500, 0.1), np.full(500, 0.5), [10.0]]).astype(np.float32)
    out = ww.normalize_peaks(peaks)
    assert max(out) == 1.0 and min(out) >= 0.0
    quiet, loud = out[:500], out[500:1000]
    assert max(quiet) < min(loud)          # el orden de volumen se conserva
    assert min(loud) > 0.9                 # un pico aislado no aplasta el resto


def test_worker_decodes_a_real_wav_and_tracks_loudness(tmp_path) -> None:
    import wave
    sr = 11025
    t = np.arange(sr) / sr
    audio = np.concatenate([np.zeros(sr), 0.9 * np.sin(2 * np.pi * 440 * t)])
    path = tmp_path / "half.wav"
    with wave.open(str(path), "wb") as f:
        f.setnchannels(1); f.setsampwidth(2); f.setframerate(sr)
        f.writeframes((audio * 32767).astype("<i2").tobytes())
    r = run_isolated(f"""
        from PySide6.QtCore import QCoreApplication
        import waveform_worker as ww
        app = QCoreApplication([])
        got = []
        w = ww.WaveformWorker({str(path)!r}, 5)
        w.ready.connect(lambda peaks, gen: got.append((peaks, gen)))
        w.finished.connect(app.quit)
        w.start(); app.exec(); w.wait(5000)
        peaks, gen = got[0]
        h = len(peaks) // 2
        print(gen, len(peaks) > 30, max(peaks[:h - 2]) < 0.05, min(peaks[h + 2:]) > 0.5)
    """, timeout=90)
    assert r.returncode == 0, r.stderr[-2000:]
    assert r.stdout.split()[-4:] == ["5", "True", "True", "True"]
