from __future__ import annotations

import json
from pathlib import Path, PureWindowsPath

import pytest

import rekordbox_fixes
from rekordbox_fixes import FixStore, fixes_path_for


def test_missing_file_is_empty(tmp_path: Path) -> None:
    assert FixStore(tmp_path / "f.json").load() == {}


def test_merge_persists_and_accumulates(tmp_path: Path) -> None:
    # Rutas absolutas del SO: «/new/a.mp3» no es absoluta en Windows (T-112).
    a, b = str(tmp_path / "new" / "a.mp3"), str(tmp_path / "new" / "b.mp3")
    s = FixStore(tmp_path / "f.json")
    assert s.merge({"file://localhost/a.mp3": a}) == {"file://localhost/a.mp3": a}
    s.merge({"file://localhost/b.mp3": b})
    assert FixStore(tmp_path / "f.json").load() == {"file://localhost/a.mp3": a, "file://localhost/b.mp3": b}
    assert s.count() == 2


@pytest.mark.parametrize("value, accepted", [
    ("C:\\Music\\a.mp3", True),
    ("\\\\nas\\music\\a.mp3", True),
    ("/x/y/a.mp3", False),          # POSIX en Windows: el JSON es por máquina, se descarta
    ("Music\\a.mp3", False),
])
def test_load_is_strict_about_absolute_paths_in_windows_semantics(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch, value: str, accepted: bool) -> None:
    monkeypatch.setattr(rekordbox_fixes, "_PURE", PureWindowsPath)
    p = tmp_path / "f.json"
    p.write_text(json.dumps({"fixes": {"k": value}}), encoding="utf-8")
    assert FixStore(p).load() == ({"k": value} if accepted else {})


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


def test_load_discards_non_str_and_relative_values_with_a_warning(
    tmp_path: Path, caplog
) -> None:
    import logging

    good = str(tmp_path / "ok.mp3")
    p = tmp_path / "f.json"
    p.write_text(json.dumps({"version": 1, "fixes": {
        "file://localhost/a.mp3": 1,
        "file://localhost/b.mp3": None,
        "file://localhost/c.mp3": ["/x/c.mp3"],
        "file://localhost/d.mp3": "rel/d.mp3",
        "file://localhost/e.mp3": good,
        "": good,
    }}), encoding="utf-8")
    with caplog.at_level(logging.WARNING, logger="listBuddy"):
        assert FixStore(p).load() == {"file://localhost/e.mp3": good}
    assert len([r for r in caplog.records if r.levelno == logging.WARNING]) == 5
