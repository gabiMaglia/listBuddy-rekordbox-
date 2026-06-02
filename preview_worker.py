"""
preview_worker.py
-----------------
Background worker para el preview de salida.

Separación de responsabilidades:
  • Main thread  → extrae metadata de la DB (SQLAlchemy no es thread-safe).
  • Worker thread → hace Path.exists() / resolve_path() por cada track.
                    En discos USB o de red esto puede tomar segundos; nunca
                    debe bloquear la UI.

El worker emite group_ready por cada playlist a medida que termina,
de modo que los grupos aparecen incrementalmente en el panel derecho.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from PyQt6.QtCore import QThread, pyqtSignal


# ─────────────────────────────────── Data transfer objects ───────────────

@dataclass
class TrackRow:
    """Metadata de un track + resultado del existence check."""
    num: str         # "001"
    title: str
    artist: str
    ext: str
    raw_path: str
    exists: bool = True   # rellenado por el worker


@dataclass
class GroupData:
    """Datos completos de una playlist para renderizar en el preview."""
    name: str
    order: int
    total_count: int
    tracks: list[TrackRow] = field(default_factory=list)

    @property
    def missing_count(self) -> int:
        return sum(1 for t in self.tracks if not t.exists)


# ────────────────────────────────────────────────── Worker ───────────────

class PreviewWorker(QThread):
    """
    Recibe GroupData con raw_path ya extraído.
    Solo hace existence checks → emite group_ready cuando termina cada grupo.
    """

    group_ready: pyqtSignal = pyqtSignal(object)  # GroupData
    finished: pyqtSignal    = pyqtSignal()

    def __init__(self, groups: list[GroupData], is_traktor: bool) -> None:
        super().__init__()
        self._groups    = groups
        self._is_traktor = is_traktor
        self._stop       = False

    def cancel(self) -> None:
        self._stop = True

    def run(self) -> None:
        if not self._is_traktor:
            from rekordbox_export import resolve_path as _rp
        else:
            _rp = None

        for group in self._groups:
            if self._stop:
                break

            for track in group.tracks:
                if self._stop:
                    break
                raw = track.raw_path
                if not raw:
                    track.exists = False
                elif self._is_traktor:
                    track.exists = Path(raw).exists()
                else:
                    track.exists = _rp(raw) is not None  # type: ignore[misc]

            self.group_ready.emit(group)

        self.finished.emit()
