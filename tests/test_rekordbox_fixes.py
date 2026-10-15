from __future__ import annotations

import json
from pathlib import Path

from rekordbox_fixes import FixStore, fixes_path_for


def test_missing_file_is_empty(tmp_path: Path) -> None:
    assert FixStore(tmp_path / "f.json").load() == {}


def test_merge_persists_and_accumulates(tmp_path: Path) -> None:
    s = FixStore(tmp_path / "f.json")
    assert s.merge({"file://localhost/a.mp3": "/new/a.mp3"}) == {"file://localhost/a.mp3": "/new/a.mp3"}
    s.merge({"file://localhost/b.mp3": "/new/b.mp3"})
    assert FixStore(tmp_path / "f.json").load() == {
        "file://localhost/a.mp3": "/new/a.mp3", "file://localhost/b.mp3": "/new/b.mp3",
    }
    assert s.count() == 2


def test_corrupt_file_reads_as_empty_and_is_not_deleted(tmp_path: Path) -> None:
    p = tmp_path / "f.json"
    p.write_text("{no es json", encoding="utf-8")
    assert FixStore(p).load() == {}
    assert p.exists()


def test_save_is_atomic_json(tmp_path: Path) -> None:
    p = tmp_path / "sub" / "f.json"
    FixStore(p).save({"k": "v"})
    assert json.loads(p.read_text(encoding="utf-8")) == {"version": 1, "fixes": {"k": "v"}}
    assert not list(p.parent.glob("*.tmp"))


def test_clear_removes_everything(tmp_path: Path) -> None:
    s = FixStore(tmp_path / "f.json")
    s.merge({"k": "v"})
    s.clear()
    assert s.load() == {} and s.count() == 0


def test_fixes_live_next_to_the_settings_file(tmp_path: Path) -> None:
    assert fixes_path_for(tmp_path / "s.ini") == tmp_path / "rekordbox_fixes.json"


def test_failed_save_removes_the_tmp_and_reraises(tmp_path, monkeypatch) -> None:
    import pytest
    import rekordbox_fixes as rf

    store = rf.FixStore(tmp_path / "rekordbox_fixes.json")

    def boom(*a, **k):
        assert (tmp_path / "rekordbox_fixes.json.tmp").exists()
        raise OSError("disco lleno")

    monkeypatch.setattr(rf.os, "replace", boom)
    with pytest.raises(OSError):
        store.save({"a": "b"})
    assert not (tmp_path / "rekordbox_fixes.json.tmp").exists()
    assert not store.path.exists()
