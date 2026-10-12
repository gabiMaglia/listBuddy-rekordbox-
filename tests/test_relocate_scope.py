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
