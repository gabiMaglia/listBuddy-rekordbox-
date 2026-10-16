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


_UNUSED_QT = ("QtPdf.framework", "QtQuick.framework", "QtQml.framework", "QtQmlMeta.framework",
              "QtQmlModels.framework", "QtQmlWorkerScript.framework", "QtVirtualKeyboard.framework",
              "QtVirtualKeyboardQml.framework", "libqpdf.dylib", "libqtvirtualkeyboardplugin.dylib")


def _fake_bundle(tmp_path, *, dirty: str | None):
    app = tmp_path / "List Buddy.app" / "Contents" / "Frameworks"
    app.mkdir(parents=True)
    (app / "libok.dylib").write_bytes(b"")
    (app / "QtCore.framework").mkdir()
    if dirty in _UNUSED_QT:
        (app / dirty).mkdir()
    elif dirty == "sqlalchemy":
        (app / "sqlalchemy").mkdir()
    elif dirty == "ini":
        (app.parent / "Resources").mkdir()
        (app.parent / "Resources" / ".rbe_settings.ini").write_text("x")
    return tmp_path / "List Buddy.app"


@pytest.mark.skipif(shutil.which("bash") is None, reason="requiere bash")
@pytest.mark.parametrize(
    "dirty,expected_ok",
    [(None, True), ("sqlalchemy", False), ("ini", False)] + [(m, False) for m in _UNUSED_QT],
)
def test_check_bundle_detects_forbidden_content(tmp_path, dirty, expected_ok) -> None:
    app = _fake_bundle(tmp_path, dirty=dirty)
    r = subprocess.run(["bash", str(_CHECK), str(app)], capture_output=True, text=True)
    assert (r.returncode == 0) is expected_ok, r.stdout + r.stderr


@pytest.mark.parametrize("script", [_RELEASE, _CHECK])
def test_release_scripts_are_executable_in_git(script) -> None:
    """QA T-087: check_bundle.sh estaba en git como 100644 y release_mac.sh lo
    invoca como ejecutable → «Permission denied» en una checkout limpia."""
    mode = subprocess.run(
        ["git", "ls-files", "-s", str(script.relative_to(PROJECT_ROOT))],
        cwd=PROJECT_ROOT, capture_output=True, text=True, check=True,
    ).stdout.split()[0]
    assert mode == "100755", f"{script.name} está en git como {mode}"


def test_build_windows_matches_spec_output_and_pins_pyinstaller() -> None:
    """TEC-11/APP-19: el spec de Windows es one-dir (dist/listBuddy/listBuddy.exe) y PyInstaller va pineado."""
    ps1 = (PROJECT_ROOT / "scripts" / "build_windows.ps1").read_text(encoding="utf-8")
    spec = (PROJECT_ROOT / "rb_exporter.spec").read_text(encoding="utf-8")
    assert "name='listBuddy'" in spec and "COLLECT(" in spec          # one-dir
    assert r"dist\listBuddy\listBuddy.exe" in ps1
    assert r'"dist\listBuddy.exe"' not in ps1
    release = _RELEASE.read_text(encoding="utf-8")
    pin = re.search(r"pyinstaller==([\d.]+)", ps1)
    assert pin and pin.group(1) == re.search(r"pyinstaller==([\d.]+)", release).group(1)
    assert not re.search(r"install pyinstaller\s*--quiet", ps1)


def test_claude_md_upx_matches_spec() -> None:
    spec = (PROJECT_ROOT / "rb_exporter.spec").read_text(encoding="utf-8")
    doc = (PROJECT_ROOT / "CLAUDE.md").read_text(encoding="utf-8")
    assert "upx=True" not in spec and "upx=False" in spec
    assert "UPX está habilitado" not in doc and "upx=True" not in doc

# ── T-096: cadena de suministro y release ───────────────────────────────────

def _fake_python(tmp_path, version: str):
    """Intérprete falso: responde `version` a cualquier -c (lo que el script le pregunta)."""
    fake = tmp_path / f"python-{version}"
    fake.write_text(f'#!/bin/sh\necho "{version}"\n')
    fake.chmod(0o755)
    return fake


def _env(tmp_path, version: str, **extra_env):
    import os
    env = {k: v for k, v in os.environ.items() if k != "ALLOW_OLD_PYTHON"}
    env["PYTHON"] = str(_fake_python(tmp_path, version))
    env.update(extra_env)
    return env


def _dry_run(tmp_path, version: str, **extra_env):
    return subprocess.run(["bash", str(_RELEASE), "--dry-run"], cwd=PROJECT_ROOT,
                          env=_env(tmp_path, version, **extra_env),
                          capture_output=True, text=True, timeout=60)


def test_release_requires_python_3_14_8_static() -> None:
    code = "\n".join(_code_lines(_RELEASE))
    for needle in ("3.14.8", "PYTHON", "ALLOW_OLD_PYTHON", "brew install python@3.14", "python.org", "sort -V"):
        assert needle in code, needle


@pytest.mark.skipif(shutil.which("bash") is None, reason="requiere bash")
def test_release_aborts_on_old_python_and_explains_install(tmp_path) -> None:
    r = _dry_run(tmp_path, "3.14.7")
    assert r.returncode != 0, r.stdout
    assert "3.14.8" in r.stderr and "brew install python@3.14" in r.stderr and "ALLOW_OLD_PYTHON=1" in r.stderr


@pytest.mark.skipif(shutil.which("bash") is None, reason="requiere bash")
@pytest.mark.parametrize("version,extra", [("3.14.8", {}), ("3.15.0", {}), ("3.14.7", {"ALLOW_OLD_PYTHON": "1"})])
def test_release_accepts_new_python_or_override(tmp_path, version, extra) -> None:
    r = _dry_run(tmp_path, version, **extra)
    assert r.returncode == 0, r.stdout + r.stderr


@pytest.mark.skipif(shutil.which("bash") is None, reason="requiere bash")
def test_dry_run_prints_plan_without_building(tmp_path) -> None:
    """TEC-13: --dry-run valida prerrequisitos e imprime el plan; no buildea ni toca build/ ni dist/."""
    build, dist = PROJECT_ROOT / "build", PROJECT_ROOT / "dist"
    before = (build.exists(), sorted(p.name for p in dist.glob("*")) if dist.exists() else None)
    r = _dry_run(tmp_path, "3.14.8")
    after = (build.exists(), sorted(p.name for p in dist.glob("*")) if dist.exists() else None)
    assert r.returncode == 0, r.stdout + r.stderr
    assert before == after
    for needle in ("[dry-run]", "pyinstaller", "check_bundle.sh", "codesign", ".dmg.sha256", "-src.tar.gz"):
        assert needle in r.stdout, needle


def test_release_skip_build_flag_static() -> None:
    code = "\n".join(_code_lines(_RELEASE))
    assert "--skip-build" in code and "SKIP_BUILD" in code


@pytest.mark.skipif(shutil.which("bash") is None, reason="requiere bash")
def test_skip_build_without_existing_app_fails_clearly(tmp_path) -> None:
    work = tmp_path / "repo"
    (work / "scripts").mkdir(parents=True)
    shutil.copy(_RELEASE, work / "scripts" / "release_mac.sh")
    shutil.copy(PROJECT_ROOT / "entitlements.plist", work)
    (work / "ui.py").write_text('_APP_VERSION = "9.9.9"\n')
    r = subprocess.run(["bash", str(work / "scripts" / "release_mac.sh"), "--skip-build"],
                       cwd=work, env=_env(tmp_path, "3.14.8"), capture_output=True, text=True, timeout=60)
    assert r.returncode != 0 and "--skip-build" in r.stderr and "List Buddy.app" in r.stderr


def test_release_publishes_checksums_and_source_tarball_static() -> None:
    code = "\n".join(_code_lines(_RELEASE))
    for needle in ("shasum -a 256", ".dmg.sha256", "-src.tar.gz", ".tar.gz.sha256",
                   "git archive --format=tar.gz --prefix=listbuddy-${VERSION}/"):
        assert needle in code, needle
    assert "--require-hashes" in code and "pyinstaller==6.20.0" in code


def test_source_tarball_has_licenses_and_no_dev_or_engram_files(tmp_path) -> None:
    """D-27 / LEG-07: el tarball de fuentes es corresponding source y no lleva venvs ni engram/."""
    import tarfile
    out = tmp_path / "src.tar.gz"
    subprocess.run(["git", "archive", "--format=tar.gz", "--prefix=listbuddy-9.9.9/", "-o", str(out), "HEAD"],
                   cwd=PROJECT_ROOT, check=True)
    with tarfile.open(out) as tar:
        names = tar.getnames()
    assert "listbuddy-9.9.9/LICENSE" in names
    assert "listbuddy-9.9.9/THIRD_PARTY_NOTICES.md" in names
    assert "listbuddy-9.9.9/rb_exporter.spec" in names
    bad = [n for n in names if "/.venv" in n or n.startswith("listbuddy-9.9.9/engram")
           or "/dist/" in n or "/build/" in n]
    assert bad == []


def test_readme_download_section_explains_checksum_verification() -> None:
    readme = (PROJECT_ROOT / "README.md").read_text(encoding="utf-8")
    section = readme.split("## Descargar", 1)[1].split("\n## ", 1)[0]
    for needle in ("shasum -a 256 -c", ".dmg.sha256", "-src.tar.gz"):
        assert needle in section, needle
