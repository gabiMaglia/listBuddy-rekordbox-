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
(ADR-001). La rama macOS quedó documentada como deuda D-02 (sin Mac para
validar, placeholder "Macintosh HD" hardcodeado) hasta T-023/B-5
(2026-08-01): confirmado como bug real contra el NML macOS real del PO
(`~/Documents/Native Instruments/Traktor 4.4.1/collection.nml`, solo
lectura) — el hardcode solo acertaba por coincidencia en el volumen de
arranque de ESA Mac en particular. Los tests de `TestPathToLocationMacos` y
`TestRoundTripMacos` de acá abajo usan samples reales tomados de ese NML
(3 volúmenes: "Macintosh HD" boot/3965 tracks, "MUSIC" externo/1763 tracks,
"NO NAME" externo/36 tracks) — ver detalle de verificación completa en el
handoff de T-023 (no se commitea el NML real del PO al repo).
"""
from __future__ import annotations

from pathlib import Path, PurePosixPath, PureWindowsPath

import pytest

import traktor_db
from traktor_db import (
    _location_to_key,
    _location_to_path,
    _nml_key_to_path,
    path_to_key,
    path_to_location,
)


@pytest.fixture(autouse=True)
def _clear_boot_volume_cache():
    """
    `_boot_volume_name()` cachea con `functools.lru_cache` (T-023): sin este
    fixture, el primer test que la ejercite fija el resultado para el resto
    de la sesión de pytest, incluso los que monkeypatchean `subprocess.run`
    para simular otro nombre de disco/plataforma.
    """
    traktor_db._boot_volume_name.cache_clear()
    yield
    traktor_db._boot_volume_name.cache_clear()


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

    def test_macos_boot_volume_label_not_prepended(self, monkeypatch):
        # El label del disco de arranque NO es un componente de path: su DIR
        # ya es absoluto desde "/". Se monkeypatchea el nombre para que el
        # test no dependa de cómo se llame el disco de quien corre la suite.
        monkeypatch.setattr(traktor_db.platform, "system", lambda: "Darwin")
        monkeypatch.setattr(traktor_db, "_boot_volume_name", lambda: "Macintosh HD")
        p = _location_to_path("Macintosh HD", "/:Users/:u/:", "t.mp3")
        assert p == Path("/Users/u/t.mp3")

    def test_empty_volume_falls_back_to_relative(self):
        p = _location_to_path("", "/:Music/:", "t.mp3")
        assert p == Path("/Music/t.mp3")


class TestLocationToPathExternalVolumeMacos:
    """Regresión de T-027: el gemelo macOS del bug de T-004. Un disco externo
    se monta en /Volumes/<Name> y Traktor guarda DIR relativo a ese punto de
    montaje; ignorar VOLUME resolvía contra la raíz del disco de arranque y
    marcaba como rota una pista sana, antes Y después de un relocate exitoso.
    Confirmado con el NML real del PO: /Volumes/MUSIC/quilombo/... se decodeaba
    como /quilombo/... (1592 pistas sanas en rojo)."""

    @pytest.fixture(autouse=True)
    def _as_macos(self, monkeypatch):
        monkeypatch.setattr(traktor_db.platform, "system", lambda: "Darwin")
        monkeypatch.setattr(traktor_db, "_boot_volume_name", lambda: "Macintosh HD")

    def test_external_volume_is_prefixed_with_volumes(self):
        p = _location_to_path("MUSIC", "/:quilombo/:Sets/:", "t.aiff")
        assert p == Path("/Volumes/MUSIC/quilombo/Sets/t.aiff")

    def test_external_volume_at_mountpoint_root(self):
        p = _location_to_path("MUSIC", "/:", "t.wav")
        assert p == Path("/Volumes/MUSIC/t.wav")

    def test_volume_name_with_spaces(self):
        # "NO NAME" es un volumen real en la colección del PO.
        p = _location_to_path("NO NAME", "/:dj/:", "t.mp3")
        assert p == Path("/Volumes/NO NAME/dj/t.mp3")

    def test_round_trip_external_volume(self):
        # Simetría con el encoder de T-023: decode → encode debe volver igual.
        original = Path("/Volumes/MUSIC/quilombo/Sets/t.aiff")
        vol, dir_attr, file_attr = traktor_db.path_to_location(original)
        assert _location_to_path(vol, dir_attr, file_attr) == original

    def test_round_trip_boot_volume(self):
        original = Path("/Users/u/Music/t.mp3")
        vol, dir_attr, file_attr = traktor_db.path_to_location(original)
        assert _location_to_path(vol, dir_attr, file_attr) == original

    def test_windows_drive_still_wins_over_volumes_prefix(self):
        # No-regresión de T-004: una letra de unidad nunca debe pasar por la
        # rama de /Volumes, ni siquiera corriendo en macOS.
        p = _location_to_path("I:", "/:Music/:", "t.mp3")
        assert p == Path("I:/Music/t.mp3")


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


class TestBootVolumeName:
    """
    T-023/B-5: `_boot_volume_name()` reemplaza el hardcode "Macintosh HD" —
    consulta `diskutil info -plist /` y cachea con `functools.lru_cache`.
    """

    def test_parses_volume_name_from_diskutil_plist(self, monkeypatch):
        import plistlib
        import subprocess

        plist_bytes = plistlib.dumps({"VolumeName": "DJ Rig"})

        def fake_run(cmd, **kwargs):
            assert cmd == ["diskutil", "info", "-plist", "/"]
            return subprocess.CompletedProcess(cmd, 0, stdout=plist_bytes, stderr=b"")

        monkeypatch.setattr(traktor_db.platform, "system", lambda: "Darwin")
        monkeypatch.setattr(traktor_db.subprocess, "run", fake_run)
        assert traktor_db._boot_volume_name() == "DJ Rig"

    def test_falls_back_to_placeholder_on_subprocess_failure(self, monkeypatch):
        import subprocess

        def fake_run(cmd, **kwargs):
            raise subprocess.SubprocessError("diskutil not found")

        monkeypatch.setattr(traktor_db.platform, "system", lambda: "Darwin")
        monkeypatch.setattr(traktor_db.subprocess, "run", fake_run)
        assert traktor_db._boot_volume_name() == "Macintosh HD"

    def test_falls_back_to_placeholder_on_malformed_plist(self, monkeypatch):
        import subprocess

        def fake_run(cmd, **kwargs):
            return subprocess.CompletedProcess(cmd, 0, stdout=b"not a plist", stderr=b"")

        monkeypatch.setattr(traktor_db.platform, "system", lambda: "Darwin")
        monkeypatch.setattr(traktor_db.subprocess, "run", fake_run)
        assert traktor_db._boot_volume_name() == "Macintosh HD"

    def test_non_darwin_uses_placeholder_without_shelling_out(self, monkeypatch):
        def fake_run(cmd, **kwargs):
            raise AssertionError("no debería llamar a subprocess en plataformas no-Darwin")

        monkeypatch.setattr(traktor_db.platform, "system", lambda: "Windows")
        monkeypatch.setattr(traktor_db.subprocess, "run", fake_run)
        assert traktor_db._boot_volume_name() == "Macintosh HD"

    def test_result_is_cached_across_calls(self, monkeypatch):
        import plistlib
        import subprocess

        calls = []
        plist_bytes = plistlib.dumps({"VolumeName": "Cached HD"})

        def fake_run(cmd, **kwargs):
            calls.append(cmd)
            return subprocess.CompletedProcess(cmd, 0, stdout=plist_bytes, stderr=b"")

        monkeypatch.setattr(traktor_db.platform, "system", lambda: "Darwin")
        monkeypatch.setattr(traktor_db.subprocess, "run", fake_run)
        assert traktor_db._boot_volume_name() == "Cached HD"
        assert traktor_db._boot_volume_name() == "Cached HD"
        assert len(calls) == 1  # segunda llamada sirvió del cache, no shelleó de nuevo


class TestPathToLocationMacos:
    """
    Rama macOS del encoder — VERIFICADA contra el NML real del PO desde
    T-023/B-5 (ver docstring del módulo). `_boot_volume_name` se
    monkeypatchea acá para que estos tests sean deterministas sin importar
    el nombre real del disco de arranque de la máquina que corre pytest.
    """

    def test_external_volume_extracts_name(self):
        # PurePosixPath: en un runner Windows, Path("/Volumes/...") no sería
        # "absoluto" (falta drive) y el encoder abortaría — se fuerza semántica
        # POSIX para ejercitar la rama macOS de forma determinista.
        vol, dir_attr, file_attr = path_to_location(PurePosixPath("/Volumes/USB_DISK/Music/t.mp3"))
        assert vol == "USB_DISK"
        assert dir_attr == "/:Music/:"
        assert file_attr == "t.mp3"

    def test_external_volume_name_with_spaces(self, monkeypatch):
        # T-023 criterio 4: volumen con espacios — real en el NML del PO
        # ("NO NAME", 36 tracks, disco externo sin nombre asignado por el
        # usuario, el default que usa macOS/Windows para discos sin label).
        vol, dir_attr, file_attr = path_to_location(
            PurePosixPath("/Volumes/NO NAME/Music/Tech House/Conguero/track.mp3")
        )
        assert vol == "NO NAME"
        assert dir_attr == "/:Music/:Tech House/:Conguero/:"
        assert file_attr == "track.mp3"

    def test_boot_volume_uses_real_system_name(self, monkeypatch):
        # T-023/B-5: ya NO es un hardcode — se deriva de `_boot_volume_name()`
        # (diskutil real, mockeado acá). Antes de este fix esto devolvía
        # "Macintosh HD" SIEMPRE sin importar el disco real del usuario.
        monkeypatch.setattr(traktor_db, "_boot_volume_name", lambda: "DJ Rig")
        vol, _, _ = path_to_location(PurePosixPath("/Users/dj/Music/t.mp3"))
        assert vol == "DJ Rig"

    def test_boot_volume_default_named_disk_still_works(self, monkeypatch):
        # Caso más común: el disco de arranque conserva el nombre default
        # de Apple. Confirmado en vivo contra la Mac real del PO.
        monkeypatch.setattr(traktor_db, "_boot_volume_name", lambda: "Macintosh HD")
        vol, dir_attr, file_attr = path_to_location(PurePosixPath("/Users/dj/Music/t.mp3"))
        assert vol == "Macintosh HD"
        assert dir_attr == "/:Users/:dj/:Music/:"
        assert file_attr == "t.mp3"


class TestRoundTripMacosRealNml:
    """
    T-023 criterio 3: round-trip decode→encode contra samples REALES de los
    3 volúmenes del NML del PO (`~/Documents/Native Instruments/
    Traktor 4.4.1/collection.nml`, solo lectura — no se commitea el archivo,
    estos son los valores VOLUME/DIR/FILE literales tal como aparecen ahí).

    "decode" acá es la reconstrucción del path absoluto real en disco a
    partir de VOLUME/DIR/FILE (para "Macintosh HD" es relativo a "/", para
    un volumen externo es relativo a "/Volumes/<VOLUME>/") — la forma en
    que macOS y Traktor efectivamente resuelven esas rutas. NO se usa
    `_location_to_path()` para esta mitad: esa función es un decoder
    genérico usado también por la detección de rotos (`find_broken_entries`)
    y hoy NO antepone "/Volumes/<VOLUME>" para discos externos en macOS
    (algo fuera del alcance de T-023, que es específicamente sobre el
    ENCODER — reportado aparte como hallazgo, no corregido acá). El
    invariante que este test protege es el del encoder: `path_to_location`
    debe recuperar EXACTAMENTE el VOLUME/DIR/FILE original a partir del
    path real, sea cual sea la función que construyó ese path.
    """

    @pytest.mark.parametrize("volume,rel_from_volume_root,dir_attr,file_attr", [
        (
            "Macintosh HD",
            "Users/gabrielsk/Music/Traktor/ContentImport/Transistor Punch/01 Kick.aif",
            "/:Users/:gabrielsk/:Music/:Traktor/:ContentImport/:Transistor Punch/:",
            "01 Kick.aif",
        ),
        (
            "MUSIC",
            "rekordbox/minimalDeepWarm/7A - 130 - DJOKO - Glace Circle (Original Mi.wav",
            "/:rekordbox/:minimalDeepWarm/:",
            "7A - 130 - DJOKO - Glace Circle (Original Mi.wav",
        ),
        (
            "NO NAME",
            "Music/Tech House/Conguero/Boris Brejcha - House Music feat Arctic Lake.mp3",
            "/:Music/:Tech House/:Conguero/:",
            "Boris Brejcha - House Music feat Arctic Lake.mp3",
        ),
    ])
    def test_encode_recovers_original_location_byte_identical(
        self, monkeypatch, volume, rel_from_volume_root, dir_attr, file_attr,
    ):
        monkeypatch.setattr(traktor_db, "_boot_volume_name", lambda: "Macintosh HD")
        if volume == "Macintosh HD":
            real_path = PurePosixPath("/") / rel_from_volume_root
        else:
            real_path = PurePosixPath("/Volumes") / volume / rel_from_volume_root

        got_vol, got_dir, got_file = path_to_location(real_path)

        assert got_vol == volume
        assert got_dir == dir_attr
        assert got_file == file_attr


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
