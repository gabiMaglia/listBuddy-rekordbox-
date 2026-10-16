"""
library_load_worker.py
----------------------
Lee la librería (Rekordbox XML o Traktor NML) en un QThread para no congelar
la ventana (T-094 / TEC-05). Todo el I/O de la carga vive acá: el parseo, el
`stat` de la fecha de exportación y el `exists()` de las reparaciones guardadas.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from PySide6.QtCore import QThread, Signal

import rekordbox_xml
from load_cancel import LoadCancelled
from rekordbox_fixes import FixStore

_log = logging.getLogger(__name__)


@dataclass
class LibraryLoadResult:
    token: int                  # generación de la carga que lo produjo
    source: str                 # "rekordbox" | "traktor"
    db: Any                     # RekordboxXmlLibrary | TraktorCollection
    tree: list[dict]


class LibraryLoadWorker(QThread):
    """`loaded(LibraryLoadResult)` o `failed(token, mensaje)`; nada si se canceló.

    Cancelación cooperativa con `requestInterruption()`; el parser la consulta
    cada bloque leído. `token` identifica la carga: Qt entrega igual las señales
    ya encoladas de un worker cancelado, y la ventana las descarta por token.
    """

    loaded = Signal(object)
    failed = Signal(int, str)
    progress = Signal(int, int)   # (token, porcentaje 0-100); solo cuando el entero cambia

    def __init__(self, token: int, source: str, path: Path | None, fixes: FixStore, parent=None) -> None:
        super().__init__(parent)
        self._token = token
        self._source = source
        self._path = path
        self._fixes = fixes
        self._last_pct = -1

    def run(self) -> None:
        try:
            result = self._load()
        except LoadCancelled:
            return
        except RuntimeError as e:      # mensajes pensados para el usuario
            if not self.isInterruptionRequested():
                self.failed.emit(self._token, str(e))
            return
        except Exception as e:         # un bug no debe dejar la ventana en «Cargando…» para siempre
            _log.exception("Falló la carga de la librería")
            if not self.isInterruptionRequested():
                self.failed.emit(self._token, f"No se pudo leer la librería.\n\nDetalle: {e}")
            return
        if not self.isInterruptionRequested():
            self.loaded.emit(result)

    def _report(self, done: int, total: int) -> None:
        pct = min(100, done * 100 // total) if total > 0 else 0
        if pct != self._last_pct:
            self._last_pct = pct
            self.progress.emit(self._token, pct)

    def _load(self) -> LibraryLoadResult:
        cancelled = self.isInterruptionRequested
        if self._source == "traktor":
            from traktor_db import get_playlist_tree, open_collection
            col = open_collection(self._path, should_cancel=cancelled, on_progress=self._report)
            return LibraryLoadResult(self._token, "traktor", col, get_playlist_tree(col))
        lib = rekordbox_xml.open_library(
            self._path, fixes=self._fixes.load(), should_cancel=cancelled, on_progress=self._report,
        )
        return LibraryLoadResult(self._token, "rekordbox", lib, rekordbox_xml.get_playlist_tree(lib))
