"""T-090: textos legales para cobrar (informe T-086 legal). Solo lee archivos, sin Qt."""
from __future__ import annotations

import re

from _qt_isolated import PROJECT_ROOT

_TEXT_FILES = ("about_dialog.py", "README.md", "DISCLAIMER.md", "branding.py", "CHANGELOG.md")


def _read(name: str) -> str:
    return (PROJECT_ROOT / name).read_text(encoding="utf-8")


def _flat(name: str) -> str:
    text = _read(name)
    if name.endswith(".py"):  # une los literales contiguos del código fuente
        text = re.sub(r'"\s*\n\s*f?"', "", text)
    return " ".join(text.split())


def test_no_free_of_charge_claim_in_user_facing_files() -> None:
    # «Free Software Foundation» es un nombre propio; «software libre» va con «libre».
    pattern = re.compile(r"gratuit|gratis|\bfree\b", re.I)
    hits = []
    for name in _TEXT_FILES:
        text = _read(name).replace("Free Software Foundation", "")
        hits += [f"{name}: {m.group(0)}" for m in pattern.finditer(text)]
    assert hits == []
    assert not (PROJECT_ROOT / "landing").exists() or not re.search(
        pattern, " ".join(p.read_text(encoding="utf-8", errors="ignore")
                          for p in (PROJECT_ROOT / "landing").rglob("*") if p.is_file()))


def test_software_libre_wording_replaces_gratuito() -> None:
    assert "software libre (GPL v3)" in _flat("README.md")
    assert "software libre (GPL v3)" in _flat("about_dialog.py")


def test_no_reverse_engineering_wording() -> None:
    pattern = re.compile(r"ingenier[ií]a inversa|reverse.engineer", re.I)
    for name in ("README.md", "CLAUDE.md", "DISCLAIMER.md", "THIRD_PARTY_NOTICES.md",
                 "about_dialog.py", "branding.py", "CHANGELOG.md"):
        assert not pattern.search(_read(name)), name
    assert "archivo XML de texto plano" in _flat("README.md")


def test_disclaimer_liability_and_consumer_rights() -> None:
    flat = _flat("DISCLAIMER.md")
    for needle in (
        "En la máxima medida que permita la ley que te proteja",
        "daños indirectos, lucro cesante",
        "se limita al precio que pagaste por tu copia",
        "no se aplica** a los daños causados con dolo o culpa grave",
        "Ley 24.240", "Código Civil y Comercial", "Directiva 2019/770",
        "No condiciona ni limita ninguno de los derechos",
    ):
        assert needle in flat, needle
    assert "Al instalar o usar List Buddy aceptás este aviso" not in flat
    assert "ningún daño" not in flat


def test_disclaimer_warranty_return_law_age_and_contact() -> None:
    flat = _flat("DISCLAIMER.md")
    for needle in (
        "Garantía legal, conformidad y devolución",
        "14 días corridos", "art. 34 de la Ley 24.240",
        "Ley aplicable y jurisdicción", "leyes de la República Argentina",
        "mayor de edad",
        "Gabriel Maglia",
    ):
        assert needle in flat, needle
    # Datos que el informe deja al PO / abogado no se inventan.
    assert flat.count("[A DEFINIR POR EL PO]") >= 3


def test_disclaimer_trademarks_and_no_official_product() -> None:
    flat = _flat("DISCLAIMER.md")
    for needle in (
        "rekordbox es marca de AlphaTheta Corporation",
        "Pioneer DJ es marca de PIONEER CORPORATION, usada bajo licencia",
        "Traktor y Native Instruments son marcas de Native Instruments GmbH",
        "no es un producto oficial",
    ):
        assert needle in flat, needle


def test_disclaimer_version_bumped_so_notice_shows_again() -> None:
    version = re.search(r'^DISCLAIMER_VERSION = "([^"]+)"', _read("about_dialog.py"), re.M).group(1)
    assert version != "2026-10-15"


def test_third_party_notices_ffmpeg_exact_version_and_qt_pdf_license() -> None:
    notices = _read("THIRD_PARTY_NOTICES.md")
    assert "| 7.1.3 |" in notices and "FFmpeg 7.1.3:" in notices
    assert "FFmpeg 7.1:" not in notices
    row = next(r for r in notices.splitlines() if r.startswith("| Qt PDF"))
    assert "LGPL-3.0" in row


def test_trademark_attribution_in_about_and_readme() -> None:
    for flat in (_flat("about_dialog.py"), _flat("README.md")):
        for needle in (
            "rekordbox es una marca de AlphaTheta Corporation",
            "Pioneer DJ es una marca de Pioneer Corporation usada bajo licencia",
            "Traktor es una marca de Native Instruments GmbH",
            "no es un producto oficial",
        ):
            assert needle in flat, needle


def test_source_code_notice_next_to_the_download() -> None:
    readme = _read("README.md")
    assert "## Código fuente" in readme
    about = _flat("about_dialog.py")
    for text in (" ".join(readme.split()), about):
        assert "el código de cada versión está en" in text
    assert "SOURCE_URL" in about


def test_first_run_notice_mentions_purchase_rights_and_non_official() -> None:
    src = _flat("about_dialog.py")
    assert "con los derechos que te da la ley de tu país" in src
    assert "no es un producto de AlphaTheta" in src
    assert "Si compraste tu copia" in src
