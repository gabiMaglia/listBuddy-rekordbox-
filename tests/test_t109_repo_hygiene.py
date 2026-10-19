"""T-109 / LEG-25: las capturas de diseño no viajan en el tarball ni están en el HEAD."""
from __future__ import annotations

import subprocess
import tarfile
import io

from _qt_isolated import PROJECT_ROOT


def _git(*args: str) -> bytes:
    return subprocess.run(["git", *args], cwd=PROJECT_ROOT, check=True, capture_output=True).stdout


def test_design_uploads_not_tracked() -> None:
    assert _git("ls-files", "listBuddy_design/uploads").strip() == b""


def test_source_archive_excludes_design_folder() -> None:
    # Se arma sobre el índice (write-tree) para que valga también antes del commit.
    tree = _git("write-tree").decode().strip()
    names = tarfile.open(fileobj=io.BytesIO(_git("archive", tree))).getnames()
    assert not [n for n in names if n.startswith("listBuddy_design")]


def test_openssl_version_is_generated_at_build_not_hardcoded() -> None:
    """LEG-24. El OpenSSL real es el del Python que buildea (python.org en CI/release,
    distinto del local): el aviso no fija número y el spec escribe el valor en el bundle."""
    import re

    notices = (PROJECT_ROOT / "THIRD_PARTY_NOTICES.md").read_text(encoding="utf-8")
    row = next(l for l in notices.splitlines() if l.startswith("| OpenSSL"))
    assert "licenses/openssl-version.txt" in " ".join(notices.split())
    assert not re.search(r"\d+\.\d+\.\d+", row), row
    spec = (PROJECT_ROOT / "rb_exporter.spec").read_text(encoding="utf-8")
    assert "ssl.OPENSSL_VERSION" in spec
    assert "openssl-version.txt" in spec and "(str(openssl_version_file), 'licenses')" in spec
    assert not (PROJECT_ROOT / "licenses" / "openssl-version.txt").exists()
    assert "openssl-version" not in (PROJECT_ROOT / "scripts" / "collect_licenses.py").read_text(encoding="utf-8")


def test_qt_embedded_third_party_notices_are_reproduced_and_linked() -> None:
    """LEG-27: los BSD/MIT/zlib/libpng/FreeType exigen reproducir el aviso."""
    qt = (PROJECT_ROOT / "licenses" / "qt-third-party.md").read_text(encoding="utf-8")
    for needle in ("doc.qt.io/qt-6/licenses-used-in-qt.html", "LibPNG", "HarfBuzz", "Freetype 2",
                   "PCRE2", "zlib", "LibJPEG-turbo", "Permission is hereby granted"):
        assert needle in qt, needle
    notices = (PROJECT_ROOT / "THIRD_PARTY_NOTICES.md").read_text(encoding="utf-8")
    assert "`licenses/qt-third-party.md`" in notices
    # SQLite solo viaja con QtSql, que el bundle no incluye: queda dicho, no omitido.
    assert "SQLite" in notices and "QtSql" in notices


def test_certifi_mpl_source_availability_notice() -> None:
    notices = (PROJECT_ROOT / "THIRD_PARTY_NOTICES.md").read_text(encoding="utf-8")
    assert "MPL-2.0" in notices and "sección 3.2" in notices
    assert "https://github.com/certifi/python-certifi" in notices


def test_collect_licenses_checks_the_hand_maintained_qt_file() -> None:
    assert "qt-third-party.md" in (PROJECT_ROOT / "scripts" / "collect_licenses.py").read_text(encoding="utf-8")


def _flat_disclaimer() -> str:
    return " ".join((PROJECT_ROOT / "DISCLAIMER.md").read_text(encoding="utf-8").split())


def test_disclaimer_privacy_covers_only_the_polar_purchase() -> None:
    """LEG-29 (reescrito en T-113): sin donaciones; la privacidad sigue cubriendo la compra vía Polar."""
    flat = _flat_disclaimer()
    assert "donación" not in flat and "DENSO WAVE" not in flat
    assert "Polar Software Inc. (operador de polar.sh) procesa tus datos de compra" in flat


def test_disclaimer_states_windows_scope() -> None:
    """LEG-31."""
    flat = _flat_disclaimer()
    assert "Windows 10 u 11 de 64 bits" in flat
    assert "sin firma de código" in flat and ".sha256" in flat


def test_readme_claims_are_verifiable_and_dmg_guide_present() -> None:
    """LEG-33 + APP-24."""
    readme = " ".join((PROJECT_ROOT / "README.md").read_text(encoding="utf-8").split())
    assert "Sin congelamientos" not in readme
    assert "la interfaz sigue respondiendo mientras carga" in readme
    assert "Si algo falla, no se escribe nada" not in readme
    assert ".part" in readme
    assert "Acerca de esta Mac" in readme
    assert "Chip Apple M" in readme and "arm64" in readme
    assert "Procesador Intel" in readme and "x86_64" in readme


def test_claude_md_lists_every_module_and_current_python() -> None:
    """TEC-30."""
    text = (PROJECT_ROOT / "CLAUDE.md").read_text(encoding="utf-8")
    assert "3.14.8" in text and "3.14.3" not in text
    arch = text.split("## Arquitectura", 1)[1].split("## Entorno", 1)[0]
    missing = [p.name for p in sorted(PROJECT_ROOT.glob("*.py")) if p.name not in arch]
    assert not missing, missing
