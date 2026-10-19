# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2025-2026 Gabriel Maglia
"""Lista blanca de extensiones que se abren con FFmpeg (SEC-18).

Una librería puede apuntar a cualquier archivo; solo los formatos de audio conocidos llegan
al demuxer del reproductor y de la onda. Listas de reproducción (m3u8) y contenedores de
scripting (ffconcat) quedan afuera a propósito.
"""
from __future__ import annotations

from pathlib import Path

AUDIO_EXTENSIONS = frozenset({
    ".mp3", ".m4a", ".mp4", ".aac", ".flac", ".wav", ".aif", ".aiff", ".ogg", ".opus", ".wma",
})

NOT_PLAYABLE_MESSAGE = "Este archivo no es un formato de audio reproducible"


def is_playable_audio(path: str) -> bool:
    return Path(path).suffix.lower() in AUDIO_EXTENSIONS
