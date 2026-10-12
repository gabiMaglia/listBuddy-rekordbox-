"""footer.py — footer de 76 px: reproductor, destino, exportar y progreso (T-063)."""
from __future__ import annotations


def export_label(n: int) -> str:
    if n <= 0:
        return "Exportar playlists"
    return f"Exportar {n} playlist" if n == 1 else f"Exportar {n} playlists"


def format_ms(ms: int) -> str:
    s = max(0, ms // 1000)
    return f"{s // 60}:{s % 60:02d}"
