"""Bloques de filas rotas contiguas (T-071, estilo D) y estados/textos de la tarjeta de carpeta (T-065).

Sin Qt a propósito: la lógica se testea en el proceso de pytest sin cargar PySide6.
"""
from __future__ import annotations

from collections.abc import Sequence

NONE = "none"      # fila sana: sin bloque
ALONE = "alone"    # rota aislada: bloque de 1
START = "start"    # primera de un bloque
MIDDLE = "middle"
END = "end"

BLOCK_RADIUS = 8

OK, PARTIAL, ALL_BROKEN, EMPTY = "ok", "partial", "all_broken", "empty"
MISSING_NOTE = " · archivo no encontrado"


def group_state(total: int, missing: int) -> str:
    if total <= 0:
        return EMPTY
    if missing <= 0:
        return OK
    return ALL_BROKEN if missing >= total else PARTIAL


def all_broken_text(n: int) -> str:
    return f"{n} {'roto' if n == 1 else 'rotos'} — ningún archivo se encuentra. ¿Cambió el disco?"


def broken_notice_text(n: int) -> str:
    if n <= 0:
        return ""
    return "1 enlace roto" if n == 1 else f"{n} enlaces rotos"


def ext_chip_text(ext: str) -> str:
    return ext.lstrip(".").upper()


def block_positions(exists: Sequence[bool]) -> list[str]:
    """Posición de cada fila dentro de su bloque de rotas contiguas."""
    missing = [not e for e in exists]
    out: list[str] = []
    for i, m in enumerate(missing):
        if not m:
            out.append(NONE)
            continue
        prev_m = i > 0 and missing[i - 1]
        next_m = i + 1 < len(missing) and missing[i + 1]
        if prev_m and next_m:
            out.append(MIDDLE)
        elif prev_m:
            out.append(END)
        elif next_m:
            out.append(START)
        else:
            out.append(ALONE)
    return out


def corner_radii(pos: str, radius: int = BLOCK_RADIUS) -> tuple[int, int, int, int]:
    """Radios (arriba-izq, arriba-der, abajo-der, abajo-izq): solo esquinas externas del bloque."""
    top = radius if pos in (ALONE, START) else 0
    bottom = radius if pos in (ALONE, END) else 0
    return (top, top, bottom, bottom)


def border_sides(pos: str) -> tuple[bool, bool, bool, bool]:
    """Lados con borde (arriba, derecha, abajo, izquierda); entre filas del bloque no hay línea."""
    if pos == NONE:
        return (False, False, False, False)
    return (pos in (ALONE, START), True, pos in (ALONE, END), True)
