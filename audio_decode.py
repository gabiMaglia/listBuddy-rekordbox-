"""Helpers de decode de Qt compartidos (QAudioBuffer → numpy mono)."""
from __future__ import annotations

import numpy as np
from PySide6.QtMultimedia import QAudioFormat

_DTYPE = {
    QAudioFormat.SampleFormat.UInt8: (np.uint8,  256.0,  128.0),
    QAudioFormat.SampleFormat.Int16: (np.int16,  32768.0, 0.0),
    QAudioFormat.SampleFormat.Int32: (np.int32,  2147483648.0, 0.0),
    QAudioFormat.SampleFormat.Float: (np.float32, 1.0,    0.0),
}


def buffer_to_mono(buf) -> np.ndarray | None:
    """QAudioBuffer → numpy float32 mono en [-1, 1], tolerante al formato real."""
    fmt = buf.format()
    spec = _DTYPE.get(fmt.sampleFormat())
    if spec is None:
        return None
    dtype, scale, offset = spec

    # PySide6 entrega un memoryview ya dimensionado (no un sip.voidptr con setsize).
    raw = buf.constData().tobytes()
    itemsize = np.dtype(dtype).itemsize
    usable = len(raw) - (len(raw) % itemsize)
    arr = np.frombuffer(raw[:usable], dtype=dtype).astype(np.float32)
    if offset:
        arr = arr - offset
    arr = arr / scale

    ch = max(1, fmt.channelCount())
    if ch > 1:
        usable = (arr.size // ch) * ch
        arr = arr[:usable].reshape(-1, ch).mean(axis=1)
    return arr
