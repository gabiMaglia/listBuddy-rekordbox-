"""
test_traktor_paths.py
----------------------
Tests de correctitud del encoder/decoder de rutas de Traktor (traktor_db.py).

Por qué estos son los tests más importantes del proyecto: `path_to_location`
es el punto de correctitud central de F-07 (relocate) — un encoding equivocado
o bien no resuelve en Traktor, o *peor*, resuelve silenciosamente al archivo
equivocado y el DJ toca la pista incorrecta en un set (ADR-001). Antes de este
feature la app solo leía; ahora ESCRIBE el NML del usuario, así que la
correctitud del round-trip encode↔decode protege directamente contra corromper
la librería.

Los casos con letra de unidad (Windows) son la rama VERIFICADA del encoder
(ADR-001). La rama macOS ("Macintosh HD" placeholder) queda como deuda D-02
(sin Mac para validar) y se cubre solo su comportamiento documentado, no su
correctitud contra un NML real de macOS.
"""
from __future__ import annotations

from pathlib import Path, PurePosixPath, PureWindowsPath

import pytest

from traktor_db import (
    _location_to_key,
    _location_to_path,
    _nml_key_to_path,
    path_to_key,
    path_to_location,
)


# ─────────────────────────── decoder: KEY → path ──────────────────────────

class TestNmlKeyToPath:
    def test_strips_volume_and_unpacks_separator(self):
        key = "Macintosh HD/:Users/:user/:Music/:file.mp3"
        assert _nml_key_to_path(key) == Path("/Users/user/Music/file.mp3")

    def test_key_without_separator_returned_as_is(self):
        assert _nml_key_to_path("plain.mp3") == Path("plain.mp3")


# ─────────────────────────── KEY reconstruction ───────────────────────────

class TestLocationToKey:
    def test_literal_concatenation_volume_dir_file(self):
        # KEY es la concatenación LITERAL VOLUME+DIR+FILE (ADR-001): es la FK
        # que liga PRIMARYKEY de la playlist con la ENTRY de la colección.
        assert (
            _location_to_key("C:", "/:Users/:dj/:Music/:", "Track01.mp3")
            == "C:/:Users/:dj/:Music/:Track01.mp3"
        )

    def test_macos_volume_label(self):
        assert (
            _location_to_key("Macintosh HD", "/:Users/:u/:", "t.mp3")
            == "Macintosh HD/:Users/:u/:t.mp3"
        )


# ─────────────────────────── decoder: honra VOLUME (T-004) ────────────────

class TestLocationToPathHonorsVolume:
    """Regresión de T-004/D-01: en Windows el path debe llevar la unidad real,
    no resolverse contra la unidad del proceso."""

    def test_windows_drive_letter_prepended(self):
        p = _location_to_path("I:", "/:Music/:", "t.mp3")
        assert p == Path("I:/Music/t.mp3")

    def test_windows_drive_is_absolute_on_that_volume(self):
        p = _location_to_path("I:", "/:Music/:", "t.mp3")
        # El bug original resolvía contra el cwd → drive equivocado.
        assert PureWindowsPath(p).drive.upper() == "I:"

    def test_macos_volume_label_not_treated_as_drive(self):
        # "Macintosh HD" NO matchea ^[A-Za-z]:$ → no se antepone (comportamiento
        # documentado; la resolución real en macOS es deuda D-02). El DIR de
        # Traktor siempre arranca con "/:" → el decode queda anclado a "/".
        p = _location_to_path("Macintosh HD", "/:Users/:u/:", "t.mp3")
        assert p == Path("/Users/u/t.mp3")

    def test_empty_volume_falls_back_to_relative(self):
        p = _location_to_path("", "/:Music/:", "t.mp3")
        assert p == Path("/Music/t.mp3")


# ─────────────────────────── encoder: path → LOCATION ─────────────────────

class TestPathToLocationWindows:
    """Rama VERIFICADA del encoder (ADR-001). Estos son los casos que el motor
    de relocate escribe realmente en el NML del usuario en Windows."""

    def test_basic_windows_path(self):
        vol, dir_attr, file_attr = path_to_location(PureWindowsPath(r"D:\Music\dj\t.mp3"))
        assert vol == "D:"
        assert dir_attr == "/:Music/:dj/:"
        assert file_attr == "t.mp3"

    def test_dir_wraps_every_segment_with_separator(self):
        _, dir_attr, _ = path_to_location(PureWindowsPath(r"C:\A\B\C\song.mp3"))
        # Cada segmento envuelto en su propio "/:" + trailing "/:".
        assert dir_attr == "/:A/:B/:C/:"

    def test_file_at_drive_root_has_only_trailing_separator(self):
        vol, dir_attr, file_attr = path_to_location(PureWindowsPath(r"E:\loose.mp3"))
        assert vol == "E:"
        assert dir_attr == "/:"
        assert file_attr == "loose.mp3"

    def test_unc_path_raises_not_implemented(self):
        # Rutas de red: formato sin verificar → fail loud, nunca escribir un
        # LOCATION adivinado (podría corromper el link).
        with pytest.raises(NotImplementedError):
            path_to_location(PureWindowsPath(r"\\server\share\Music\t.mp3"))

    def test_relative_path_raises(self):
        with pytest.raises(ValueError):
            path_to_location(PureWindowsPath(r"Music\t.mp3"))


class TestPathToLocationMacos:
    """Rama best-effort UNVERIFIED (deuda D-02). Se testea el comportamiento
    documentado, no correctitud contra NML real de macOS."""

    def test_external_volume_extracts_name(self):
        # PurePosixPath: en un runner Windows, Path("/Volumes/...") no sería
        # "absoluto" (falta drive) y el encoder abortaría — se fuerza semántica
        # POSIX para ejercitar la rama macOS de forma determinista.
        vol, dir_attr, file_attr = path_to_location(PurePosixPath("/Volumes/USB_DISK/Music/t.mp3"))
        assert vol == "USB_DISK"
        assert dir_attr == "/:Music/:"
        assert file_attr == "t.mp3"

    def test_boot_volume_uses_placeholder(self):
        vol, _, _ = path_to_location(PurePosixPath("/Users/dj/Music/t.mp3"))
        assert vol == "Macintosh HD"  # placeholder documentado, D-02


# ─────────────────────────── round-trip (el invariante clave) ─────────────

class TestRoundTrip:
    """encode(path) → decode debe volver al path original en Windows. Este
    invariante es la garantía de que un relocate no rompe el link."""

    @pytest.mark.parametrize("winpath", [
        r"D:\Music\dj\t.mp3",
        r"C:\A\B\C\song.flac",
        r"I:\LISTAS\Track 01 - Artist - Title.aiff",
        r"E:\loose.mp3",
    ])
    def test_encode_then_decode_recovers_windows_path(self, winpath):
        vol, dir_attr, file_attr = path_to_location(PureWindowsPath(winpath))
        recovered = _location_to_path(vol, dir_attr, file_attr)
        assert PureWindowsPath(recovered) == PureWindowsPath(winpath)

    def test_path_to_key_matches_manual_concatenation(self):
        p = PureWindowsPath(r"D:\Music\t.mp3")
        vol, dir_attr, file_attr = path_to_location(p)
        assert path_to_key(p) == _location_to_key(vol, dir_attr, file_attr)

    def test_key_is_consistent_between_encode_and_decode_family(self):
        # El new_key que apply_relocation escribe en las PRIMARYKEY de la
        # playlist debe ser EXACTAMENTE la concatenación que Traktor espera.
        p = PureWindowsPath(r"I:\Music\sub\t.mp3")
        assert path_to_key(p) == "I:/:Music/:sub/:t.mp3"
