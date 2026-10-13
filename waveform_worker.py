"""
waveform_worker.py
------------------
Picos de volumen de un tema completo para la onda del footer.

Decodifica con QAudioDecoder (mismo backend que la reproducción, mismos formatos),
guarda SOLO el pico absoluto de cada ventana de ~50 ms (no el audio) y emite la lista
normalizada. Corre en un QThread con su propio event loop: la UI nunca se bloquea.
A diferencia del espectrograma que reemplaza no hay tope de 90 s: la onda tiene que
representar el tema entero para que el click haga seek al lugar correcto.
"""
from __future__ import annotations

import numpy as np
from PySide6.QtCore import QEventLoop, QThread, QTimer, QUrl, Signal
from PySide6.QtMultimedia import QAudioDecoder, QAudioFormat

from audio_decode import buffer_to_mono

TARGET_SR = 11025
WIN = 551                      # ≈ 50 ms a 11025 Hz
MAX_SECONDS = 20 * 60          # tope de seguridad (sets larguísimos)
DECODE_TIMEOUT = 90_000        # ms; corta si el decode se cuelga


def window_peaks(
    samples: np.ndarray, carry: np.ndarray, win: int = WIN
) -> tuple[np.ndarray, np.ndarray]:
    """Pico absoluto por ventana; lo que no completa una ventana vuelve como `carry`."""
    mag = np.abs(samples)
    data = np.concatenate([carry, mag]) if carry.size else mag
    n = data.size // win
    if n == 0:
        return np.empty(0, np.float32), data
    peaks = data[: n * win].reshape(n, win).max(axis=1).astype(np.float32)
    return peaks, data[n * win:]


def normalize_peaks(peaks: np.ndarray) -> list[float]:
    """0..1 con techo en el percentil 99: un click aislado no aplasta el resto."""
    if peaks.size == 0:
        return []
    ceiling = float(np.percentile(peaks, 99))
    if ceiling <= 1e-6:
        return [0.0] * int(peaks.size)
    return np.clip(peaks / ceiling, 0.0, 1.0).tolist()


class WaveformWorker(QThread):
    ready: Signal = Signal(object, int)   # (picos normalizados, generation)

    def __init__(self, path: str, generation: int) -> None:
        super().__init__()
        self.path = path
        self._gen = generation
        self._stop = False
        self._parts: list[np.ndarray] = []
        self._carry = np.empty(0, np.float32)
        self._samples = 0

    def cancel(self) -> None:
        self._stop = True

    def run(self) -> None:
        try:
            self._decode()
            if self._stop or not self._parts:
                return
            peaks = normalize_peaks(np.concatenate(self._parts))
            if peaks and not self._stop:
                self.ready.emit(peaks, self._gen)
        except Exception:
            return  # sin onda, sin ruido: el player sigue funcionando

    def _decode(self) -> None:
        decoder = QAudioDecoder()
        fmt = QAudioFormat()
        fmt.setSampleRate(TARGET_SR)
        fmt.setChannelCount(1)
        fmt.setSampleFormat(QAudioFormat.SampleFormat.Int16)
        decoder.setAudioFormat(fmt)
        decoder.setSource(QUrl.fromLocalFile(self.path))
        loop = QEventLoop()
        limit = TARGET_SR * MAX_SECONDS

        def on_buffer() -> None:
            while decoder.bufferAvailable():
                mono = buffer_to_mono(decoder.read())
                if mono is not None and mono.size:
                    peaks, self._carry = window_peaks(mono, self._carry)
                    if peaks.size:
                        self._parts.append(peaks)
                    self._samples += mono.size
                if self._stop or self._samples >= limit:
                    decoder.stop()
                    loop.quit()
                    return

        decoder.bufferReady.connect(on_buffer)
        decoder.finished.connect(loop.quit)
        QTimer.singleShot(DECODE_TIMEOUT, loop.quit)
        decoder.start()
        loop.exec()
        decoder.stop()
