"""T-113: el producto se vende vía Polar; no queda rastro de Ko-fi ni de qrcode."""
from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
_SELF = Path(__file__).resolve()
_PATTERN = re.compile(r"ko-fi|kofi|qrcode", re.I)


def _scanned_files() -> list[Path]:
    files = list(ROOT.glob("*.py"))
    files += [ROOT / n for n in ("README.md", "DISCLAIMER.md", "THIRD_PARTY_NOTICES.md", "rb_exporter.spec")]
    files += ROOT.glob("requirements*.in")
    files += ROOT.glob("requirements*.txt")
    files += (ROOT / "licenses").rglob("*")
    files += (ROOT / "tests").rglob("*.py")
    return [p for p in files if p.is_file() and p.resolve() != _SELF]


def test_no_kofi_or_qrcode_traces() -> None:
    hits = [
        f"{p.relative_to(ROOT)}:{n}"
        for p in _scanned_files()
        for n, line in enumerate(p.read_text(encoding="utf-8", errors="ignore").splitlines(), 1)
        if _PATTERN.search(line)
    ]
    assert not hits, hits


def test_no_donation_entry_points_in_ui() -> None:
    ui = (ROOT / "ui.py").read_text(encoding="utf-8")
    assert "DonationDialog" not in ui and "_show_donation" not in ui and "_donate_btn" not in ui


def test_no_qr_trademark_in_disclaimer() -> None:
    assert "DENSO WAVE" not in (ROOT / "DISCLAIMER.md").read_text(encoding="utf-8")
