"""T-073: relocate con alcance por playlist (motor, sin tocar nunca la librería real)."""
from __future__ import annotations

from pathlib import Path
from xml.etree import ElementTree as ET

import pytest

import relocate_core as rc
import traktor_relocate as tr
import rekordbox_relocate as rr


class TestRelocateScope:
    def test_none_scope_contains_everything(self) -> None:
        assert rc.scope_contains(None, "/any/thing.mp3") is True

    def test_scope_contains_only_its_paths(self) -> None:
        sc = rc.RelocateScope("P1", frozenset({"/a/1.mp3"}))
        assert rc.scope_contains(sc, "/a/1.mp3") is True
        assert rc.scope_contains(sc, "/a/2.mp3") is False

    def test_empty_scope_contains_nothing_it_is_not_global(self) -> None:
        sc = rc.RelocateScope("vacía", frozenset())
        assert rc.scope_contains(sc, "/a/1.mp3") is False

    def test_scope_is_immutable(self) -> None:
        sc = rc.RelocateScope("P1", frozenset({"/a/1.mp3"}))
        with pytest.raises(Exception):
            sc.name = "otra"  # type: ignore[misc]

    def test_base_worker_stores_the_scope(self, tmp_path: Path) -> None:
        sc = rc.RelocateScope("P1", frozenset({"/a/1.mp3"}))

        class W(rc.BaseRelocateWorker):
            pass

        assert W(tmp_path, scope=sc)._scope is sc
        assert W(tmp_path)._scope is None


# ───────────────────────── Traktor (NML sintético) ────────────────────────

def _nml(tmp_path: Path, names: list[str], second_playlist_with: str | None = None) -> Path:
    """NML sintético: una ENTRY rota por nombre y una playlist que las lista todas."""
    entries = "".join(
        f'<ENTRY TITLE="{n}" ARTIST="A"><LOCATION VOLUME="Z:" DIR="/:nope/:" FILE="{n}.mp3"/></ENTRY>'
        for n in names
    )
    prims = "".join(f'<ENTRY><PRIMARYKEY TYPE="TRACK" KEY="Z:/:nope/:{n}.mp3"/></ENTRY>' for n in names)
    second = ""
    if second_playlist_with:
        second = (
            '<NODE TYPE="PLAYLIST" NAME="dos"><PLAYLIST ENTRIES="1" TYPE="LIST" UUID="v">'
            f'<ENTRY><PRIMARYKEY TYPE="TRACK" KEY="Z:/:nope/:{second_playlist_with}.mp3"/></ENTRY>'
            '</PLAYLIST></NODE>'
        )
    xml = (
        '<?xml version="1.0" encoding="UTF-8"?><NML VERSION="19">'
        f'<COLLECTION ENTRIES="{len(names)}">{entries}</COLLECTION>'
        '<PLAYLISTS><NODE TYPE="FOLDER" NAME="$ROOT"><SUBNODES COUNT="2">'
        f'<NODE TYPE="PLAYLIST" NAME="all"><PLAYLIST ENTRIES="{len(names)}" TYPE="LIST" UUID="u">{prims}'
        f'</PLAYLIST></NODE>{second}</SUBNODES></NODE></PLAYLISTS></NML>'
    )
    p = tmp_path / "collection.nml"
    p.write_text(xml, encoding="utf-8")
    return p


def _raw(name: str) -> str:
    # mismo cálculo que la vista previa: str(_location_to_path(...))
    from traktor_db import _location_to_path
    return str(_location_to_path("Z:", "/:nope/:", f"{name}.mp3"))


class TestTraktorFindBrokenScoped:
    def test_only_scoped_entries_are_returned(self, tmp_path: Path) -> None:
        root = ET.parse(_nml(tmp_path, ["a", "b", "c"])).getroot()
        sc = rc.RelocateScope("P", frozenset({_raw("a"), _raw("c")}))
        broken = tr.find_broken_entries(root.find("COLLECTION"), scope=sc)
        assert sorted(b.title for _, b in broken) == ["a", "c"]

    def test_no_scope_returns_all_like_before(self, tmp_path: Path) -> None:
        root = ET.parse(_nml(tmp_path, ["a", "b", "c"])).getroot()
        assert len(tr.find_broken_entries(root.find("COLLECTION"))) == 3

    def test_empty_scope_returns_nothing(self, tmp_path: Path) -> None:
        root = ET.parse(_nml(tmp_path, ["a", "b"])).getroot()
        sc = rc.RelocateScope("vacía", frozenset())
        assert tr.find_broken_entries(root.find("COLLECTION"), scope=sc) == []

    def test_out_of_scope_entries_never_hit_the_disk(self, tmp_path: Path, monkeypatch) -> None:
        root = ET.parse(_nml(tmp_path, ["a", "b", "c"])).getroot()
        orig_exists = Path.exists
        checked: list[str] = []
        monkeypatch.setattr(Path, "exists", lambda self: (checked.append(self.name), orig_exists(self))[1])
        sc = rc.RelocateScope("P", frozenset({_raw("a")}))
        tr.find_broken_entries(root.find("COLLECTION"), scope=sc)
        assert checked == ["a.mp3"]


def _run_traktor(nml: Path, search: Path, scope, monkeypatch) -> tuple[list, list[str]]:
    monkeypatch.setattr(tr, "is_traktor_running", lambda: False)
    w = tr.RelocateWorker(nml, search, auto_resolve=True, scope=scope)
    logs: list[str] = []
    done: list[tuple] = []
    w.log.connect(logs.append)
    w.finished_ok.connect(lambda *a: done.append(a))
    w.run()
    return done, logs


def _dirs(nml: Path) -> dict[str, str]:
    coll = ET.parse(nml).getroot().find("COLLECTION")
    return {e.get("TITLE"): e.find("LOCATION").get("DIR") for e in coll}


class TestTraktorWorkerScoped:
    def test_only_the_scoped_track_is_repaired_the_other_is_untouched(self, tmp_path, monkeypatch) -> None:
        nml = _nml(tmp_path, ["a", "b"])
        disk = tmp_path / "disk"; disk.mkdir()
        (disk / "a.mp3").write_text("x"); (disk / "b.mp3").write_text("x")  # ambas tienen reemplazo
        sc = rc.RelocateScope("P", frozenset({_raw("a")}))
        done, _ = _run_traktor(nml, disk, sc, monkeypatch)
        assert done[-1] == (1, 0, 0, "ok")
        dirs = _dirs(nml)
        assert dirs["a"] != "/:nope/:"          # reparada
        assert dirs["b"] == "/:nope/:"          # intacta: fuera del alcance aunque tenía candidato

    def test_scope_with_no_matching_track_writes_nothing_and_makes_no_backup(self, tmp_path, monkeypatch) -> None:
        nml = _nml(tmp_path, ["a"])
        before = nml.read_bytes()
        disk = tmp_path / "disk"; disk.mkdir(); (disk / "a.mp3").write_text("x")
        sc = rc.RelocateScope("otra", frozenset({"/no/esta.mp3"}))
        done, _ = _run_traktor(nml, disk, sc, monkeypatch)
        assert done[-1] == (0, 0, 0, "ok")
        assert nml.read_bytes() == before
        assert not (tmp_path / "listBuddy_backups").exists()

    def test_playlists_section_follows_the_repaired_entry(self, tmp_path, monkeypatch) -> None:
        # ADR-001: el sync COLLECTION↔PLAYLISTS corre igual con alcance (sin huérfanas).
        nml = _nml(tmp_path, ["a", "b"])
        disk = tmp_path / "disk"; disk.mkdir(); (disk / "a.mp3").write_text("x")
        _run_traktor(nml, disk, rc.RelocateScope("P", frozenset({_raw("a")})), monkeypatch)
        keys = [k.get("KEY") for k in ET.parse(nml).getroot().iter("PRIMARYKEY")]
        assert "Z:/:nope/:a.mp3" not in keys     # la repetida vieja ya no está
        assert "Z:/:nope/:b.mp3" in keys         # la no reparada conserva su clave
        coll = ET.parse(nml).getroot().find("COLLECTION")
        coll_keys = {
            tr._location_to_key(l.get("VOLUME"), l.get("DIR"), l.get("FILE"))
            for l in (e.find("LOCATION") for e in coll)
        }
        assert set(keys) <= coll_keys            # ninguna PRIMARYKEY huérfana

    def test_track_in_two_playlists_is_repaired_for_both(self, tmp_path, monkeypatch) -> None:
        nml = _nml(tmp_path, ["a"], second_playlist_with="a")
        disk = tmp_path / "disk"; disk.mkdir(); (disk / "a.mp3").write_text("x")
        _run_traktor(nml, disk, rc.RelocateScope("uno", frozenset({_raw("a")})), monkeypatch)
        keys = [k.get("KEY") for k in ET.parse(nml).getroot().iter("PRIMARYKEY")]
        assert len(keys) == 2 and "Z:/:nope/:a.mp3" not in keys
        assert keys[0] == keys[1]                # las dos playlists apuntan a la entrada nueva
