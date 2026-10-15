"""
waveform_worker.py
------------------
Energía (RMS en dB) y tono (graves/agudos) de un tema completo para la onda del footer.

Decodifica con QAudioDecoder (mismo backend que la reproducción, mismos formatos),
guarda SOLO RMS y tono de cada ventana de ~50 ms (no el audio) y emite un `WaveData`. Corre en un QThread con su propio event loop: la UI nunca se bloquea.
A diferencia del espectrograma que reemplaza no hay tope de 90 s: la onda tiene que
representar el tema entero para que el click haga seek al lugar correcto.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from PySide6.QtCore import QEventLoop, QThread, QTimer, QUrl, Signal
from PySide6.QtMultimedia import QAudioDecoder, QAudioFormat

from audio_decode import buffer_to_mono

TARGET_SR = 11025
WIN = 551                      # ≈ 50 ms a 11025 Hz
MAX_SECONDS = 20 * 60          # tope de seguridad (sets larguísimos)
DECODE_TIMEOUT = 90_000        # ms; corta si el decode se cuelga
LO_HZ = 180.0                  # graves (bombo/bajo): por debajo
HI_HZ = 2500.0                 # agudos (hats/voces): desde acá
DB_RANGE = 24.0                # rango dinámico mostrado, en dB bajo lo más fuerte
SILENCE_RMS = 1e-4             # tema (casi) mudo: onda en el piso, sin amplificar ruido


@dataclass(frozen=True)
class WaveData:
    """Onda lista para dibujar: `levels` (energía en dB, 0..1) y `tone` (0 graves … 1 agudos)."""

    levels: tuple[float, ...]
    tone: tuple[float, ...]


def window_features(
    samples: np.ndarray, carry: np.ndarray, win: int = WIN, sr: int = TARGET_SR
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """RMS y tono crudo por ventana; lo que no completa una ventana vuelve como `carry`.

    tono crudo = hi / (hi + lo): hi = suma de |X| desde HI_HZ, lo = suma de |X| bajo LO_HZ
    (FFT con ventana Hann). Es invariante al corte en chunks porque el carry guarda muestras.
    """
    data = np.concatenate([carry, samples]) if carry.size else samples
    n = data.size // win
    if n == 0:
        return np.empty(0, np.float32), np.empty(0, np.float32), data
    block = data[: n * win].reshape(n, win).astype(np.float32, copy=False)
    rms = np.sqrt((block.astype(np.float64) ** 2).mean(axis=1)).astype(np.float32)
    spec = np.abs(np.fft.rfft(block * np.hanning(win).astype(np.float32), axis=1))
    freqs = np.fft.rfftfreq(win, 1.0 / sr)
    hi = spec[:, freqs >= HI_HZ].sum(axis=1)
    lo = spec[:, freqs < LO_HZ].sum(axis=1)
    tone = (hi / (hi + lo + 1e-9)).astype(np.float32)
    return rms, tone, data[n * win:]


def finalize_wave(rms: np.ndarray, tone: np.ndarray) -> WaveData:
    """Niveles en dB relativos a lo más fuerte del tema y tono normalizado por percentiles."""
    if rms.size == 0:
        return WaveData((), ())
    d = 20.0 * np.log10(np.maximum(rms.astype(np.float64), 1e-9))
    top = float(np.percentile(d, 99.5))
    if float(rms.max()) < SILENCE_RMS:
        levels = np.zeros(rms.size)
    else:
        levels = np.clip((d - (top - DB_RANGE)) / DB_RANGE, 0.0, 1.0)
    t = tone.astype(np.float64)
    p5, p95 = float(np.percentile(t, 5)), float(np.percentile(t, 95))
    if p95 - p5 < 1e-6:
        tn = np.full(rms.size, 0.5)
    else:
        tn = np.clip((t - p5) / (p95 - p5), 0.0, 1.0)
    return WaveData(tuple(levels.tolist()), tuple(tn.tolist()))


class WaveformWorker(QThread):
    ready: Signal = Signal(object, int)   # (WaveData, generation)

    def __init__(self, path: str, generation: int) -> None:
        super().__init__()
        self.path = path
        self._gen = generation
        self._stop = False
        self._rms: list[np.ndarray] = []
        self._tone: list[np.ndarray] = []
        self._carry = np.empty(0, np.float32)
        self._samples = 0

    def cancel(self) -> None:
        self._stop = True

    def run(self) -> None:
        try:
            self._decode()
            if self._stop or not self._rms:
                return
            data = finalize_wave(np.concatenate(self._rms), np.concatenate(self._tone))
            if data.levels and not self._stop:
                self.ready.emit(data, self._gen)
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
                    rms, tone, self._carry = window_features(mono, self._carry)
                    if rms.size:
                        self._rms.append(rms)
                        self._tone.append(tone)
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
