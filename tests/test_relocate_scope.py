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


# ───────────────────── Rekordbox (DB de prueba en memoria) ────────────────

from dataclasses import dataclass


@dataclass
class _C:
    FolderPath: str
    Title: str = ""
    ArtistName: str = ""
    ID: str = "1"


class _FakeRbDb:
    """Duck-type de Rekordbox6Database: nunca abre un master.db real."""

    def __init__(self, contents: list[_C], db_dir: Path) -> None:
        self.contents, self.db_directory = contents, db_dir
        self.commits = 0
        self.rollbacks = 0

    def get_content(self) -> list[_C]:
        return list(self.contents)

    def update_content_path(self, content, chosen, save=True, check_path=True, commit=False) -> None:
        content.FolderPath = str(chosen)

    def commit(self) -> None:
        self.commits += 1

    def rollback(self) -> None:
        self.rollbacks += 1

    def close(self) -> None:
        pass


class TestRekordboxFindBrokenScoped:
    def test_only_scoped_content_is_returned(self) -> None:
        db = _FakeRbDb([_C("/Z/n/a.mp3", "a", ID="1"), _C("/Z/n/b.mp3", "b", ID="2")], Path("."))
        sc = rc.RelocateScope("P", frozenset({"/Z/n/a.mp3"}))
        assert [b.content_id for _, b in rr.find_broken_content(db, scope=sc)] == ["1"]

    def test_no_scope_returns_all(self) -> None:
        db = _FakeRbDb([_C("/Z/n/a.mp3"), _C("/Z/n/b.mp3", ID="2")], Path("."))
        assert len(rr.find_broken_content(db)) == 2

    def test_empty_scope_returns_nothing(self) -> None:
        db = _FakeRbDb([_C("/Z/n/a.mp3")], Path("."))
        assert rr.find_broken_content(db, scope=rc.RelocateScope("v", frozenset())) == []

    def test_out_of_scope_content_never_hits_the_disk(self, monkeypatch) -> None:
        db = _FakeRbDb([_C("/Z/n/a.mp3", ID="1"), _C("/Z/n/b.mp3", ID="2")], Path("."))
        checked: list[str] = []
        real = rr.resolve_path
        monkeypatch.setattr(rr, "resolve_path", lambda raw: (checked.append(raw), real(raw))[1])
        rr.find_broken_content(db, scope=rc.RelocateScope("P", frozenset({"/Z/n/a.mp3"})))
        assert checked == ["/Z/n/a.mp3"]


def _rb_setup(tmp_path: Path, names: list[str], monkeypatch) -> tuple[_FakeRbDb, Path, Path]:
    master = tmp_path / "master.db"
    master.write_bytes(b"fake-master-db")
    contents = [_C(f"/Z/nope/{n}.mp3", n, ID=str(i)) for i, n in enumerate(names)]
    fake = _FakeRbDb(contents, tmp_path)
    monkeypatch.setattr(rr, "Rekordbox6Database", lambda *a, **k: fake)
    monkeypatch.setattr(rr, "is_rekordbox_running", lambda: False)
    disk = tmp_path / "disk"
    disk.mkdir()
    for n in names:
        (disk / f"{n}.mp3").write_text("x")   # todas tienen reemplazo posible
    return fake, master, disk


def _run_rb(master: Path, disk: Path, scope) -> list[tuple]:
    w = rr.RekordboxRelocateWorker(master, disk, auto_resolve=True, scope=scope)
    done: list[tuple] = []
    w.finished_ok.connect(lambda *a: done.append(a))
    w.run()
    return done


class TestRekordboxWorkerScoped:
    def test_only_the_scoped_track_is_repaired_the_other_is_untouched(self, tmp_path, monkeypatch) -> None:
        fake, master, disk = _rb_setup(tmp_path, ["a", "b"], monkeypatch)
        done = _run_rb(master, disk, rc.RelocateScope("P", frozenset({"/Z/nope/a.mp3"})))
        assert done[-1] == (1, 0, 0, "ok")
        assert fake.contents[0].FolderPath == str(disk / "a.mp3")
        assert fake.contents[1].FolderPath == "/Z/nope/b.mp3"      # fuera del alcance
        assert fake.commits == 1

    def test_scope_with_no_matching_track_commits_nothing_and_makes_no_backup(self, tmp_path, monkeypatch) -> None:
        fake, master, disk = _rb_setup(tmp_path, ["a"], monkeypatch)
        done = _run_rb(master, disk, rc.RelocateScope("otra", frozenset({"/no/esta.mp3"})))
        assert done[-1] == (0, 0, 0, "ok")
        assert fake.commits == 0
        assert not (tmp_path / "listBuddy_backups").exists()

    def test_no_scope_repairs_everything_like_before(self, tmp_path, monkeypatch) -> None:
        fake, master, disk = _rb_setup(tmp_path, ["a", "b"], monkeypatch)
        done = _run_rb(master, disk, None)
        assert done[-1] == (2, 0, 0, "ok")
        assert fake.commits == 1

    def test_same_content_in_two_playlists_is_one_repair(self, tmp_path, monkeypatch) -> None:
        # Rekordbox liga playlists por Content.ID: una sola fila repara a todas.
        fake, master, disk = _rb_setup(tmp_path, ["a"], monkeypatch)
        done = _run_rb(master, disk, rc.RelocateScope("uno", frozenset({"/Z/nope/a.mp3"})))
        assert done[-1][0] == 1
        assert fake.contents[0].FolderPath == str(disk / "a.mp3")


# ───────────── Criterio 3: el backup es el mismo y va antes del primer write ─────────────

class TestBackupBeforeFirstWriteWithScope:
    def test_traktor_backup_then_write_and_real_backup_has_original_bytes(self, tmp_path, monkeypatch) -> None:
        nml = _nml(tmp_path, ["a", "b"])
        original = nml.read_bytes()
        disk = tmp_path / "disk"; disk.mkdir(); (disk / "a.mp3").write_text("x")
        order: list[str] = []
        real_backup, real_write = tr.backup_collection, tr.write_atomic
        monkeypatch.setattr(tr, "backup_collection", lambda p: (order.append("backup"), real_backup(p))[1])
        monkeypatch.setattr(tr, "write_atomic", lambda t, p: (order.append("write"), real_write(t, p))[1])
        _run_traktor(nml, disk, rc.RelocateScope("P", frozenset({_raw("a")})), monkeypatch)
        assert order == ["backup", "write"]
        backups = list((tmp_path / "listBuddy_backups").glob("*"))
        assert len(backups) == 1 and backups[0].read_bytes() == original

    def test_traktor_backup_failure_aborts_without_writing(self, tmp_path, monkeypatch) -> None:
        nml = _nml(tmp_path, ["a"])
        original = nml.read_bytes()
        disk = tmp_path / "disk"; disk.mkdir(); (disk / "a.mp3").write_text("x")

        def boom(_p):
            raise OSError("sin espacio")

        monkeypatch.setattr(tr, "backup_collection", boom)
        done, _ = _run_traktor(nml, disk, rc.RelocateScope("P", frozenset({_raw("a")})), monkeypatch)
        assert done[-1][3] == "error"
        assert nml.read_bytes() == original

    def test_rekordbox_backup_then_commit(self, tmp_path, monkeypatch) -> None:
        fake, master, disk = _rb_setup(tmp_path, ["a", "b"], monkeypatch)
        order: list[str] = []
        real_backup = rr.backup_master_db
        monkeypatch.setattr(rr, "backup_master_db", lambda p: (order.append("backup"), real_backup(p))[1])
        real_commit = fake.commit
        monkeypatch.setattr(fake, "commit", lambda: (order.append("commit"), real_commit())[1])
        _run_rb(master, disk, rc.RelocateScope("P", frozenset({"/Z/nope/a.mp3"})))
        assert order == ["backup", "commit"]
        assert len(list((tmp_path / "listBuddy_backups").glob("*"))) == 1

    def test_rekordbox_backup_failure_rolls_back_and_does_not_commit(self, tmp_path, monkeypatch) -> None:
        fake, master, disk = _rb_setup(tmp_path, ["a"], monkeypatch)

        def boom(_p):
            raise OSError("sin espacio")

        monkeypatch.setattr(rr, "backup_master_db", boom)
        done = _run_rb(master, disk, rc.RelocateScope("P", frozenset({"/Z/nope/a.mp3"})))
        assert done[-1][3] == "error"
        assert fake.commits == 0 and fake.rollbacks == 1
