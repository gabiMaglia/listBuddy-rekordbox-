"""
spectro_worker.py
-----------------
Espectrograma de fondo para el rack-head, calculado en background.

Decodifica el audio con QAudioDecoder (mismo backend de Qt que la reproducción,
así cubre los mismos formatos), arma una STFT con numpy puro y renderiza un
QImage tenue tintado con el accent del tema. Todo corre en un QThread con su
propio event loop: la UI nunca se bloquea.

Acotamiento de recursos:
  • sample-rate bajo (11025 Hz) y mono  → menos datos
  • cap de ~90 s de audio                → memoria/CPU acotadas
  • un solo worker a la vez (la UI cancela el anterior)
  • cualquier fallo → no se emite nada (degradación elegante)
"""
from __future__ import annotations

import numpy as np
from PyQt6.QtCore import QEventLoop, QThread, QTimer, QUrl, pyqtSignal
from PyQt6.QtGui import QImage
from PyQt6.QtMultimedia import QAudioDecoder, QAudioFormat

_TARGET_SR      = 11025
_MAX_SECONDS    = 90
_N_FFT          = 1024
_HOP            = 512
_DECODE_TIMEOUT = 25_000   # ms — corta si el decode se cuelga


class SpectrogramWorker(QThread):
    ready: pyqtSignal = pyqtSignal(QImage, int)   # (imagen, generation)

    def __init__(
        self,
        path: str,
        width: int,
        height: int,
        accent_rgb: tuple[int, int, int],
        generation: int,
    ) -> None:
        super().__init__()
        self._path   = path
        self._w      = width
        self._h      = height
        self._accent = accent_rgb
        self._gen    = generation
        self._stop   = False
        self._chunks: list[np.ndarray] = []
        self._samples = 0
        self._max_samples = _TARGET_SR * _MAX_SECONDS

    def cancel(self) -> None:
        self._stop = True

    # ── QThread entrypoint ────────────────────────────────────────────────

    def run(self) -> None:
        try:
            y = self._decode()
            if self._stop or y is None or y.size < _N_FFT:
                return
            img = self._render(self._stft(y))
            if not self._stop and img is not None:
                self.ready.emit(img, self._gen)
        except Exception:
            # Degradación elegante: sin espectrograma, sin ruido en consola.
            return

    # ── Decodificación → mono float32 ─────────────────────────────────────

    def _decode(self) -> np.ndarray | None:
        decoder = QAudioDecoder()

        fmt = QAudioFormat()
        fmt.setSampleRate(_TARGET_SR)
        fmt.setChannelCount(1)
        fmt.setSampleFormat(QAudioFormat.SampleFormat.Int16)
        decoder.setAudioFormat(fmt)
        decoder.setSource(QUrl.fromLocalFile(self._path))

        loop = QEventLoop()

        def on_buffer() -> None:
            while decoder.bufferAvailable():
                buf = decoder.read()
                mono = _buffer_to_mono(buf)
                if mono is not None and mono.size:
                    self._chunks.append(mono)
                    self._samples += mono.size
                if self._stop or self._samples >= self._max_samples:
                    decoder.stop()
                    loop.quit()
                    return

        decoder.bufferReady.connect(on_buffer)
        decoder.finished.connect(loop.quit)
        # QAudioDecoder.error es señal+getter (overload ambiguo en PyQt6); no la
        # conectamos. finished + timeout cubren el caso de fallo de decode.
        QTimer.singleShot(_DECODE_TIMEOUT, loop.quit)

        decoder.start()
        loop.exec()
        decoder.stop()

        if not self._chunks:
            return None
        return np.concatenate(self._chunks)[: self._max_samples]

    # ── STFT (numpy puro) → matriz 0..1 ───────────────────────────────────

    def _stft(self, y: np.ndarray) -> np.ndarray:
        win = np.hanning(_N_FFT).astype(np.float32)
        n_frames = 1 + (len(y) - _N_FFT) // _HOP
        if n_frames < 1:
            return np.zeros((1, 1), np.float32)

        # Matriz de frames (n_frames, n_fft) con ventana aplicada
        idx = np.arange(_N_FFT)[None, :] + _HOP * np.arange(n_frames)[:, None]
        frames = y[idx] * win

        mag = np.abs(np.fft.rfft(frames, axis=1))           # (n_frames, F)
        power = mag ** 2
        db = 10.0 * np.log10(power + 1e-9)

        lo, hi = np.percentile(db, 5), np.percentile(db, 99)
        if hi <= lo:
            hi = lo + 1.0
        norm = np.clip((db - lo) / (hi - lo), 0.0, 1.0)
        return norm.T                                       # (F, n_frames)

    # ── Render → QImage RGBA tenue ────────────────────────────────────────

    def _render(self, s: np.ndarray) -> QImage | None:
        if s.size == 0:
            return None
        f_bins, t_bins = s.shape
        fi = np.linspace(0, f_bins - 1, self._h).astype(int)
        ti = np.linspace(0, t_bins - 1, self._w).astype(int)
        grid = s[np.ix_(fi, ti)][::-1]                      # low freq abajo

        r, g, b = self._accent
        rgba = np.empty((self._h, self._w, 4), np.uint8)
        rgba[..., 0] = r
        rgba[..., 1] = g
        rgba[..., 2] = b
        # Alpha tenue: el banner ya tiene su fondo; esto solo lo matiza.
        rgba[..., 3] = (grid * 150).astype(np.uint8)

        rgba = np.ascontiguousarray(rgba)
        img = QImage(
            rgba.data, self._w, self._h, 4 * self._w,
            QImage.Format.Format_RGBA8888,
        )
        return img.copy()   # detach del buffer numpy antes de cruzar el hilo


# ── Helpers de formato ────────────────────────────────────────────────────

_DTYPE = {
    QAudioFormat.SampleFormat.UInt8: (np.uint8,  256.0,  128.0),
    QAudioFormat.SampleFormat.Int16: (np.int16,  32768.0, 0.0),
    QAudioFormat.SampleFormat.Int32: (np.int32,  2147483648.0, 0.0),
    QAudioFormat.SampleFormat.Float: (np.float32, 1.0,    0.0),
}


def _buffer_to_mono(buf) -> np.ndarray | None:
    """QAudioBuffer → numpy float32 mono en [-1, 1], tolerante al formato real."""
    fmt = buf.format()
    spec = _DTYPE.get(fmt.sampleFormat())
    if spec is None:
        return None
    dtype, scale, offset = spec

    data = buf.constData()
    data.setsize(buf.byteCount())
    arr = np.frombuffer(bytes(data), dtype=dtype).astype(np.float32)
    if offset:
        arr = arr - offset
    arr = arr / scale

    ch = max(1, fmt.channelCount())
    if ch > 1:
        usable = (arr.size // ch) * ch
        arr = arr[:usable].reshape(-1, ch).mean(axis=1)
    return arr
