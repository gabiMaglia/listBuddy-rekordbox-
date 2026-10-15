"""T-063: energía/tono de la onda, alturas de barras y WaveformSeek."""
from __future__ import annotations

import textwrap

import numpy as np

from _qt_isolated import run_isolated

# Estos importan numpy puro: corren en el proceso de pytest sin Qt.
import waveform_worker as ww


E0 = np.empty(0, np.float32)
SR = ww.TARGET_SR


def _sine(freq: float, n: int, amp: float = 0.9) -> np.ndarray:
    return (amp * np.sin(2 * np.pi * freq * np.arange(n) / SR)).astype(np.float32)


def test_window_features_is_invariant_to_chunking() -> None:
    rng = np.random.default_rng(7)
    y = (rng.random(5000).astype(np.float32) * 2 - 1)
    r0, t0, _ = ww.window_features(y, E0, win=100)
    carry = E0
    rs: list[np.ndarray] = []
    ts: list[np.ndarray] = []
    for a, b in ((0, 730), (730, 1063), (1063, 5000)):  # cortes que NO caen en múltiplos de 100
        r, t, carry = ww.window_features(y[a:b], carry, win=100)
        rs.append(r)
        ts.append(t)
    assert np.allclose(np.concatenate(rs), r0) and np.allclose(np.concatenate(ts), t0)
    assert r0.size == t0.size == 50


def test_window_features_returns_the_leftover_as_carry_and_handles_empty() -> None:
    r, t, carry = ww.window_features(np.ones(250, np.float32), E0, win=100)
    assert r.size == t.size == 2 and carry.size == 50
    r, t, carry = ww.window_features(E0, E0)
    assert r.size == t.size == 0 and carry.size == 0


def test_window_rms_of_a_sine_is_amp_over_sqrt2() -> None:
    r, _, _ = ww.window_features(_sine(440, ww.WIN * 4), E0)
    assert np.allclose(r, 0.9 / np.sqrt(2), atol=0.02)


def test_tone_is_low_for_a_bass_sine_and_high_for_a_treble_sine() -> None:
    _, bass, _ = ww.window_features(_sine(60, ww.WIN * 8), E0)
    _, treble, _ = ww.window_features(_sine(4000, ww.WIN * 8), E0)
    assert bass.max() < 0.15 and treble.min() > 0.85


def test_levels_separate_a_dense_signal_from_a_sparse_one_with_equal_peaks() -> None:
    n = ww.WIN * 40
    dense = _sine(440, n)
    sparse = np.zeros(n, np.float32)
    sparse[::ww.WIN] = 0.9                        # mismo pico (0.9), muchísima menos energía
    r, t, _ = ww.window_features(np.concatenate([dense, sparse]), E0)
    wd = ww.finalize_wave(r, t)
    assert len(wd.levels) == len(wd.tone) == r.size
    assert min(wd.levels[:40]) > 0.9              # el denso está arriba del todo
    assert max(wd.levels[40:]) < 0.4              # el ralo queda claramente más abajo
    assert 0.0 <= min(wd.levels) and max(wd.levels) <= 1.0


def test_finalize_wave_empty_silence_and_flat_tone() -> None:
    assert ww.finalize_wave(E0, E0) == ww.WaveData((), ())
    z = np.zeros(10, np.float32)
    wd = ww.finalize_wave(z, z)
    assert wd.levels == (0.0,) * 10 and wd.tone == (0.5,) * 10   # sin rango de tono → 0.5, sin NaN


def test_finalize_wave_normalizes_tone_by_percentiles() -> None:
    r = np.full(100, 0.3, np.float32)
    t = np.linspace(0.2, 0.6, 100).astype(np.float32)
    wd = ww.finalize_wave(r, t)
    assert min(wd.tone) == 0.0 and max(wd.tone) == 1.0 and wd.tone[50] > 0.3


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
        w.ready.connect(lambda data, gen: got.append((data, gen)))
        w.finished.connect(app.quit)
        w.start(); app.exec(); w.wait(5000)
        data, gen = got[0]
        lv = data.levels
        h = len(lv) // 2
        print(gen, len(lv) > 30 and len(lv) == len(data.tone), max(lv[:h - 2]) < 0.05, min(lv[h + 2:]) > 0.9)
    """, timeout=90)
    assert r.returncode == 0, r.stderr[-2000:]
    assert r.stdout.split()[-4:] == ["5", "True", "True", "True"]


def _rc(code: str) -> str:
    r = run_isolated(code)
    assert r.returncode == 0, r.stderr[-2000:]
    return r.stdout.strip().splitlines()[-1]


def test_bar_heights_mean_pools_flat_when_empty_and_respects_floor() -> None:
    assert _rc("""
        import ui_components as uc
        spike = [0.0] * 99 + [1.0]
        h = uc.bar_heights(spike, 10)
        print(len(h), round(h[-1], 3), h[0], uc.bar_heights([], 4), uc.bar_heights([0.5], 3),
              uc.bar_means([0.0, 1.0, 0.5, 0.5], 2))
    """) == "10 0.12 0.12 [0.12, 0.12, 0.12, 0.12] [0.5, 0.5, 0.5] [0.5, 0.5]"


_WF = """
    from PySide6.QtCore import QEventLoop, QTimer
    from PySide6.QtWidgets import QApplication
    from PySide6.QtGui import QColor
    import styles, ui_components as uc
    from waveform_worker import WaveData
    app = QApplication([]); styles.register_fonts()
    def pump(ms):
        loop = QEventLoop(); QTimer.singleShot(ms, loop.quit); loop.exec()
    acc, hi, rest = (styles.token('dark', k) for k in ('accent', 'wave_hi', 'line'))
    def make(tone=0.0):
        wf = uc.WaveformSeek(); wf.resize(200, 32); wf.set_colors(acc, hi, rest); wf.show(); app.processEvents()
        return wf
    D = WaveData((1.0,) * 100, (0.0,) * 100)
"""


def _wf(code: str) -> str:
    return textwrap.dedent(_WF) + textwrap.dedent(code)


def test_waveform_seek_paints_played_in_tone_color_and_pending_dimmer() -> None:
    assert _rc(_wf("""
        wf = make(); wf.set_wave(D); wf.set_progress(500, 1000); pump(700)
        img = wf.grab().toImage(); mid = wf.height() // 2
        left = QColor(img.pixel(1, mid)); right = QColor(img.pixel(196, mid))
        bg = QColor(img.pixel(1, 0))
        print(left.name() == QColor(acc).name(), right.name() != left.name(), right.name() != bg.name(),
              right.lightness() < left.lightness())
    """)) == "True True True True"


def test_waveform_seek_tone_mixes_from_lo_to_hi() -> None:
    assert _rc(_wf("""
        wf = make(); wf.set_wave(WaveData((1.0,) * 100, (1.0,) * 100)); wf.set_progress(1000, 1000); pump(700)
        img = wf.grab().toImage(); mid = wf.height() // 2
        print(QColor(img.pixel(1, mid)).name() == QColor(hi).name())
    """)) == "True"


def test_waveform_seek_animates_on_new_data_and_ends_at_full_height() -> None:
    assert _rc(_wf("""
        wf = make(); wf.set_wave(D)
        start = (wf._anim.state() == wf._anim.State.Running, wf._grow < 1.0)
        pump(700)
        end = (wf._grow, wf._anim.state() == wf._anim.State.Running)
        print(start, end)
    """)) == "(True, True) (1.0, False)"


def test_waveform_seek_same_data_none_and_progress_do_not_animate() -> None:
    assert _rc(_wf("""
        wf = make(); wf.set_wave(D); pump(700)
        wf.set_wave(D); a = wf._anim.state() == wf._anim.State.Running      # mismo objeto
        for i in range(20): wf.set_progress(i * 10, 1000)
        b = wf._anim.state() == wf._anim.State.Running
        wf.set_wave(WaveData((0.5,) * 100, (0.5,) * 100)); c = wf._anim.state() == wf._anim.State.Running
        wf.set_wave(None); d = wf._anim.state() == wf._anim.State.Running   # None corta y no anima
        print(a, b, c, d, wf._grow)
    """)) == "False False True False 1.0"


def test_waveform_seek_prerenders_pixmaps_once_per_data_size_and_colors() -> None:
    assert _rc(_wf("""
        wf = make(); wf.set_wave(D); pump(700); wf.grab()
        base = wf._rebuilds
        for i in range(30): wf.set_progress(i * 30, 1000); wf.grab()
        after_progress = wf._rebuilds - base
        wf.resize(300, 32); app.processEvents(); wf.grab(); after_resize = wf._rebuilds - base
        wf.set_colors(acc, hi, '#555555'); wf.grab(); after_colors = wf._rebuilds - base
        wf.set_wave(WaveData((0.3,) * 50, (0.3,) * 50)); pump(700); wf.grab(); after_data = wf._rebuilds - base
        print(after_progress, after_resize, after_colors, after_data)
    """)) == "0 1 2 3"


def test_waveform_seek_destroyed_mid_animation_is_safe() -> None:
    r = run_isolated(_wf("""
        wf = make(); wf.set_wave(D); wf.deleteLater(); pump(700); print('alive')
    """))
    assert r.returncode == 0, r.stderr[-2000:]
    assert r.stdout.strip().splitlines()[-1] == "alive" and "Traceback" not in r.stderr


def test_waveform_seek_click_emits_proportional_position_and_ignores_unknown_duration() -> None:
    assert _rc("""
        from PySide6.QtCore import Qt, QPoint
        from PySide6.QtTest import QTest
        from PySide6.QtWidgets import QApplication
        import ui_components as uc
        app = QApplication([])
        wf = uc.WaveformSeek(); wf.resize(200, 32); wf.show()
        got = []; wf.seek_requested.connect(got.append)
        QTest.mouseClick(wf, Qt.MouseButton.LeftButton, pos=QPoint(100, 16))
        assert got == []                          # sin duración no hay seek
        wf.set_progress(0, 10_000)
        QTest.mouseClick(wf, Qt.MouseButton.LeftButton, pos=QPoint(100, 16))
        print(len(got) == 1 and abs(got[0] - 5000) <= 100)
    """) == "True"
