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
    Hace existence checks con un cache compartido para no re-chequear el mismo
    archivo dos veces (crítico en discos USB/red donde cada stat puede tardar).
    """

    group_ready: pyqtSignal = pyqtSignal(object)  # GroupData
    finished: pyqtSignal    = pyqtSignal()

    def __init__(
        self,
        groups: list[GroupData],
        is_traktor: bool,
        exists_cache: dict[str, bool],
    ) -> None:
        super().__init__()
        self._groups       = groups
        self._is_traktor   = is_traktor
        self._exists_cache = exists_cache   # dict compartido — GIL-safe en CPython
        self._stop         = False

    def cancel(self) -> None:
        self._stop = True

    def _check(self, raw: str) -> bool:
        """Existence check con cache. Primer acceso hace I/O; resto es O(1)."""
        if raw in self._exists_cache:
            return self._exists_cache[raw]

        if self._is_traktor:
            result = Path(raw).exists()
        else:
            from rekordbox_export import resolve_path as _rp
            result = _rp(raw) is not None

        self._exists_cache[raw] = result
        return result

    def run(self) -> None:
        for group in self._groups:
            if self._stop:
                break
            for track in group.tracks:
                if self._stop:
                    break
                track.exists = self._check(track.raw_path) if track.raw_path else False
            self.group_ready.emit(group)
        self.finished.emit()
