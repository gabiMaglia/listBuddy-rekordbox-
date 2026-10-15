"""T-087: entitlements válidos para codesign y scripts de release (chequeos estáticos)."""
from __future__ import annotations

import plistlib
import re
import shutil
import subprocess
import sys
import xml.etree.ElementTree as ET

import pytest

from _qt_isolated import PROJECT_ROOT

_ENT = PROJECT_ROOT / "entitlements.plist"
_RELEASE = PROJECT_ROOT / "scripts" / "release_mac.sh"
_CHECK = PROJECT_ROOT / "scripts" / "check_bundle.sh"


def test_entitlements_only_allow_unsigned_executable_memory() -> None:
    data = plistlib.loads(_ENT.read_bytes())
    assert data == {"com.apple.security.cs.allow-unsigned-executable-memory": True}


def test_entitlements_comments_have_no_double_dash() -> None:
    # codesign rechaza `--` dentro de un comentario XML aunque plutil -lint lo acepte (APP-01).
    text = _ENT.read_text(encoding="utf-8")
    for comment in re.findall(r"<!--(.*?)-->", text, re.S):
        assert "--" not in comment
    ET.fromstring(text.split("?>", 1)[1].split("<!DOCTYPE", 1)[0] + "<x/>")  # prólogo sano


@pytest.mark.skipif(sys.platform != "darwin", reason="plutil es de macOS")
def test_entitlements_plutil_lint() -> None:
    r = subprocess.run(["plutil", "-lint", str(_ENT)], capture_output=True, text=True)
    assert r.returncode == 0, r.stdout + r.stderr


def _code_lines(path) -> list[str]:
    return [ln for ln in path.read_text(encoding="utf-8").splitlines() if not ln.lstrip().startswith("#")]


def test_release_script_syntax_and_signing_flags() -> None:
    assert subprocess.run(["bash", "-n", str(_RELEASE)]).returncode == 0
    code = "\n".join(_code_lines(_RELEASE))
    sign_lines = [ln for ln in code.splitlines() if "codesign" in ln and "--verify" not in ln]
    assert sign_lines and all("--deep" not in ln for ln in sign_lines)
    assert "--options runtime" in code and "--timestamp" in code
    assert "--entitlements entitlements.plist" in code


def test_release_script_notarization_flow() -> None:
    code = "\n".join(_code_lines(_RELEASE))
    for needle in ("trap ", "--dry-run", "notarytool submit", "stapler staple", "stapler validate",
                   "context:primary-signature", "hdiutil verify", "NOTARY_PROFILE", "check_bundle.sh",
                   "LSMinimumSystemVersion", "minos"):
        assert needle in code, needle
    # sin credenciales de notarización el script avisa en vez de fallar
    assert re.search(r"DEVELOPER_ID.*NOTARY_PROFILE|NOTARY_PROFILE.*DEVELOPER_ID", code, re.S)


def _fake_bundle(tmp_path, *, dirty: str | None):
    app = tmp_path / "List Buddy.app" / "Contents" / "Frameworks"
    app.mkdir(parents=True)
    (app / "libok.dylib").write_bytes(b"")
    if dirty == "sqlalchemy":
        (app / "sqlalchemy").mkdir()
    elif dirty == "ini":
        (app.parent / "Resources").mkdir()
        (app.parent / "Resources" / ".rbe_settings.ini").write_text("x")
    return tmp_path / "List Buddy.app"


@pytest.mark.skipif(shutil.which("bash") is None, reason="requiere bash")
@pytest.mark.parametrize("dirty,expected_ok", [(None, True), ("sqlalchemy", False), ("ini", False)])
def test_check_bundle_detects_forbidden_content(tmp_path, dirty, expected_ok) -> None:
    app = _fake_bundle(tmp_path, dirty=dirty)
    r = subprocess.run(["bash", str(_CHECK), str(app)], capture_output=True, text=True)
    assert (r.returncode == 0) is expected_ok, r.stdout + r.stderr
