"""Cancelación cooperativa de la carga de una librería (T-094)."""
from __future__ import annotations

from typing import Callable

# `should_cancel()` devuelve True cuando el hilo de carga fue interrumpido.
CancelCheck = Callable[[], bool]

# Cada cuántos eventos del parser se consulta la cancelación (barato pero no gratis).
CHECK_EVERY = 2048


class LoadCancelled(Exception):
    """La carga se abandonó porque otra la reemplazó o se cerró la ventana."""
