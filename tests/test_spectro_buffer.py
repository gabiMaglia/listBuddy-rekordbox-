"""T-033: el espectrograma lee buffers de PySide6 (constData = memoryview)."""
from __future__ import annotations

from _qt_isolated import run_isolated

_PRELUDE = """
    import numpy as np
    from PySide6.QtCore import QByteArray
    from PySide6.QtMultimedia import QAudioBuffer, QAudioFormat
    import spectro_worker as sw

    def make(raw, fmt, ch):
        f = QAudioFormat()
        f.setSampleFormat(fmt)
        f.setChannelCount(ch)
        f.setSampleRate(11025)
        return QAudioBuffer(QByteArray(raw), f)

    SF = QAudioFormat.SampleFormat
"""


def _run(body: str) -> str:
    proc = run_isolated(_PRELUDE + body)
    assert proc.returncode == 0, proc.stderr
    return proc.stdout.strip()


def test_int16_mono_is_normalized() -> None:
    out = _run("""
    raw = np.array([16384, -16384], np.int16).tobytes()
    print(sw._buffer_to_mono(make(raw, SF.Int16, 1)).tolist())
    """)
    assert out == "[0.5, -0.5]"


def test_int16_stereo_is_downmixed() -> None:
    out = _run("""
    raw = np.array([16384, 0, -16384, 0], np.int16).tobytes()
    print(sw._buffer_to_mono(make(raw, SF.Int16, 2)).tolist())
    """)
    assert out == "[0.25, -0.25]"


def test_uint8_offset_is_removed() -> None:
    out = _run("""
    raw = np.array([192, 64], np.uint8).tobytes()
    print(sw._buffer_to_mono(make(raw, SF.UInt8, 1)).tolist())
    """)
    assert out == "[0.25, -0.25]"


def test_unknown_format_returns_none() -> None:
    out = _run("""
    print(sw._buffer_to_mono(make(b"\\x00\\x00", SF.Unknown, 1)))
    """)
    assert out == "None"


def test_odd_length_buffer_is_trimmed() -> None:
    # Decode cortado a mitad de muestra: se descarta el byte suelto en vez de tirar.
    out = _run("""
    raw = np.array([16384], np.int16).tobytes() + b"\\x01"
    print(sw._buffer_to_mono(make(raw, SF.Int16, 1)).tolist())
    """)
    assert out == "[0.5]"


def test_render_returns_pyside6_qimage() -> None:
    out = _run("""
    from PySide6.QtGui import QImage
    w = sw.SpectrogramWorker("x.mp3", 8, 4, (1, 2, 3), 0)
    img = w._render(np.ones((3, 5), np.float32))
    print(isinstance(img, QImage), img.width(), img.height(), img.pixelColor(0, 0).alpha())
    """)
    assert out == "True 8 4 150"
