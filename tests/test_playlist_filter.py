"""T-064: filtro de playlists (puro, sin Qt): sin distinguir mayúsculas ni acentos."""
from __future__ import annotations

import pytest

from playlist_filter import matches, normalize


@pytest.mark.parametrize("name", ["Tech House", "DEEP TECH", "Techno", "minimal-tech"])
def test_tech_matches_names_containing_it_any_case(name: str) -> None:
    assert matches(name, "tech")
    assert matches(name, "TeCh")


@pytest.mark.parametrize("name", ["Deep House", "Teh", "Minimal"])
def test_tech_does_not_match_unrelated_names(name: str) -> None:
    assert not matches(name, "tech")


def test_accents_are_ignored_in_both_directions() -> None:
    assert matches("Café del Mar", "cafe")
    assert matches("Cafe del Mar", "CAFÉ")
    assert matches("Música Cálida", "musica calida")


def test_empty_or_blank_query_matches_everything() -> None:
    assert matches("Cualquiera", "")
    assert matches("Cualquiera", "   ")


def test_query_is_trimmed_but_inner_text_must_match_as_substring() -> None:
    assert matches("Deep Tech", "  deep t ")
    assert not matches("Deep House Tech", "deep tech")


def test_normalize_is_idempotent_and_lowercase() -> None:
    once = normalize("ÁRBOL Çedilla")
    assert once == "arbol cedilla"
    assert normalize(once) == once
