"""
audio_player.py
---------------
Reproducción de audio para el preview de listBuddy.

Envuelve QMediaPlayer + QAudioOutput (PyQt6.QtMultimedia). PyQt6 6.11 trae el
backend multimedia de FFmpeg embebido, que decodifica mp3 / wav / aiff / mp4 /
m4a / flac / wma de forma nativa (FLAC y WMA incluidos). QMediaPlayer es
asíncrono por diseño: play() retorna al instante y el decode corre en el hilo
multimedia de Qt — nunca bloquea la UI.

Si algún archivo puntual no se puede decodificar, se reporta vía la señal
`error` sin romper el estado del player (degradación elegante).
"""
from __future__ import annotations

from PyQt6.QtCore import QObject, QUrl, pyqtSignal
from PyQt6.QtMultimedia import QAudioOutput, QMediaPlayer


class AudioPlayer(QObject):
    """Player de un solo track reutilizable. Estado mínimo, todo por señales."""

    playing_changed:  pyqtSignal = pyqtSignal(bool)       # True=reproduciendo
    track_changed:    pyqtSignal = pyqtSignal(str)        # path actual
    error:            pyqtSignal = pyqtSignal(str)        # mensaje legible
    position_changed: pyqtSignal = pyqtSignal(int, int)  # (pos_ms, dur_ms)
    track_finished:   pyqtSignal = pyqtSignal()          # llegó al final

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._player = QMediaPlayer(self)
        self._output = QAudioOutput(self)
        self._output.setVolume(0.9)
        self._player.setAudioOutput(self._output)
        self._current: str = ""

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
        self._current = path
        self._player.setSource(QUrl.fromLocalFile(path))
        self._player.play()
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

    def current_path(self) -> str:
        return self._current

    def is_playing(self) -> bool:
        return (
            self._player.playbackState()
            == QMediaPlayer.PlaybackState.PlayingState
        )

    # ── Internos ──────────────────────────────────────────────────────────

    def _on_state(self, state: QMediaPlayer.PlaybackState) -> None:
        self.playing_changed.emit(
            state == QMediaPlayer.PlaybackState.PlayingState
        )

    def _on_error(self, _err: QMediaPlayer.Error, msg: str) -> None:
        if _err != QMediaPlayer.Error.NoError:
            self.error.emit(msg or "No se pudo reproducir el archivo")

    def _on_position(self, pos: int) -> None:
        self.position_changed.emit(pos, self._player.duration())

    def _on_duration(self, dur: int) -> None:
        self.position_changed.emit(self._player.position(), dur)

    def _on_media_status(self, status: QMediaPlayer.MediaStatus) -> None:
        if status == QMediaPlayer.MediaStatus.EndOfMedia:
            self.track_finished.emit()
