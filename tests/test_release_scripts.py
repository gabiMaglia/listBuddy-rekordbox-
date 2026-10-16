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


def test_release_script_ci_hooks() -> None:
    """T-097: el workflow de GitHub Actions llama al script con --arch-suffix y PYTHON,
    y sube el .sha256 que el script escribe al lado del DMG."""
    code = "\n".join(_code_lines(_RELEASE))
    assert "--arch-suffix" in code
    assert "uname -m" in code
    assert re.search(r'PYTHON="?\$\{PYTHON:-python3\}', code)
    assert ".sha256" in code
    # uso: aceptar los dos flags a la vez y rechazar uno desconocido
    r = subprocess.run(["bash", str(_RELEASE), "--bogus"], capture_output=True, text=True, cwd=PROJECT_ROOT)
    assert r.returncode == 2 and "--arch-suffix" in r.stderr


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
@pytest.mark.parametrize("version,extra", [("3.14.8", {}), ("3.14.10", {}), ("3.15.0", {}), ("3.14.7", {"ALLOW_OLD_PYTHON": "1"})])
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


@pytest.mark.skipif(shutil.which("bash") is None, reason="requiere bash")
def test_arch_suffix_names_dmg_with_machine_arch(tmp_path) -> None:
    """T-097 (QA D4): --arch-suffix debe dar «ListBuddy-<v>-<uname -m>.dmg»; sin el flag, sin sufijo."""
    arch = subprocess.run(["uname", "-m"], capture_output=True, text=True).stdout.strip()
    with_flag = subprocess.run(["bash", str(_RELEASE), "--dry-run", "--arch-suffix"], cwd=PROJECT_ROOT,
                               env=_env(tmp_path, "3.14.8"), capture_output=True, text=True, timeout=60)
    assert with_flag.returncode == 0, with_flag.stderr
    assert re.search(rf"dist/ListBuddy-[\d.]+-{re.escape(arch)}\.dmg\.sha256", with_flag.stdout), with_flag.stdout
    without = _dry_run(tmp_path, "3.14.8")
    assert re.search(r"dist/ListBuddy-[\d.]+\.dmg\.sha256", without.stdout), without.stdout


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


# ── T-097 (QA intento 1): workflow de release ───────────────────────────────

_WORKFLOW = PROJECT_ROOT / ".github" / "workflows" / "release.yml"


def _steps(name_part: str) -> str:
    """Texto del paso del workflow cuyo `name:` contiene name_part (hasta el próximo `- `)."""
    text = _WORKFLOW.read_text(encoding="utf-8")
    m = re.search(rf"- name: [^\n]*{re.escape(name_part)}[^\n]*\n(.*?)(?=\n      - |\n  \w)", text, re.S)
    assert m, name_part
    return m.group(0)


def _step_if_operands(name_part: str) -> list[str]:
    """Operandos del `if:` REAL del paso (no comentarios), partidos por `&&` de nivel superior.
    Falla si la condición usa `||` o paréntesis: ahí un operando ya no garantiza nada por sí solo."""
    step = _steps(name_part)
    ifs = [l for l in step.splitlines() if re.match(r"\s*if:\s*\S", l)]
    assert len(ifs) == 1, f"{name_part}: {len(ifs)} líneas if:"
    cond = ifs[0].split("if:", 1)[1].strip()
    assert "||" not in cond and "(" not in cond, f"{name_part}: condición no conjuntiva: {cond}"
    return [op.strip() for op in cond.split("&&")]


def test_workflow_never_signs_on_pull_request() -> None:
    """D1 (QA D6): PR del mismo repo también recibe secrets; certificado y notarización solo fuera de PR.
    Se exige la guarda como operando de un `&&` real, no como subcadena (un `||` la anularía)."""
    for name in ("Importar certificado", "Guardar credenciales de notarytool"):
        assert "github.event_name != 'pull_request'" in _step_if_operands(name), name


def test_workflow_uploads_source_tarball_from_one_leg_only() -> None:
    """D2: con merge-multiple, el -src.tar.gz de dos patas se pisaría; sale de una sola."""
    text = _WORKFLOW.read_text(encoding="utf-8")
    uploads = re.findall(r"uses: actions/upload-artifact@[^\n]*\n(.*?)(?=\n      - |\n  \w)", text, re.S)
    assert len(uploads) >= 2
    first = uploads[0]
    assert "src.tar.gz" not in first
    assert any("src.tar.gz" in u and "matrix.arch == 'arm64'" in u for u in uploads)
    # El `if:` real del paso del tarball es exactamente esa guarda (un `|| true` lo anularía).
    assert _step_if_operands("tarball de fuentes") == ["matrix.arch == 'arm64'"]


@pytest.mark.skipif(shutil.which("bash") is None, reason="requiere bash")
@pytest.mark.parametrize("dev,notary,expected", [
    ("", "", "Firma: ad-hoc · Notarización: no"),
    ("Developer ID Application: X (T)", "listbuddy", "Firma: Developer ID · Notarización: sí"),
])
def test_workflow_summary_line_renders_cleanly(dev, notary, expected) -> None:
    """D3: la línea de resumen ejecutada en bash (el run: del paso) no mezcla las dos ramas."""
    line = next(l.strip() for l in _steps("Resumen").splitlines() if "Firma:" in l)
    line = line.removeprefix('echo "').removesuffix('"')
    r = subprocess.run(["bash", "-c", f'echo "{line}"'], capture_output=True, text=True,
                       env={"DEVELOPER_ID": dev, "NOTARY_PROFILE": notary, "PATH": "/usr/bin:/bin"})
    assert r.stdout.strip() == expected, r.stdout


# ── T-097 (intento 3, revisión P-2): frontera de secrets en un environment ──

def _job_text(job: str) -> str:
    """Texto del job `job` del workflow real (hasta el próximo job de nivel 2)."""
    text = _WORKFLOW.read_text(encoding="utf-8")
    m = re.search(rf"^  {job}:\n(.*?)(?=^  \w[\w-]*:\n|\Z)", text, re.S | re.M)
    assert m, job
    return m.group(0)


def test_c1_build_environment_release_only_on_tags() -> None:
    """C1: los secrets viven en el environment `release` (regla de tag v*); el job build lo
    referencia solo en tags y en cualquier otro ref cae a `smoke`, sin secrets."""
    build = _job_text("build")
    m = re.search(r"^    environment:\n      name: (\$\{\{.*?\}\})\s*$", build, re.M)
    assert m, "build sin environment con name: por expresión"
    expr = m.group(1)
    assert "startsWith(github.ref, 'refs/tags/v')" in expr
    assert "||" in expr and "'smoke'" in expr and "'release'" in expr
    assert expr.index("'release'") < expr.index("'smoke'")
    # 'release' solo puede salir si la condición de tag es verdadera: nunca fuera de la rama &&.
    assert re.fullmatch(r"\$\{\{ startsWith\(github\.ref, 'refs/tags/v'\) && 'release' \|\| 'smoke' \}\}", expr)


def test_c1_no_secrets_outside_build_job() -> None:
    """C1: ningún `secrets.` fuera del job build (el único que referencia el environment)."""
    def code(t: str) -> str:
        return "\n".join(l for l in t.splitlines() if not l.lstrip().startswith("#"))
    assert "secrets." in code(_job_text("build"))
    assert "environment:" in code(_job_text("build"))   # y ese job es el que lo referencia
    assert "secrets." not in code(_job_text("release"))


def test_c1_docs_use_environment_not_repository_secrets() -> None:
    doc = (PROJECT_ROOT / "docs" / "RELEASE.md").read_text(encoding="utf-8")
    assert "New repository secret" not in doc
    assert "New environment secret" in doc or "Environment secrets" in doc
    for needle in ("Deployment branches and tags", "`v*`", "Required reviewers", "`release`"):
        assert needle in doc, needle


# ── C2: fail-closed en tags ─────────────────────────────────────────────────

def _step_if_conjuncts(name_part: str) -> list[str]:
    """Como _step_if_operands pero admite llamadas `f(...)`: rechaza `||` y parte por `&&`."""
    step = _steps(name_part)
    ifs = [l for l in step.splitlines() if re.match(r"\s*if:\s*\S", l)]
    assert len(ifs) == 1, f"{name_part}: {len(ifs)} líneas if:"
    cond = ifs[0].split("if:", 1)[1].strip()
    assert "||" not in cond and "!(" not in cond, f"{name_part}: condición no conjuntiva: {cond}"
    return [op.strip() for op in cond.split("&&")]


def test_c2_tag_aborts_before_build_without_signing_or_notarization() -> None:
    """C2: en un tag v* sin firma Developer ID o sin notarización el job aborta ANTES de buildear."""
    build = _job_text("build")
    name = "Exigir firma y notarización en tags"
    assert "'refs/tags/v'" in " ".join(_step_if_conjuncts(name))
    assert "startsWith(github.ref, 'refs/tags/v')" in _step_if_conjuncts(name)
    step = _steps(name)
    assert "::error::" in step and "exit 1" in step
    for var in ("SIGNING", "NOTARIZING", "DEVELOPER_ID", "NOTARY_PROFILE"):
        assert var in step, var
    # Orden: después de importar cert y credenciales, antes del build.
    at = build.index(f"- name: {name}")
    assert build.index("- name: Importar certificado") < at
    assert at < build.index("- name: Build, firma, DMG y notarización")
    assert build.index("- name: Guardar credenciales") < at


def test_c2_abort_script_logic() -> None:
    """El run: del paso, ejecutado en bash: aborta si falta cualquiera de las cuatro variables."""
    run = _steps("Exigir firma y notarización en tags").split("run: |\n", 1)[1]
    run = "\n".join(l[10:] if l.startswith(" " * 10) else l for l in run.splitlines())
    ok = {"SIGNING": "true", "NOTARIZING": "true", "DEVELOPER_ID": "Developer ID Application: X",
          "NOTARY_PROFILE": "listbuddy"}
    def go(**over: str):
        env = {"PATH": "/usr/bin:/bin", **ok, **over}
        return subprocess.run(["bash", "-c", run], env=env, capture_output=True, text=True)
    assert go().returncode == 0
    for k in ok:
        r = go(**{k: ""})
        assert r.returncode != 0 and "::error::" in r.stdout, k
    assert go(SIGNING="false").returncode != 0


# ── C3: nada de terceros en el job con contents: write ──────────────────────

def test_c3_release_job_uses_only_first_party_actions_and_gh() -> None:
    job = _job_text("release")
    uses = re.findall(r"^\s*(?:-\s+)?uses:\s*(\S+)", job, re.M)
    assert uses, "el job release debería usar al menos download-artifact"
    assert all(u.startswith("actions/") for u in uses), uses
    assert "softprops" not in job
    cmd = re.search(r"gh release create(?:[^\n]*\\\n)*[^\n]*", job)
    assert cmd, "falta gh release create"
    for flag in ("--draft", "--verify-tag", "--generate-notes", "--title"):
        assert flag in cmd.group(0), flag
    assert "GH_TOKEN: ${{ github.token }}" in job and "GH_REPO: ${{ github.repository }}" in job


def test_c3_release_job_fails_if_an_expected_asset_is_missing() -> None:
    """Sin fail_on_unmatched_files de softprops, el job comprueba los 6 assets a mano."""
    job = _job_text("release")
    for needle in ("-arm64.dmg", "-x86_64.dmg", "-arm64.dmg.sha256", "-x86_64.dmg.sha256",
                   "-src.tar.gz", "-src.tar.gz.sha256"):
        assert needle in job, needle
    step = _steps("Verificar assets")
    assert "exit 1" in step or "::error::" in step


# ── C4: credenciales de notarytool en el keychain temporal ──────────────────

_SIGN_ENV = {"DEVELOPER_ID": "Developer ID Application: X (TEAM)", "NOTARY_PROFILE": "listbuddy",
             "ALLOW_OLD_PYTHON": "1"}


@pytest.mark.skipif(shutil.which("bash") is None, reason="requiere bash")
def test_c4_dry_run_passes_keychain_only_with_notary_keychain(tmp_path) -> None:
    kc = "/tmp/ci/listbuddy-signing.keychain-db"
    with_kc = _dry_run(tmp_path, "3.14.8", NOTARY_KEYCHAIN=kc, **_SIGN_ENV)
    assert with_kc.returncode == 0, with_kc.stderr
    line = next(l for l in with_kc.stdout.splitlines() if "notarytool submit" in l)
    assert f"--keychain {kc}" in line
    without = _dry_run(tmp_path, "3.14.8", **_SIGN_ENV)
    assert without.returncode == 0, without.stderr
    line = next(l for l in without.stdout.splitlines() if "notarytool submit" in l)
    assert "--keychain " not in line.replace("--keychain-profile", "")
    assert "--keychain-profile listbuddy" in line


def test_c4_script_passes_keychain_to_submit_and_log() -> None:
    code = "\n".join(_code_lines(_RELEASE))
    for sub in ("notarytool submit", "notarytool log"):
        row = next(l for l in code.splitlines() if sub in l)
        nxt = code[code.index(row):code.index(row) + 300]
        assert "NOTARY_KC" in nxt, sub
    assert 'NOTARY_KC=(--keychain "$NOTARY_KEYCHAIN")' in code


def test_c4_workflow_stores_profile_in_temp_keychain() -> None:
    step = _steps("Guardar credenciales de notarytool")
    assert re.search(r'store-credentials listbuddy[\s\S]{0,200}?--keychain "\$KEYCHAIN_PATH"', step)
    assert 'echo "NOTARY_KEYCHAIN=$KEYCHAIN_PATH" >> "$GITHUB_ENV"' in step
    assert 'security delete-keychain "$KEYCHAIN_PATH"' in _steps("Limpiar keychain temporal")
