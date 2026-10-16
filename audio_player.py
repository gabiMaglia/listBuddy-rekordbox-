"""
audio_player.py
---------------
Reproducción de audio para el preview de listBuddy.

Envuelve QMediaPlayer + QAudioOutput (PySide6.QtMultimedia). PySide6 6.11 trae el
backend multimedia de FFmpeg embebido, que decodifica mp3 / wav / aiff / mp4 /
m4a / flac / wma de forma nativa (FLAC y WMA incluidos). QMediaPlayer es
asíncrono por diseño: play() retorna al instante y el decode corre en el hilo
multimedia de Qt — nunca bloquea la UI.

Si algún archivo puntual no se puede decodificar, se reporta vía la señal
`error` sin romper el estado del player (degradación elegante).
"""
from __future__ import annotations

from PySide6.QtCore import QObject, QUrl, Signal
from PySide6.QtMultimedia import QAudioOutput, QMediaPlayer

from audio_formats import NOT_PLAYABLE_MESSAGE, is_playable_audio


class AudioPlayer(QObject):
    """Player de un solo track reutilizable. Estado mínimo, todo por señales."""

    playing_changed:  Signal = Signal(bool)       # True=reproduciendo
    track_changed:    Signal = Signal(str)        # path actual
    error:            Signal = Signal(str)        # mensaje legible
    position_changed: Signal = Signal(int, int)  # (pos_ms, dur_ms)
    track_finished:   Signal = Signal()          # llegó al final

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._player = QMediaPlayer(self)
        self._output = QAudioOutput(self)
        self._output.setVolume(0.9)
        self._player.setAudioOutput(self._output)
        self._current: str = ""
        self._last_playing = False
        self._switching = False

        self._player.playbackStateChanged.connect(self._on_state)
        self._player.errorOccurred.connect(self._on_error)
        self._player.positionChanged.connect(self._on_position)
        self._player.durationChanged.connect(self._on_duration)
        self._player.mediaStatusChanged.connect(self._on_media_status)

    # ── API ───────────────────────────────────────────────────────────────

    def play(self, path: str) -> None:
        """Carga y reproduce `path`. No bloquea."""
        if not path:
            return
        if not is_playable_audio(path):
            self.error.emit(NOT_PLAYABLE_MESSAGE)   # sin abrir el archivo (SEC-18)
            return
        self._current = path
        # setSource() pasa por Stopped un instante: no es un corte real del usuario.
        self._switching = True
        try:
            self._player.setSource(QUrl.fromLocalFile(path))
            self._player.play()
        finally:
            self._switching = False
        self.track_changed.emit(path)

    def toggle(self) -> None:
        """Pausa si está sonando; reanuda si está pausado; no-op sin fuente."""
        if not self._current:
            return
        if self._player.playbackState() == QMediaPlayer.PlaybackState.PlayingState:
            self._player.pause()
        else:
            self._player.play()

    def seek(self, ms: int) -> None:
        self._player.setPosition(int(ms))

    def duration(self) -> int:
        return self._player.duration()

    def stop(self) -> None:
        self._player.stop()

    def set_volume(self, value: float) -> None:
        self._output.setVolume(max(0.0, min(1.0, value)))

    def set_output_device(self, device) -> None:
        """Cambia el dispositivo de salida (QAudioDevice). No corta la reproducción."""
        self._output.setDevice(device)

    def current_path(self) -> str:
        return self._current

    def is_playing(self) -> bool:
        return (
            self._player.playbackState()
            == QMediaPlayer.PlaybackState.PlayingState
        )

    # ── Internos ──────────────────────────────────────────────────────────

    def _on_state(self, state: QMediaPlayer.PlaybackState) -> None:
        playing = state == QMediaPlayer.PlaybackState.PlayingState
        if self._switching and not playing and self._last_playing:
            return
        if playing != self._last_playing:
            self._last_playing = playing
            self.playing_changed.emit(playing)

    def _on_error(self, _err: QMediaPlayer.Error, msg: str) -> None:
        if _err != QMediaPlayer.Error.NoError:
            # Un error es una parada real: sin esto la próxima pista que suene no emite True.
            if self._last_playing:
                self._last_playing = False
                self.playing_changed.emit(False)
            self.error.emit(msg or "No se pudo reproducir el archivo")

    def _on_position(self, pos: int) -> None:
        self.position_changed.emit(pos, self._player.duration())

    def _on_duration(self, dur: int) -> None:
        self.position_changed.emit(self._player.position(), dur)

    def _on_media_status(self, status: QMediaPlayer.MediaStatus) -> None:
        if status == QMediaPlayer.MediaStatus.EndOfMedia:
            self.track_finished.emit()
