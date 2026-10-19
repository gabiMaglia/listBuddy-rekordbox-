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


# ── T-079: contexto SSL con el CA de certifi ──────────────────────────────

import ssl
import sys
import types

import update_checker
from _qt_isolated import PROJECT_ROOT


class TestSslContext:
    def test_verification_is_never_disabled(self):
        ctx = update_checker._build_ssl_context()
        assert ctx.verify_mode == ssl.CERT_REQUIRED
        assert ctx.check_hostname is True

    def test_uses_certifi_bundle(self, monkeypatch):
        import certifi

        seen: dict[str, object] = {}
        real = ssl.create_default_context

        def spy(*args, **kwargs):
            seen.update(kwargs)
            return real()

        monkeypatch.setattr(update_checker.ssl, "create_default_context", spy)
        update_checker._build_ssl_context()
        assert seen.get("cafile") == certifi.where()

    def test_falls_back_to_default_when_certifi_missing(self, monkeypatch):
        # None en sys.modules hace que `import certifi` lance ImportError.
        monkeypatch.setitem(sys.modules, "certifi", None)
        ctx = update_checker._build_ssl_context()
        assert ctx.verify_mode == ssl.CERT_REQUIRED
        assert ctx.check_hostname is True

    def test_falls_back_when_certifi_bundle_unreadable(self, monkeypatch):
        fake = types.SimpleNamespace(where=lambda: "/no/existe/cacert.pem")
        monkeypatch.setitem(sys.modules, "certifi", fake)
        ctx = update_checker._build_ssl_context()
        assert ctx.verify_mode == ssl.CERT_REQUIRED

    def test_request_passes_context_to_urlopen(self, monkeypatch):
        captured: dict[str, object] = {}

        def fake_urlopen(req, timeout=None, context=None):
            captured["context"] = context
            raise OSError("sin red")

        monkeypatch.setattr(update_checker.urllib.request, "urlopen", fake_urlopen)
        update_checker.UpdateCheckWorker("1.0.0").run()  # no debe propagar
        assert isinstance(captured["context"], ssl.SSLContext)

    def test_no_network_is_silent(self, monkeypatch):
        def boom(*a, **k):
            raise TimeoutError("timeout")

        monkeypatch.setattr(update_checker.urllib.request, "urlopen", boom)
        emitted: list[object] = []
        w = update_checker.UpdateCheckWorker("1.0.0")
        w.update_available.connect(emitted.append)
        w.run()
        assert emitted == []


class TestCertifiPackaging:
    def test_requirements_pin_certifi_exact(self):
        reqs = (PROJECT_ROOT / "requirements.txt").read_text(encoding="utf-8").splitlines()
        assert any(r.startswith("certifi==") for r in reqs)

    def test_spec_collects_certifi(self):
        spec = (PROJECT_ROOT / "rb_exporter.spec").read_text(encoding="utf-8")
        assert "collect_data_files('certifi')" in spec
        assert "'certifi'" in spec


# ── T-092 (SEC-10): solo se abren URLs de releases del repo ────────────────

import pytest

_OK = "https://github.com/gabiMaglia/listbuddy/releases/tag/v1.2.0"


class TestSafeReleaseUrl:
    def test_accepts_release_tag(self):
        assert update_checker.safe_release_url(_OK) == _OK

    def test_accepts_releases_listing(self):
        assert update_checker.safe_release_url(update_checker._RELEASES_PAGE_URL) == update_checker._RELEASES_PAGE_URL

    @pytest.mark.parametrize("bad", [
        "file:///etc/passwd",
        "javascript:alert(1)",
        "http://github.com/gabiMaglia/listbuddy/releases",
        "https://evil.com/gabiMaglia/listbuddy/releases",
        "https://github.com.evil.com/gabiMaglia/listbuddy/releases",
        "https://github.com@evil.com/gabiMaglia/listbuddy/releases",
        "https://github.com:8443/gabiMaglia/listbuddy/releases",
        "https://github.com/otro/repo/releases/tag/v9",
        "https://github.com/gabiMaglia/listbuddy/issues/1",
        "https://github.com/gabiMaglia/listbuddy/releases/../../../evil",
        "https://github.com/gabiMaglia/listbuddy/releasesX",
        "",
        None,
        123,
    ])
    def test_rejects_everything_else(self, bad):
        assert update_checker.safe_release_url(bad) is None


class TestSafeReleaseUrlEncodedDots:
    """Verifier T-092 D2: `%2e%2e` y `.%2e` son `..` para el navegador; no pueden pasar la validación."""

    @pytest.mark.parametrize("path", ["%2e%2e/evil", "%2E%2E/evil", ".%2e/evil", "a/%2e%2e/%2e%2e/x", "%2e/x"])
    def test_percent_encoded_dot_segments_are_rejected(self, path):
        assert update_checker.safe_release_url(f"https://github.com/gabiMaglia/listbuddy/releases/{path}") is None

    @pytest.mark.parametrize("tail", ["\n", "\t", " ", "\r"])
    def test_trailing_whitespace_is_rejected(self, tail):
        assert update_checker.safe_release_url(_OK + tail) is None

    def test_plain_tag_still_accepted(self):
        assert update_checker.safe_release_url(_OK + "/download/x.dmg") == _OK + "/download/x.dmg"

