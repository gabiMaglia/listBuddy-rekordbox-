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

from PySide6.QtCore import QThread, Signal


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
    key: str = ""          # Camelot/Open Key tal cual viene de la fuente
    bpm: float | None = None
    relocated: bool = False  # ruta reparada por List Buddy (Rekordbox XML)
    streaming: bool = False  # pista de streaming: no es un archivo, nunca «rota»


@dataclass
class GroupData:
    """Datos completos de una playlist para renderizar en el preview."""
    name: str
    order: int
    total_count: int
    tracks: list[TrackRow] = field(default_factory=list)
    # T-015: referencia a la PlaylistCard del árbol izquierdo que originó este
    # grupo — permite que el botón "✕" del header (ui.py._render_group_header)
    # destilde el checkbox real en vez de reimplementar la lógica de selección.
    # Tipado como `object` (no PlaylistCard) para no importar widgets acá:
    # preview_worker.py corre en el QThread y no debe acoplarse a widgets Qt,
    # solo transporta la referencia sin tocarla (el worker jamás llama métodos
    # de `card`, ver PreviewWorker.run() más abajo).
    card: object = None

    @property
    def missing_count(self) -> int:
        return sum(1 for t in self.tracks if not t.exists)


# ────────────────────────────────────────────────── Worker ───────────────

def path_exists(raw: str, is_traktor: bool) -> bool:
    """Existencia real en disco de una ruta de la librería (sin cache)."""
    if is_traktor:
        return Path(raw).exists()
    from rekordbox_export import resolve_path as _rp
    return _rp(raw) is not None


class ExistenceRecheckWorker(QThread):
    """TEC-18: vuelve a mirar en disco las rutas ya dibujadas (se conectó el disco, se
    borró un archivo) sin congelar la UI. Emite `changed(True)` si alguna cambió de estado."""

    changed: Signal = Signal(bool)

    def __init__(self, known: dict[str, bool], is_traktor: bool) -> None:
        super().__init__()
        self._known = known
        self._is_traktor = is_traktor

    def run(self) -> None:
        diff = False
        for raw, was in self._known.items():
            if self.isInterruptionRequested():
                return
            if path_exists(raw, self._is_traktor) != was:
                diff = True
                break
        self.changed.emit(diff)


class PreviewWorker(QThread):
    """
    Recibe GroupData con raw_path ya extraído.
    Hace existence checks con un cache compartido para no re-chequear el mismo
    archivo dos veces (crítico en discos USB/red donde cada stat puede tardar).
    """

    group_ready: Signal = Signal(object)  # GroupData
    # No se llama `finished`: pisaría QThread.finished, que Qt emite recién
    # cuando el hilo terminó de verdad (no al salir del bucle de run()).
    done: Signal        = Signal()

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

    def _stopped(self) -> bool:
        return self._stop or self.isInterruptionRequested()

    def _check(self, raw: str) -> bool:
        """Existence check con cache. Primer acceso hace I/O; resto es O(1)."""
        if raw in self._exists_cache:
            return self._exists_cache[raw]

        result = path_exists(raw, self._is_traktor)
        self._exists_cache[raw] = result
        return result

    def run(self) -> None:
        for group in self._groups:
            if self._stopped():
                break
            for track in group.tracks:
                if self._stopped():
                    break
                if track.streaming:
                    track.exists = True
                else:
                    track.exists = self._check(track.raw_path) if track.raw_path else False
            self.group_ready.emit(group)
        self.done.emit()
