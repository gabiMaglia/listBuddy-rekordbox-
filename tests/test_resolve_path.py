"""T-093 (TEC-19): `/X/...` solo se reinterpreta como `X:/...` si parece ruta de Windows."""
from __future__ import annotations

import sys
from pathlib import Path

import rekordbox_export as rbx


def _record_exists(monkeypatch, existing: set[str]) -> list[str]:
    seen: list[str] = []

    def fake_exists(self: Path) -> bool:
        key = str(self).replace("\\", "/")
        seen.append(key)
        return key in existing

    monkeypatch.setattr(Path, "exists", fake_exists)
    return seen


def test_posix_path_that_exists_is_not_transformed(monkeypatch) -> None:
    monkeypatch.setattr(sys, "platform", "darwin")
    seen = _record_exists(monkeypatch, {"/a/musica.mp3"})
    assert rbx.resolve_path("/a/musica.mp3") == Path("/a/musica.mp3")
    assert "a:/musica.mp3" not in seen


def test_posix_volume_style_non_windows_looking_path_is_left_alone(monkeypatch) -> None:
    monkeypatch.setattr(sys, "platform", "linux")
    seen = _record_exists(monkeypatch, set())
    assert rbx.resolve_path("/v/musica/x.mp3") is None
    assert not any(s.startswith("v:") for s in seen)


def test_windows_looking_volume_path_is_converted_off_windows(monkeypatch) -> None:
    monkeypatch.setattr(sys, "platform", "darwin")
    seen = _record_exists(monkeypatch, {"C:/Users/dj/x.mp3"})
    assert rbx.resolve_path("/C/Users/dj/x.mp3") == Path("C:/Users/dj/x.mp3")
    assert "C:/Users/dj/x.mp3" in seen


def test_any_volume_letter_is_converted_on_win32(monkeypatch) -> None:
    monkeypatch.setattr(sys, "platform", "win32")
    _record_exists(monkeypatch, {"D:/musica/x.mp3"})
    assert rbx.resolve_path("/D/musica/x.mp3") == Path("D:/musica/x.mp3")


def test_posix_existing_wins_over_windows_looking_guess(monkeypatch) -> None:
    monkeypatch.setattr(sys, "platform", "linux")
    _record_exists(monkeypatch, {"/C/Users/x.mp3"})
    assert rbx.resolve_path("/C/Users/x.mp3") == Path("/C/Users/x.mp3")


def test_native_windows_path_and_empty_still_work(monkeypatch) -> None:
    monkeypatch.setattr(sys, "platform", "win32")
    _record_exists(monkeypatch, {"C:/m/x.mp3"})
    assert rbx.resolve_path("C:/m/x.mp3") == Path("C:/m/x.mp3")
    assert rbx.resolve_path("") is None
