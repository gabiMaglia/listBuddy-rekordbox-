"""
test_relocate_core.py
----------------------
Tests de las piezas puras compartidas de relocate_core.py (T-017/T-018).

Foco de este archivo: `check_disk_space_for_backup` (B-3, T-018) — el
chequeo de espacio libre ANTES de intentar el backup, mismo patrón que
worker.py ya usa para el export y que el write path sobre la librería del
usuario no tenía hasta este ticket. La otra mitad de B-3 (que un backup
interrumpido a mitad no deje un archivo parcial) se testea en
test_traktor_relocate.py / test_rekordbox_relocate.py, donde viven
backup_collection/backup_master_db.

T-028 agrega acá el matching tolerante a prefijo numérico (`NN - `) y a
extensión (`_normalize_key`/`build_normalized_index`/fallback en
`find_candidates`), y el loop de resolución (`_run_resolution`) que
garantiza que un match normalizado nunca auto-resuelve (ADR-001 p.3
ampliado). Vive acá y no en test_traktor_relocate.py/
test_rekordbox_relocate.py porque el matching y el loop son compartidos
por los dos motores (criterio 6 del ticket): un test acá cubre ambos sin
duplicar.

Se evita instanciar BaseRelocateWorker (QThread) para los tests de
matching puro. Para `_run_resolution` (criterio 4, ver
TestRunResolutionNormalizedNeverAutoResolves) sí hace falta una subclase
concreta mínima, pero se llama al método directamente (nunca `.start()`):
sin `.start()` no hay hilo real ni event loop Qt de por medio, las
conexiones de señal↔slot son directas (mismo hilo) y se resuelven
sincrónicamente dentro de `emit()` — no hay riesgo de deadlock ni de
requerir `QApplication`.
"""
from __future__ import annotations

import shutil
from dataclasses import dataclass
from pathlib import Path

import pytest

import relocate_core as rc


class TestCheckDiskSpaceForBackup:
    def test_raises_when_insufficient_free_space(self, tmp_path, monkeypatch):
        src = tmp_path / "collection.nml"
        src.write_bytes(b"x" * 1000)  # tamaño irrelevante, se mockea disk_usage

        class _Usage:
            free = 500  # menos que el tamaño del archivo → insuficiente

        monkeypatch.setattr(shutil, "disk_usage", lambda _path: _Usage())

        with pytest.raises(OSError) as exc_info:
            rc.check_disk_space_for_backup(src)
        # El mensaje debe ser legible y en GB, no un traceback crudo.
        assert "GB" in str(exc_info.value)

    def test_passes_when_enough_free_space(self, tmp_path):
        src = tmp_path / "collection.nml"
        src.write_bytes(b"x" * 10)
        # tmp_path real del runner: de sobra para 10 bytes. No debe lanzar.
        rc.check_disk_space_for_backup(src)

    def test_missing_source_does_not_raise_here(self, tmp_path):
        # Si el origen ni siquiera existe, este chequeo no es quien debe
        # fallar — se difiere al intento real de copia, que dará un error
        # más específico (archivo no encontrado, no "sin espacio").
        missing = tmp_path / "no_existe.nml"
        rc.check_disk_space_for_backup(missing)  # no debe lanzar


# ─────────────────────── T-028: matching tolerante ────────────────────────

def _broken(name: str, title: str = "", artist: str = "") -> "_BrokenTrack":
    """Duck-type mínimo de BrokenTrack (Traktor/Rekordbox comparten forma:
    `original_path`/`title`/`artist`), sin importar traktor_relocate.py acá
    — este archivo testea relocate_core.py de forma neutral a los motores
    (ver docstring del módulo)."""
    return _BrokenTrack(title=title, artist=artist, original_path=Path(f"/old/{name}"))


@dataclass
class _BrokenTrack:
    title: str
    artist: str
    original_path: Path


class TestNormalizeKey:
    def test_strips_numeric_prefix(self):
        assert rc._normalize_key("001 - Artist - Title.mp3") == "artist - title"

    def test_strips_extension(self):
        assert rc._normalize_key("Artist - Title.aiff") == "artist - title"

    def test_strips_prefix_and_extension_together(self):
        assert rc._normalize_key("014 - Artist - Title.aif") == "artist - title"

    def test_lowercases(self):
        assert rc._normalize_key("ARTIST - TITLE.MP3") == "artist - title"

    def test_no_prefix_present_unchanged_besides_extension(self):
        # Sin "NN - " al inicio, no hay nada que recortar salvo la extensión.
        assert rc._normalize_key("Artist - Title.mp3") == "artist - title"

    def test_digits_without_trailing_dash_are_not_stripped(self):
        # "2 Unlimited" no es un prefijo de orden (no hay "-" pegado a los
        # dígitos) — no debe recortarse, sería un falso positivo de artista.
        assert rc._normalize_key("2 Unlimited - No Limit.mp3") == "2 unlimited - no limit"


class TestBuildNormalizedIndex:
    def test_derives_from_existing_index_without_rescanning_disk(self, tmp_path):
        (tmp_path / "001 - Artist - Title.wav").write_text("x")
        index = rc.build_basename_index(tmp_path)
        normalized = rc.build_normalized_index(index)
        assert "artist - title" in normalized
        assert normalized["artist - title"][0].name == "001 - Artist - Title.wav"

    def test_collision_n_to_1_same_track_multiple_playlists(self, tmp_path):
        # Escenario real medido por el Orquestador: el mismo track
        # exportado a varias playlists produce "001 - X.wav", "014 - X.wav"
        # — ambos deben colisionar bajo la misma clave normalizada.
        (tmp_path / "001 - Artist - Title.wav").write_text("x")
        (tmp_path / "014 - Artist - Title.wav").write_text("y")
        index = rc.build_basename_index(tmp_path)
        normalized = rc.build_normalized_index(index)
        assert len(normalized["artist - title"]) == 2


class TestFindCandidatesNormalizedFallback:
    def test_prefix_tolerance(self, tmp_path):
        (tmp_path / "003 - Artist - Title.mp3").write_text("x")
        index = rc.build_basename_index(tmp_path)
        normalized_index = rc.build_normalized_index(index)
        track = _broken("Artist - Title.mp3")

        # Sin normalized_index: comportamiento exacto de siempre, 0 matches.
        assert rc.find_candidates(track, index) == []

        cands = rc.find_candidates(track, index, normalized_index)
        assert len(cands) == 1
        assert cands[0].path.name == "003 - Artist - Title.mp3"
        assert cands[0].match_type == "normalized"

    def test_extension_tolerance(self, tmp_path):
        # Caso real medido: .aiff en la DB vs .aif truncado en disco
        # (exFAT/Windows).
        (tmp_path / "Artist - Title.aif").write_text("x")
        index = rc.build_basename_index(tmp_path)
        normalized_index = rc.build_normalized_index(index)
        track = _broken("Artist - Title.aiff")

        cands = rc.find_candidates(track, index, normalized_index)
        assert len(cands) == 1
        assert cands[0].path.name == "Artist - Title.aif"
        assert cands[0].match_type == "normalized"

    def test_prefix_and_extension_together(self, tmp_path):
        (tmp_path / "007 - Artist - Title.aif").write_text("x")
        index = rc.build_basename_index(tmp_path)
        normalized_index = rc.build_normalized_index(index)
        track = _broken("Artist - Title.aiff")

        cands = rc.find_candidates(track, index, normalized_index)
        assert len(cands) == 1
        assert cands[0].path.name == "007 - Artist - Title.aif"
        assert cands[0].match_type == "normalized"

    def test_collision_n_to_1_returns_multiple_normalized_candidates(self, tmp_path):
        (tmp_path / "001 - Artist - Title.wav").write_text("x")
        (tmp_path / "014 - Artist - Title.wav").write_text("y")
        index = rc.build_basename_index(tmp_path)
        normalized_index = rc.build_normalized_index(index)
        track = _broken("Artist - Title.wav")

        cands = rc.find_candidates(track, index, normalized_index)
        assert len(cands) == 2
        assert all(c.match_type == "normalized" for c in cands)

    def test_exact_match_takes_priority_over_normalized(self, tmp_path):
        # Criterio 5 (no-regresión): si existe el nombre EXACTO, el
        # fallback normalizado ni se intenta — nunca se mezclan candidatos
        # exactos con normalizados para el mismo track.
        (tmp_path / "Artist - Title.mp3").write_text("exact")
        (tmp_path / "003 - Artist - Title.mp3").write_text("prefixed")
        index = rc.build_basename_index(tmp_path)
        normalized_index = rc.build_normalized_index(index)
        track = _broken("Artist - Title.mp3")

        cands = rc.find_candidates(track, index, normalized_index)
        assert len(cands) == 1
        assert cands[0].path.name == "Artist - Title.mp3"
        assert cands[0].match_type == "exact"

    def test_no_normalized_index_preserves_old_exact_only_behavior(self, tmp_path):
        # Regression explícita: llamar find_candidates sin el 3er argumento
        # (como hacía todo el código antes de T-028) da exactamente el
        # mismo resultado que antes — 0 matches si no hay nombre exacto,
        # sin fallback implícito.
        (tmp_path / "003 - Artist - Title.mp3").write_text("x")
        index = rc.build_basename_index(tmp_path)
        assert rc.find_candidates(_broken("Artist - Title.mp3"), index) == []

    def test_exact_single_match_unaffected_by_t028(self, tmp_path):
        # Regression: un match exacto simple sigue igual (score, path,
        # match_type "exact") pasando o no el normalized_index.
        (tmp_path / "Artist - Title.mp3").write_text("x")
        index = rc.build_basename_index(tmp_path)
        normalized_index = rc.build_normalized_index(index)
        track = _broken("Artist - Title.mp3", title="Title", artist="Artist")

        without = rc.find_candidates(track, index)
        with_norm = rc.find_candidates(track, index, normalized_index)
        assert len(without) == len(with_norm) == 1
        assert without[0].path == with_norm[0].path
        assert without[0].match_type == with_norm[0].match_type == "exact"


# ───────────── T-028 criterio 4: normalizado nunca auto-resuelve ──────────

class _StubWorker(rc.BaseRelocateWorker):
    """Subclase concreta mínima de BaseRelocateWorker para ejercitar
    `_run_resolution` sin QThread real (nunca se llama `.start()`, ver
    docstring del módulo)."""

    def __init__(self, search_root: Path, auto_resolve: bool = False, apply_result: bool = True) -> None:
        super().__init__(search_root, auto_resolve=auto_resolve)
        self._apply_result = apply_result
        self.applied: list[tuple] = []

    def _broken_scope_noun(self) -> str:
        return "colección"

    def _write_target_name(self) -> str:
        return "NML"

    def _engine_name(self) -> str:
        return "Test"

    def _label_for(self, broken_track) -> str:
        return broken_track.original_path.name

    def _apply_one(self, raw_entry, broken_track, chosen) -> bool:
        self.applied.append((broken_track, chosen))
        return self._apply_result


class TestRunResolutionNormalizedNeverAutoResolves:
    def test_auto_resolve_on_single_normalized_candidate_stays_unresolved(self, tmp_path):
        # Criterio 4: con el checkbox de auto-resolución (T-003) activo, un
        # match que SOLO existe por clave normalizada nunca se aplica solo
        # — ni siendo el único candidato. Se loguea como no resuelto.
        (tmp_path / "003 - Artist - Title.mp3").write_text("x")
        worker = _StubWorker(tmp_path, auto_resolve=True)
        logs: list[str] = []
        asked: list[object] = []
        worker.log.connect(logs.append)
        worker.ask_user.connect(asked.append)

        broken = [(None, _broken("Artist - Title.mp3"))]
        result = worker._run_resolution(broken)

        assert result is not None
        assert result.repaired == 0
        assert result.unresolved == 1
        assert worker.applied == []  # nunca se llamó _apply_one
        assert not asked  # auto_resolve nunca muestra modal
        assert any("confirmación manual" in line for line in logs)

    def test_auto_resolve_off_single_normalized_candidate_goes_to_modal(self, tmp_path):
        # Con el checkbox OFF (default), el mismo caso SÍ debe pasar por el
        # modal (decisión humana) — nunca auto-aplicarse por ser el único
        # candidato, a diferencia del caso exacto.
        (tmp_path / "003 - Artist - Title.mp3").write_text("x")
        worker = _StubWorker(tmp_path, auto_resolve=False)
        asked: list[object] = []

        def _answer_yes(request):
            asked.append(request)
            worker.provide_answer(request.candidates[0].path)

        worker.ask_user.connect(_answer_yes)

        broken = [(None, _broken("Artist - Title.mp3"))]
        result = worker._run_resolution(broken)

        assert result is not None
        assert len(asked) == 1  # el modal SÍ se mostró
        assert asked[0].candidates[0].match_type == "normalized"
        assert result.repaired == 1  # el usuario eligió aplicar
        assert worker.applied  # _apply_one se llamó con la elección humana

    def test_exact_single_candidate_still_auto_applies_no_regression(self, tmp_path):
        # Criterio 5 (no-regresión) a nivel del loop, no solo de
        # find_candidates: un match EXACTO simple sigue aplicándose sin
        # modal, con o sin auto_resolve — comportamiento intacto.
        (tmp_path / "Artist - Title.mp3").write_text("x")
        worker = _StubWorker(tmp_path, auto_resolve=False)
        asked: list[object] = []
        worker.ask_user.connect(asked.append)

        broken = [(None, _broken("Artist - Title.mp3"))]
        result = worker._run_resolution(broken)

        assert result is not None
        assert result.repaired == 1
        assert result.unresolved == 0
        assert not asked  # nunca pidió confirmación — 1 match exacto se aplica solo
        assert worker.applied
