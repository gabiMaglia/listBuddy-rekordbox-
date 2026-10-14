from __future__ import annotations

import sys
from pathlib import Path

import app_paths


def test_data_dir_is_per_user_and_created(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(Path, "home", staticmethod(lambda: tmp_path))
    monkeypatch.setenv("APPDATA", str(tmp_path / "AppData"))
    d = app_paths.data_dir()
    assert d.is_dir() and tmp_path in d.parents
    if sys.platform == "darwin":
        assert d == tmp_path / "Library" / "Application Support" / "listBuddy"


def test_frozen_settings_live_in_the_data_dir(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(Path, "home", staticmethod(lambda: tmp_path))
    monkeypatch.setenv("APPDATA", str(tmp_path / "AppData"))
    assert app_paths.default_settings_path(frozen=True) == app_paths.data_dir() / "settings.ini"


def test_dev_settings_stay_next_to_the_code() -> None:
    p = app_paths.default_settings_path(frozen=False)
    assert p.name == ".rbe_settings.ini" and p.parent == Path(app_paths.__file__).parent
