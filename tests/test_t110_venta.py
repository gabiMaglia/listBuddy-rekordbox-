"""T-110: canal de venta 1.0.0 (LEG-22) y marcadores del PO. Solo lee archivos, sin Qt."""
from __future__ import annotations

import re

from _qt_isolated import PROJECT_ROOT


def _read(name: str) -> str:
    return (PROJECT_ROOT / name).read_text(encoding="utf-8")


def _flat(name: str) -> str:
    text = _read(name)
    if name.endswith(".py"):
        text = re.sub(r'"\s*\n\s*f?"', "", text)
    return " ".join(text.split())


def test_item1_no_markers_and_real_seller_data() -> None:
    for name in ("DISCLAIMER.md", "about_dialog.py", "README.md", "branding.py"):
        assert "[A DEFINIR POR EL PO" not in _read(name), name
    flat = _flat("DISCLAIMER.md")
    for needle in (
        "Polar Software Inc.", "polar.sh", "Monotributista", "CUIT 20-32758971-8",
        "Rosario, Argentina", "gab.maglia@gmail.com",
    ):
        assert needle in flat, needle


def test_item2_clauses_return_law_age_warranty() -> None:
    flat = _flat("DISCLAIMER.md")
    for needle in (
        "10 días corridos", "art. 34 de la Ley 24.240", "política de devolución de Polar",
        "tribunales ordinarios de Rosario", "derechos irrenunciables",
        "18 años", "garantía legal",
        "te devolvemos el dinero si List Buddy no funciona",
    ):
        assert needle in flat, needle
    assert "Ciudad Autónoma de Buenos Aires" not in flat
    assert "14 días" not in flat


def test_item2_first_run_summary_says_not_official() -> None:
    src = _flat("about_dialog.py")
    summary = src[src.index("_NOTICE_TEXT = ("):]
    assert "no es un producto oficial de AlphaTheta" in summary
    assert "Native Instruments" in summary
