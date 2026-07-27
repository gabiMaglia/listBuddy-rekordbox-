"""
update_checker.py
------------------
T-021 (I-8, engram/07_production_readiness.md): chequeo de actualización
simple, NO un auto-updater. Al arrancar, consulta en background la API de
releases de GitHub y compara contra `_APP_VERSION` (ui.py). Si hay una
versión más nueva, emite una señal para que la UI muestre un aviso discreto
con un link — nunca bloquea el arranque ni molesta si falla.

Por qué QThread (mismo patrón que ExportWorker/PreviewWorker/RelocateWorker):
la request de red (incluso con timeout corto) no puede correr en el hilo de
UI sin congelar la ventana un instante en el peor caso (red lenta/rate
limit). Es un thread de un solo uso: corre `run()` una vez y termina, no
necesita cancelación intra-request (el timeout del socket ya acota cuánto
puede tardar).

Falla en silencio a propósito (sin internet, GitHub caído, rate limit,
JSON inesperado, tag_name no parseable): es una mejora opcional, no una
feature crítica — nunca debe interrumpir ni ensuciar la UI con un error.
"""
from __future__ import annotations

import json
import logging
import urllib.error
import urllib.request
from dataclasses import dataclass

from PyQt6.QtCore import QThread, pyqtSignal

_log = logging.getLogger("listBuddy")

_RELEASES_API_URL = (
    "https://api.github.com/repos/gabiMaglia/listBuddy-rekordbox-/releases/latest"
)
_RELEASES_PAGE_URL = "https://github.com/gabiMaglia/listBuddy-rekordbox-/releases"
_REQUEST_TIMEOUT_SECONDS = 4.0


@dataclass(frozen=True)
class UpdateInfo:
    """Datos mínimos que necesita la UI para armar el aviso discreto."""
    version: str   # ej. "1.2.0" (ya sin el prefijo "v")
    url: str       # link a la página del release (o al listado general si falta)


def _parse_version(raw: str) -> tuple[int, ...] | None:
    """
    "v1.2.0" / "1.2.0" -> (1, 2, 0). None si no matchea un semver numérico
    simple (ej. releases con sufijo "-beta" u otro formato inesperado) —
    nunca asumir, mejor no mostrar el aviso que mostrarlo mal.
    """
    text = raw.strip()
    if text[:1] in ("v", "V"):
        text = text[1:]
    parts = text.split(".")
    if not parts:
        return None
    try:
        return tuple(int(p) for p in parts)
    except ValueError:
        return None


def _is_newer(remote: tuple[int, ...], local: tuple[int, ...]) -> bool:
    """Compara tuplas de versión, rellenando con ceros la más corta."""
    length = max(len(remote), len(local))
    remote_padded = remote + (0,) * (length - len(remote))
    local_padded = local + (0,) * (length - len(local))
    return remote_padded > local_padded


class UpdateCheckWorker(QThread):
    """
    GET en background a la API de releases de GitHub. Emite
    `update_available` SOLO si hay una versión más nueva que la actual;
    ante cualquier falla (red, parseo, rate limit) no emite nada y no
    propaga la excepción — ver docstring del módulo.
    """

    update_available: pyqtSignal = pyqtSignal(object)  # UpdateInfo

    def __init__(self, current_version: str) -> None:
        super().__init__()
        self._current_version = current_version

    def run(self) -> None:
        try:
            local = _parse_version(self._current_version)
            if local is None:
                return

            request = urllib.request.Request(
                _RELEASES_API_URL,
                headers={
                    "Accept": "application/vnd.github+json",
                    # La API de GitHub responde 403 sin un User-Agent.
                    "User-Agent": "listBuddy-update-check",
                },
            )
            with urllib.request.urlopen(request, timeout=_REQUEST_TIMEOUT_SECONDS) as resp:
                payload = json.loads(resp.read().decode("utf-8"))

            tag_name = payload.get("tag_name")
            if not tag_name:
                return
            remote = _parse_version(tag_name)
            if remote is None:
                return

            if _is_newer(remote, local):
                url = payload.get("html_url") or _RELEASES_PAGE_URL
                version_text = ".".join(str(part) for part in remote)
                self.update_available.emit(UpdateInfo(version=version_text, url=url))

        except Exception as exc:  # noqa: BLE001 — fallo intencionalmente silencioso (I-8)
            # Se loguea a archivo (nivel INFO, no error) para poder diagnosticar
            # si hace falta, pero jamás se muestra nada al usuario por esto.
            _log.info("Chequeo de actualización omitido (%s: %s)", type(exc).__name__, exc)
