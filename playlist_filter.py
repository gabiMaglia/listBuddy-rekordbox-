# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2025-2026 Gabriel Maglia
"""Filtro de playlists por nombre: sin Qt, para poder testearlo en proceso."""
from __future__ import annotations

import unicodedata


def normalize(text: str) -> str:
    """Minúsculas y sin marcas diacríticas («Café» y «cafe» comparan igual)."""
    decomposed = unicodedata.normalize("NFKD", text.casefold())
    return "".join(ch for ch in decomposed if not unicodedata.combining(ch))


def matches(name: str, query: str) -> bool:
    q = normalize(query.strip())
    return not q or q in normalize(name)
