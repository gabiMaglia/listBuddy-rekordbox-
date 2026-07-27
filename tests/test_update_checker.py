"""
test_update_checker.py
-----------------------
T-021 (I-8): tests de la lógica pura de comparación de versiones usada por
el chequeo de actualización. No cubre la parte de red (urllib) ni Qt —
eso se prueba manualmente lanzando la app (ver handoff), acá solo se valida
que "¿la versión remota es más nueva?" nunca dé un falso positivo/negativo,
que es lo único que podría hacer que el aviso se muestre cuando no debería
(o al revés).
"""
from __future__ import annotations

from update_checker import _is_newer, _parse_version


class TestParseVersion:
    def test_strips_v_prefix(self):
        assert _parse_version("v1.2.0") == (1, 2, 0)

    def test_no_prefix(self):
        assert _parse_version("1.2.0") == (1, 2, 0)

    def test_two_components(self):
        assert _parse_version("v2.0") == (2, 0)

    def test_non_numeric_suffix_returns_none(self):
        # ej. "v1.2.0-beta" — no asumir, mejor no mostrar el aviso.
        assert _parse_version("v1.2.0-beta") is None

    def test_empty_string_returns_none(self):
        assert _parse_version("") is None


class TestIsNewer:
    def test_patch_bump_is_newer(self):
        assert _is_newer((1, 1, 1), (1, 1, 0)) is True

    def test_same_version_is_not_newer(self):
        assert _is_newer((1, 1, 0), (1, 1, 0)) is False

    def test_older_is_not_newer(self):
        assert _is_newer((1, 0, 0), (1, 1, 0)) is False

    def test_different_length_padding_major(self):
        # "v2.0" vs "1.1.0" -> (2, 0) se rellena a (2, 0, 0)
        assert _is_newer((2, 0), (1, 1, 0)) is True

    def test_different_length_padding_equal(self):
        # "v1.1" vs "1.1.0" -> misma versión, solo distinto formato
        assert _is_newer((1, 1), (1, 1, 0)) is False
