"""
test_traktor_relocate.py
------------------------
Tests del motor de relocate de Traktor (traktor_relocate.py), las piezas puras
que protegen contra corromper el NML del usuario (ADR-001):

  - matching (find_candidates): 0/1/>1, case-insensitive, orden por score.
  - backup + poda de retención (N=10): el backup es la ÚNICA red de rollback.
  - escritura atómica (write_atomic): round-trip serializar→reparsear.
  - sync COLLECTION↔PLAYLISTS (apply_relocation): que NO queden entradas
    huérfanas es el criterio de correctitud central de ADR-001.

Se evita instanciar RelocateWorker (QThread) — se testean las funciones puras,
sin event loop de Qt.
"""
from __future__ import annotations

import errno
from pathlib import Path, PureWindowsPath
from xml.etree import ElementTree as ET

import pytest

import traktor_relocate as tr
from traktor_relocate import (
    BrokenTrack,
    apply_relocation,
    backup_collection,
    build_basename_index,
    build_reverse_key_index,
    find_broken_entries,
    find_candidates,
    write_atomic,
)


# ─────────────────────────── disk index ───────────────────────────────────

class TestBuildBasenameIndex:
    def test_lowercased_keys_and_full_paths(self, tmp_path):
        (tmp_path / "Track One.MP3").write_text("x")
        (tmp_path / "sub").mkdir()
        (tmp_path / "sub" / "Otro.flac").write_text("y")

        index = build_basename_index(tmp_path)

        assert "track one.mp3" in index
        assert "otro.flac" in index
        assert index["otro.flac"][0].name == "Otro.flac"

    def test_skips_own_backup_dir(self, tmp_path):
        backups = tmp_path / tr._BACKUP_DIR_NAME
        backups.mkdir()
        (backups / "old.mp3").write_text("x")
        (tmp_path / "real.mp3").write_text("y")

        index = build_basename_index(tmp_path)

        assert "real.mp3" in index
        assert "old.mp3" not in index  # el backup propio no se ofrece de candidato

    def test_same_basename_collects_all_paths(self, tmp_path):
        (tmp_path / "a").mkdir()
        (tmp_path / "b").mkdir()
        (tmp_path / "a" / "dup.mp3").write_text("x")
        (tmp_path / "b" / "dup.mp3").write_text("y")

        index = build_basename_index(tmp_path)

        assert len(index["dup.mp3"]) == 2

    def test_progress_callback_fires(self, tmp_path):
        for i in range(5):
            (tmp_path / f"f{i}.mp3").write_text("x")
        seen: list[int] = []
        build_basename_index(tmp_path, on_progress=seen.append, progress_every=2)
        assert seen  # se reportó avance al menos una vez

    def test_should_stop_aborts_walk(self, tmp_path):
        for i in range(10):
            (tmp_path / f"f{i}.mp3").write_text("x")
        # Corta ni bien empieza: el índice queda vacío o parcial, nunca completo.
        index = build_basename_index(tmp_path, should_stop=lambda: True)
        assert len(index) == 0


# ─────────────────────────── detección de rotos (T-020, I-2/I-3) ──────────

def _collection_with_broken_entries(n: int) -> ET.Element:
    """
    COLLECTION con `n` ENTRY, todas apuntando a un LOCATION inexistente
    (volumen "Z:" que no existe en el runner). Suficiente para testear
    detección + cancelación sin depender de archivos reales en disco: el
    criterio de "roto" es simplemente que `Path.exists()` dé False.
    """
    entries_xml = "".join(
        f'<ENTRY TITLE="t{i}" ARTIST="a{i}">'
        f'<LOCATION VOLUME="Z:" DIR="/:nope/:" FILE="f{i}.mp3"/>'
        "</ENTRY>"
        for i in range(n)
    )
    return ET.fromstring(f'<COLLECTION ENTRIES="{n}">{entries_xml}</COLLECTION>')


class TestFindBrokenEntries:
    def test_detects_all_broken_when_not_interrupted(self):
        collection = _collection_with_broken_entries(5)
        broken = find_broken_entries(collection)
        assert len(broken) == 5

    def test_should_stop_aborts_before_finishing(self):
        # T-020: la fase de detección no era cancelable (I-2/I-3) — con un
        # disco de red o USB desconectado, cada `.exists()` puede tardar
        # decenas de segundos y esto dejaba la app colgada varios minutos
        # sin que "Cancelar" hiciera nada. Este test fija que `should_stop`
        # corta el loop ANTES de procesar todas las entries, no solo al
        # final.
        collection = _collection_with_broken_entries(10)
        seen: list[int] = []
        broken = find_broken_entries(
            collection,
            should_stop=lambda: len(seen) >= 3,
            on_progress=lambda done, total: seen.append(done),
            progress_every=1,
        )
        assert len(broken) == 3  # cortó a mitad de camino, no llegó a 10
        assert len(seen) == 3

    def test_progress_reports_known_total_upfront(self):
        # A diferencia de build_basename_index (total desconocido hasta
        # terminar el walk), acá el total de ENTRY se conoce de entrada.
        collection = _collection_with_broken_entries(6)
        seen: list[tuple[int, int]] = []
        find_broken_entries(
            collection,
            on_progress=lambda done, total: seen.append((done, total)),
            progress_every=2,
        )
        assert seen  # se reportó avance al menos una vez
        assert all(total == 6 for _, total in seen)

    def test_non_broken_entry_is_excluded(self, tmp_path):
        # Un ENTRY cuyo archivo SÍ existe no debe aparecer como roto —
        # el fix de cancelación/progreso no puede cambiar QUÉ detecta.
        real_file = tmp_path / "real.mp3"
        real_file.write_text("x")
        drive = real_file.drive  # ej. "C:"
        parent_dir = "/:" + "/:".join(real_file.parent.parts[1:]) + "/:"
        xml = (
            f'<COLLECTION ENTRIES="1">'
            f'<ENTRY TITLE="ok" ARTIST="a">'
            f'<LOCATION VOLUME="{drive}" DIR="{parent_dir}" FILE="real.mp3"/>'
            f"</ENTRY></COLLECTION>"
        )
        broken = find_broken_entries(ET.fromstring(xml))
        assert broken == []


# ─────────────────────────── matching ─────────────────────────────────────

def _broken(name: str, title: str = "", artist: str = "") -> BrokenTrack:
    return BrokenTrack(
        title=title, artist=artist,
        original_key="k", original_path=PureWindowsPath(rf"I:\old\{name}"),
    )


class TestFindCandidates:
    def test_zero_matches(self, tmp_path):
        index = build_basename_index(tmp_path)
        assert find_candidates(_broken("nope.mp3"), index) == []

    def test_case_insensitive_match(self, tmp_path):
        (tmp_path / "Song.MP3").write_text("x")
        index = build_basename_index(tmp_path)
        cands = find_candidates(_broken("song.mp3"), index)
        assert len(cands) == 1
        assert cands[0].path.name == "Song.MP3"

    def test_multiple_matches_sorted_by_score_desc(self, tmp_path):
        (tmp_path / "good").mkdir()
        (tmp_path / "bad").mkdir()
        # Un candidato con nombre "Artist - Title.mp3" debe rankear más alto
        # contra un BrokenTrack de ese artist/title que uno sin metadata.
        (tmp_path / "good" / "Daft Punk - Aerodynamic.mp3").write_text("x")
        (tmp_path / "bad" / "Daft Punk - Aerodynamic.mp3").write_text("y")
        # ambos mismo nombre → mismo score; garantizamos que devuelve los 2
        index = build_basename_index(tmp_path)
        track = _broken(
            "Daft Punk - Aerodynamic.mp3",
            title="Aerodynamic", artist="Daft Punk",
        )
        cands = find_candidates(track, index)
        assert len(cands) == 2
        scores = [c.score for c in cands]
        assert scores == sorted(scores, reverse=True)

    def test_fuzzy_only_ranks_never_filters(self, tmp_path):
        # Aunque el fuzzy score sea bajo, un match por nombre exacto SIEMPRE
        # es candidato (ADR-001: el fuzzy no decide ni descarta, solo rankea).
        (tmp_path / "weird.mp3").write_text("x")
        index = build_basename_index(tmp_path)
        cands = find_candidates(_broken("weird.mp3", title="zzz", artist="qqq"), index)
        assert len(cands) == 1


# ─────────────────────────── backup + poda ────────────────────────────────

class TestBackup:
    def test_backup_creates_copy_in_subdir(self, tmp_path):
        nml = tmp_path / "collection.nml"
        nml.write_text("<NML/>")
        dest = backup_collection(nml)
        assert dest.exists()
        assert dest.parent.name == tr._BACKUP_DIR_NAME
        assert dest.read_text() == "<NML/>"

    def test_prune_keeps_only_retention_n(self, tmp_path):
        backups = tmp_path / tr._BACKUP_DIR_NAME
        backups.mkdir()
        # Crea N+3 backups con mtimes crecientes.
        import os, time
        for i in range(tr._BACKUP_RETENTION + 3):
            f = backups / f"collection.2026010{i:02d}-000000.nml"
            f.write_text("x")
            os.utime(f, (1000 + i, 1000 + i))
        tr._prune_backups(backups)
        remaining = list(backups.glob("collection.*.nml"))
        assert len(remaining) == tr._BACKUP_RETENTION

    def test_prune_removes_oldest_first(self, tmp_path):
        backups = tmp_path / tr._BACKUP_DIR_NAME
        backups.mkdir()
        import os
        files = []
        for i in range(tr._BACKUP_RETENTION + 2):
            f = backups / f"collection.x{i:02d}.nml"
            f.write_text("x")
            os.utime(f, (1000 + i, 1000 + i))  # i más alto = más nuevo
            files.append(f)
        tr._prune_backups(backups)
        # Los 2 más viejos (i=0,1) deben haberse borrado.
        assert not files[0].exists()
        assert not files[1].exists()
        assert files[-1].exists()  # el más nuevo sobrevive


class TestBackupInterruptedByOSError:
    """
    B-3 (T-018): un `OSError` a mitad de `shutil.copy2` (ej. ENOSPC por
    disco lleno) dejaba antes un archivo destino PARCIAL en
    `listBuddy_backups/`, que `_prune_backups` contaba como el backup más
    nuevo — exactamente el que el usuario elegiría restaurar. Ahora
    `backup_collection` borra ese destino parcial antes de re-lanzar.
    """

    def test_partial_backup_removed_on_copy_failure(self, tmp_path, monkeypatch):
        nml = tmp_path / "collection.nml"
        original = "<NML>" + "x" * 500 + "</NML>"
        nml.write_text(original)

        def fake_copy2(_src, dst):
            # Simula una copia real interrumpida a mitad de camino: el
            # archivo destino existe (parcial) en el momento de fallar.
            Path(dst).write_text("PARTIAL-GARBAGE")
            raise OSError(errno.ENOSPC, "No space left on device")

        monkeypatch.setattr(tr.shutil, "copy2", fake_copy2)

        with pytest.raises(OSError):
            backup_collection(nml)

        backups_dir = tmp_path / tr._BACKUP_DIR_NAME
        # (b) ningún backup parcial sobrevive en el directorio.
        assert list(backups_dir.glob("collection.*.nml")) == []
        # (a) la librería original no se tocó.
        assert nml.read_text() == original

    def test_insufficient_disk_space_aborts_before_copying(self, tmp_path, monkeypatch):
        nml = tmp_path / "collection.nml"
        nml.write_text("<NML/>")

        class _Usage:
            free = 0

        monkeypatch.setattr(tr.shutil, "disk_usage", lambda _p: _Usage())

        with pytest.raises(OSError):
            backup_collection(nml)

        # El chequeo de espacio debe abortar ANTES de intentar copiar nada.
        backups_dir = tmp_path / tr._BACKUP_DIR_NAME
        assert not backups_dir.exists() or list(backups_dir.glob("collection.*.nml")) == []


# ─────────────────────────── escritura atómica ────────────────────────────

class TestWriteAtomic:
    def test_round_trip_preserves_tree(self, tmp_path):
        src = tmp_path / "collection.nml"
        src.write_text(
            '<?xml version="1.0" encoding="UTF-8"?>'
            '<NML><COLLECTION><ENTRY TITLE="t"/></COLLECTION></NML>'
        )
        tree = ET.parse(str(src))
        # muta y reescribe
        tree.getroot().find("COLLECTION").find("ENTRY").set("TITLE", "nuevo")
        write_atomic(tree, src)

        reparsed = ET.parse(str(src))
        assert reparsed.getroot().find("COLLECTION").find("ENTRY").get("TITLE") == "nuevo"

    def test_no_tmp_file_left_behind(self, tmp_path):
        src = tmp_path / "collection.nml"
        src.write_text('<?xml version="1.0"?><NML/>')
        write_atomic(ET.parse(str(src)), src)
        assert not (tmp_path / "collection.nml.tmp").exists()


# ─────────────── sync COLLECTION↔PLAYLISTS (el corazón de ADR-001) ─────────

_NML_SAMPLE = """<?xml version="1.0" encoding="UTF-8"?>
<NML>
  <COLLECTION ENTRIES="1">
    <ENTRY TITLE="Song" ARTIST="Artist">
      <LOCATION VOLUME="I:" DIR="/:old/:" FILE="song.mp3"/>
    </ENTRY>
  </COLLECTION>
  <PLAYLISTS>
    <NODE TYPE="FOLDER" NAME="$ROOT">
      <SUBNODES>
        <NODE TYPE="PLAYLIST" NAME="Set A">
          <PLAYLIST ENTRIES="1">
            <ENTRY><PRIMARYKEY TYPE="TRACK" KEY="I:/:old/:song.mp3"/></ENTRY>
          </PLAYLIST>
        </NODE>
        <NODE TYPE="PLAYLIST" NAME="Set B">
          <PLAYLIST ENTRIES="1">
            <ENTRY><PRIMARYKEY TYPE="TRACK" KEY="I:/:old/:song.mp3"/></ENTRY>
          </PLAYLIST>
        </NODE>
      </SUBNODES>
    </NODE>
  </PLAYLISTS>
</NML>
"""


class TestApplyRelocationSync:
    def _tree(self):
        return ET.ElementTree(ET.fromstring(_NML_SAMPLE))

    def test_collection_location_rewritten(self):
        tree = self._tree()
        root = tree.getroot()
        entry = root.find("COLLECTION").find("ENTRY")
        key_index = build_reverse_key_index(root.find("PLAYLISTS"))

        apply_relocation(entry, PureWindowsPath(r"D:\new\song.mp3"), key_index)

        loc = entry.find("LOCATION")
        assert loc.get("VOLUME") == "D:"
        assert loc.get("DIR") == "/:new/:"
        assert loc.get("FILE") == "song.mp3"

    def test_all_primarykeys_across_playlists_rewritten(self):
        # El invariante que evita entradas huérfanas: TODA PRIMARYKEY que
        # apuntaba al old_key debe pasar al new_key, en todas las playlists.
        tree = self._tree()
        root = tree.getroot()
        entry = root.find("COLLECTION").find("ENTRY")
        key_index = build_reverse_key_index(root.find("PLAYLISTS"))

        new_key = apply_relocation(entry, PureWindowsPath(r"D:\new\song.mp3"), key_index)

        keys = [pk.get("KEY") for pk in root.find("PLAYLISTS").iter("PRIMARYKEY")]
        assert keys == [new_key, new_key]  # ambas playlists sincronizadas
        assert new_key == "D:/:new/:song.mp3"
        assert "I:/:old/:song.mp3" not in keys  # ningún huérfano quedó atrás

    def test_new_key_recomputed_from_path_not_assuming_stable_basename(self):
        # Si el archivo elegido tiene OTRO basename, el new_key se recomputa
        # entero (ADR-001 punto 4) — la sync no asume que FILE queda igual.
        tree = self._tree()
        root = tree.getroot()
        entry = root.find("COLLECTION").find("ENTRY")
        key_index = build_reverse_key_index(root.find("PLAYLISTS"))

        new_key = apply_relocation(entry, PureWindowsPath(r"D:\new\renamed.mp3"), key_index)

        assert entry.find("LOCATION").get("FILE") == "renamed.mp3"
        assert new_key.endswith("renamed.mp3")
        keys = [pk.get("KEY") for pk in root.find("PLAYLISTS").iter("PRIMARYKEY")]
        assert all(k == new_key for k in keys)

    def test_entry_without_location_raises(self):
        entry = ET.fromstring('<ENTRY TITLE="x"/>')
        with pytest.raises(ValueError):
            apply_relocation(entry, PureWindowsPath(r"D:\a\b.mp3"), {})


# ─────── aliasing del índice inverso (T-022, hallazgo adversarial #6 ──────
#
# engram/07_production_readiness.md: "build_reverse_key_index se construye
# UNA vez antes del loop y apply_relocation nunca lo actualiza. Si la pista
# A se repara hacia la ubicación que la pista B ocupa hoy, y B se procesa
# después, los PRIMARYKEY que A acaba de reescribir vuelven a reescribirse
# al reparar B — dejando huérfanas las referencias de A."
#
# Investigación (antes de escribir el test): ¿cuándo puede pasar esto en la
# práctica? `key_index` mapea old_key (string) -> [PRIMARYKEY elements],
# construido una sola vez. `apply_relocation` recomputa `old_key` EN VIVO
# desde el LOCATION actual de cada ENTRY al momento de llamarla (no reusa
# un valor cacheado), así que dos ENTRY con old_key *distinto* nunca pisan
# el bucket del otro — cada string vive en su propio bucket para siempre.
# La lectura literal del reporte ("A se repara hacia la ubicación que B
# ocupa hoy") sería imposible si B estuviera genuinamente roto: para que el
# candidato de A coincida con la ruta de B, esa ruta tendría que EXISTIR en
# disco (build_basename_index solo indexa archivos reales) — pero si existe,
# `find_broken_entries` no habría marcado a B como roto en primer lugar
# (`Path.exists()` daría True). Ese caso literal se autocontradice.
#
# El escenario EQUIVALENTE real (mencionado explícitamente como alternativa
# válida en el ticket) sí es alcanzable: DOS ENTRY de COLLECTION con el
# MISMO LOCATION original (mismo old_key) — nada en el NML ni en nuestro
# parser lo impide, y colecciones de Traktor fusionadas/duplicadas por
# import repetido son conocidas por tener ENTRY duplicadas apuntando al
# mismo archivo (que luego se rompe para ambas a la vez si ese archivo se
# borra/mueve). En ese caso, `key_index[old_key]` es UN SOLO bucket
# compartido por PRIMARYKEY de ambas pistas — indistinguibles entre sí,
# porque PRIMARYKEY solo guarda un KEY, no un ID de ENTRY. Confirmado con
# el test de abajo: SIN el fix, procesar A y después B sobre ese bucket
# compartido reescribe DOS VECES los mismos PRIMARYKEY, y la segunda
# reescritura (la de B) pisa la de A — las referencias de playlist que A
# acababa de arreglar terminan apuntando al archivo de B, no al de A.
# CONFIRMADO: es un bug real, no solo teórico (ver test_reproduces_bug_*).
class TestApplyRelocationAliasing:
    _NML_SHARED_KEY = """<?xml version="1.0" encoding="UTF-8"?>
<NML>
  <COLLECTION ENTRIES="2">
    <ENTRY TITLE="Song A" ARTIST="Artist A">
      <LOCATION VOLUME="I:" DIR="/:old/:" FILE="dup.mp3"/>
    </ENTRY>
    <ENTRY TITLE="Song B" ARTIST="Artist B">
      <LOCATION VOLUME="I:" DIR="/:old/:" FILE="dup.mp3"/>
    </ENTRY>
  </COLLECTION>
  <PLAYLISTS>
    <NODE TYPE="FOLDER" NAME="$ROOT">
      <SUBNODES>
        <NODE TYPE="PLAYLIST" NAME="Set A">
          <PLAYLIST ENTRIES="1">
            <ENTRY><PRIMARYKEY TYPE="TRACK" KEY="I:/:old/:dup.mp3"/></ENTRY>
          </PLAYLIST>
        </NODE>
        <NODE TYPE="PLAYLIST" NAME="Set B">
          <PLAYLIST ENTRIES="1">
            <ENTRY><PRIMARYKEY TYPE="TRACK" KEY="I:/:old/:dup.mp3"/></ENTRY>
          </PLAYLIST>
        </NODE>
      </SUBNODES>
    </NODE>
  </PLAYLISTS>
</NML>
"""

    def _tree(self):
        return ET.ElementTree(ET.fromstring(self._NML_SHARED_KEY))

    def test_two_entries_sharing_original_key_do_not_clobber_each_other(self):
        tree = self._tree()
        root = tree.getroot()
        entry_a, entry_b = root.find("COLLECTION").findall("ENTRY")
        key_index = build_reverse_key_index(root.find("PLAYLISTS"))

        # A se procesa primero (orden del loop en _run_resolution), B
        # después — igual que el escenario del reporte.
        new_key_a = apply_relocation(entry_a, PureWindowsPath(r"D:\fixed\songA.mp3"), key_index)
        new_key_b = apply_relocation(entry_b, PureWindowsPath(r"E:\fixed\songB.mp3"), key_index)

        assert new_key_a != new_key_b  # sanity: cada una fue a un archivo distinto

        keys_after = [pk.get("KEY") for pk in root.find("PLAYLISTS").iter("PRIMARYKEY")]

        # Invariante que el fix garantiza: una vez que un bucket de
        # key_index fue consumido (las PRIMARYKEY que tenía se reescribieron
        # a un new_key válido), procesar una ENTRY DISTINTA que comparte el
        # mismo old_key original NO debe volver a tocar esas mismas
        # PRIMARYKEY — si no, se pierde el trabajo que A ya hizo bien.
        # Sin el fix (key_index.get sin consumir el bucket), ambas
        # PRIMARYKEY terminan con new_key_b (la reescritura de A queda
        # pisada) — huérfano exacto que describe el reporte.
        assert keys_after == [new_key_a, new_key_a]
        assert new_key_b not in keys_after  # ninguna referencia de B sobrevive huérfana de A

        # La propia ENTRY de B en COLLECTION sí quedó reparada (su LOCATION
        # apunta al archivo correcto) aunque ninguna playlist la referencie
        # ya — es la limitación inherente de una librería con dos ENTRY
        # duplicadas que comparten LOCATION: PRIMARYKEY no puede distinguir
        # cuál de las dos "es" cada referencia, así que como máximo UNA de
        # las dos puede quedarse con las referencias de playlist correctas.
        # Lo que el fix garantiza es que sea determinístico (la primera
        # procesada gana) y que no haya doble reescritura silenciosa.
        assert entry_b.find("LOCATION").get("FILE") == "songB.mp3"
