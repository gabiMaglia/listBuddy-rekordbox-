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
    # T-108: PyInstaller viene del lock de build de Windows (con hashes), no de un pin suelto en el .ps1.
    assert not re.search(r"pyinstaller==[\d.]+", ps1)
    assert "requirements-build-windows.txt" in ps1 and "-m PyInstaller" in ps1


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
    assert "--require-hashes" in code and "requirements-build.txt" in code   # PyInstaller viene del lock (T-107)


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
    # `\Z`: el último paso del archivo no tiene otro `- ` detrás (QA T-097 D7 lo encontró).
    m = re.search(rf"- name: [^\n]*{re.escape(name_part)}[^\n]*\n(.*?)(?=\n      - |\n  \w|\Z)", text, re.S)
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
    assert at < build.index("- name: Firma, DMG y notarización")
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


_EXPECTED_ASSETS = ("ListBuddy-${VERSION}-arm64.dmg", "ListBuddy-${VERSION}-arm64.dmg.sha256",
                    "ListBuddy-${VERSION}-x86_64.dmg", "ListBuddy-${VERSION}-x86_64.dmg.sha256",
                    "listbuddy-${VERSION}-src.tar.gz", "listbuddy-${VERSION}-src.tar.gz.sha256")


def _step_run(name_part: str) -> str:
    """Bloque `run: |` real del paso (sin el `run:`), des-indentado."""
    step = _steps(name_part)
    m = re.search(r"^( *)run: \|\n((?:\1 +[^\n]*\n|\n)+)", step + "\n", re.M)
    assert m, f"{name_part}: sin bloque run: |"
    indent = len(m.group(1)) + 2
    return "".join(l[indent:] + "\n" if len(l) > indent else "\n" for l in m.group(2).splitlines())


def test_c3_release_job_lists_all_six_assets_in_check_and_in_gh_release() -> None:
    """QA T-097 D7: cada asset, con su nombre completo, está en el paso de verificación Y en `gh release create`
    (una subcadena suelta en el job no alcanza: sacar un DMG del create pasaba inadvertido)."""
    check, create = _step_run("Verificar assets"), _step_run("Crear release")

    def has_token(text: str, tok: str) -> bool:
        # Palabra entera: «…-arm64.dmg» NO debe darse por presente porque exista «…-arm64.dmg.sha256».
        return re.search(rf'(?<![\w./]){re.escape(tok)}(?![\w.])', text) is not None

    for asset in _EXPECTED_ASSETS:
        assert has_token(check, asset), f"falta en la verificación: {asset}"
        assert has_token(create, f"assets/{asset}"), f"falta en gh release create: {asset}"
    assert "gh release create" in create and "--verify-tag" in create and "--draft" in create


@pytest.mark.skipif(shutil.which("bash") is None, reason="requiere bash")
@pytest.mark.parametrize("missing", list(range(6)))
def test_c3_asset_check_step_really_fails_when_one_is_missing(tmp_path, missing) -> None:
    """QA T-097 D7: el `run:` del paso se ejecuta en bash: con los 6 assets pasa; sin cualquiera, exit 1 y lo nombra."""
    script = _step_run("Verificar assets")
    version = "9.9.9"
    names = [a.replace("${VERSION}", version) for a in _EXPECTED_ASSETS]
    (tmp_path / "assets").mkdir()
    for n in names:
        (tmp_path / "assets" / n).write_bytes(b"x")
    env = {"PATH": "/usr/bin:/bin", "GITHUB_REF_NAME": f"v{version}"}
    ok = subprocess.run(["bash", "-e", "-c", script], cwd=tmp_path, env=env, capture_output=True, text=True)
    assert ok.returncode == 0, ok.stdout + ok.stderr
    (tmp_path / "assets" / names[missing]).unlink()
    r = subprocess.run(["bash", "-e", "-c", script], cwd=tmp_path, env=env, capture_output=True, text=True)
    assert r.returncode == 1 and names[missing] in r.stdout + r.stderr, r.stdout + r.stderr


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


def test_windows_lock_has_colorama_and_build_script_stops_on_pip_failure() -> None:
    """Verifier T-092 D1: el lock se compila en macOS; pytest exige colorama solo en win32.
    Sin el pin explícito, `pip install --require-hashes` falla en Windows («must have their versions pinned»),
    y el .ps1 seguía igual porque $ErrorActionPreference no corta comandos nativos."""
    for lock in ("requirements-dev.txt",):
        text = (PROJECT_ROOT / lock).read_text(encoding="utf-8")
        assert re.search(r"^colorama==[\d.]+ \\\n    --hash=sha256:[0-9a-f]{64}", text, re.M), f"{lock}: sin colorama pineado con hash"
    ps1 = (PROJECT_ROOT / "scripts" / "build_windows.ps1").read_text(encoding="utf-8")
    installs = [l for l in ps1.splitlines() if re.match(r"\s*& \$py -m pip install", l)]
    assert len(installs) == 2
    assert ps1.count("Assert-Success") >= len(installs), "cada pip install debe cortar el script si falla"


def test_workflow_hygiene_no_set_x_cleanup_always_summary_without_secrets() -> None:
    """Verifier T-097 (observaciones): sin `set -x` en ningún `run:` (los secrets irían al log), la limpieza del
    keychain corre siempre (`always()`), y el resumen no imprime variables de secrets."""
    text = _WORKFLOW.read_text(encoding="utf-8")
    # Cualquier forma de xtrace: `set -x`, `set -ex`, `set -euxo`, `set -o xtrace`, `bash -x`.
    assert not re.search(r"\bset\s+-[a-zA-Z]*x|\bset\s+-o\s+xtrace|\bbash\s+-x\b", text)
    # El job con secrets no restaura cachés de pip (un run de tag restaura la caché de la rama default).
    assert "cache:" not in text and "cache-dependency-path" not in text
    cleanup_if = [l for l in _steps("Limpiar keychain").splitlines() if re.match(r"\s*if:\s*\S", l)]
    assert len(cleanup_if) == 1 and cleanup_if[0].split("if:", 1)[1].strip().startswith("always()")
    summary = _step_run("Resumen")
    for secret in ("MACOS_CERT_P12_BASE64", "MACOS_CERT_PASSWORD", "NOTARY_KEY_ID", "NOTARY_ISSUER_ID", "NOTARY_KEY_P8_BASE64"):
        assert secret not in summary, secret


def test_release_docs_require_tag_ruleset_with_restrict_updates() -> None:
    """Verifier T-097 D1: el ruleset de tags es parte de la frontera (ADR-005 §1), no una recomendación,
    y debe bloquear actualizaciones (mover un tag v* existente a otro commit) además de creaciones."""
    doc = (PROJECT_ROOT / "docs" / "RELEASE.md").read_text(encoding="utf-8")
    # El paso numerado del ruleset, entero (hasta el próximo paso o párrafo).
    m = re.search(r"^\d+\. \*\*Obligatorio[^\n]*New tag ruleset\*\*(?:\n(?!\d+\. |\n)[^\n]*)*", doc, re.M)
    assert m, "el paso del ruleset tiene que ser «Obligatorio» y nombrar New tag ruleset"
    step = m.group(0)
    # La lista de reglas exigidas es la frase ANTES de la explicación («Sin *Restrict updates*…»):
    rules = step.split("Sin *Restrict", 1)[0]
    assert re.search(r"con \*Restrict creations\*, \*Restrict updates\* y \*Restrict deletions\*", rules), rules
    assert "sin bypass salvo" in rules and "mantenedor" in rules
    assert "Opcional" not in step and "Recomendado" not in step and "Write" not in rules
    for asset in ("listbuddy-<v>-src.tar.gz", "listbuddy-1.0.0-src.tar.gz"):
        assert asset in doc, asset
    assert "`release.yml`, `release_mac.sh`" in doc



# ── T-103: verificación de minos contra el mínimo 14.4 ──────────────────────

_KNOWN_BINDINGS = (
    "QtCore", "QtGui", "QtWidgets", "QtSvg", "QtNetwork", "QtDBus", "QtMultimedia",
    "QtMultimediaWidgets", "QtConcurrent",
)


def _minos_snippet() -> str:
    text = _RELEASE.read_text(encoding="utf-8")
    return text.split("# >>> minos-check", 1)[1].split("# <<< minos-check", 1)[0]


def test_minos_warning_tells_the_truth_static() -> None:
    text = _RELEASE.read_text(encoding="utf-8")
    assert "26.0" in text and "14.8" in text
    assert "15.0" not in text and "53 módulos" not in text
    for name in _KNOWN_BINDINGS + ("Shiboken.abi3.so", "libshiboken6.abi3.6.12.dylib", "libpyside6.abi3.6.12.dylib"):
        assert name in _minos_snippet(), name


def _run_minos(tmp_path, files: dict[str, str]):
    """Corre solo el tramo de minos con otool/file falsos: el minos es el contenido del archivo."""
    app = tmp_path / "List Buddy.app"
    fw = app / "Contents" / "Frameworks"
    fw.mkdir(parents=True)
    (app / "Contents" / "Info.plist").write_bytes(plistlib.dumps({"LSMinimumSystemVersion": "14.4"}))
    for rel, minos in files.items():
        (fw / rel).parent.mkdir(parents=True, exist_ok=True)
        (fw / rel).write_text(minos)
        (fw / rel).chmod(0o755)
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    (bin_dir / "file").write_text("#!/bin/sh\necho 'Mach-O 64-bit bundle x86_64'\n")
    (bin_dir / "otool").write_text(
        '#!/bin/sh\nprintf "Load command 1\\n      cmd LC_BUILD_VERSION\\n    minos %s\\n" "$(cat "$2")"\n')
    for f in bin_dir.iterdir():
        f.chmod(0o755)
    env = {"PATH": f"{bin_dir}:/usr/bin:/bin:/usr/libexec", "APP": str(app)}
    return subprocess.run(["bash", "-c", _minos_snippet()], capture_output=True, text=True, env=env)


@pytest.mark.skipif(sys.platform != "darwin", reason="PlistBuddy es de macOS")
def test_minos_known_bindings_warn_and_list_files(tmp_path) -> None:
    files = {f"PySide6/{n}.abi3.so": "26.0" for n in _KNOWN_BINDINGS}
    files["shiboken6/Shiboken.abi3.so"] = "26.0"
    files["shiboken6/libshiboken6.abi3.6.12.dylib"] = "26.0"
    files["PySide6/libpyside6.abi3.6.12.dylib"] = "26.0"
    files["libok.dylib"] = "14.0"
    r = _run_minos(tmp_path, files)
    assert r.returncode == 0, r.stderr
    assert "AVISO" in r.stderr and "26.0" in r.stderr and "14.8" in r.stderr and "12" in r.stderr
    assert "Shiboken.abi3.so" in r.stderr and "libok.dylib" not in r.stderr


@pytest.mark.skipif(sys.platform != "darwin", reason="PlistBuddy es de macOS")
def test_minos_unknown_macho_above_minimum_aborts(tmp_path) -> None:
    r = _run_minos(tmp_path, {"PySide6/QtCore.abi3.so": "26.0", "libnuevo.dylib": "15.0"})
    assert r.returncode == 1
    assert "libnuevo.dylib" in r.stderr


# ── T-107: release/CI endurecido ────────────────────────────────────────────

def _snippet(name: str) -> str:
    """Tramo del script entre `# >>> name` y `# <<< name` (se ejecuta aparte, con binarios falsos)."""
    text = _RELEASE.read_text(encoding="utf-8")
    assert f"# >>> {name}" in text and f"# <<< {name}" in text, name
    return text.split(f"# >>> {name}", 1)[1].split(f"# <<< {name}", 1)[0]


def _fake_bin(tmp_path, **scripts: str):
    """Directorio de binarios falsos para el PATH; cada valor es el cuerpo sh del comando."""
    bin_dir = tmp_path / "fakebin"
    bin_dir.mkdir(exist_ok=True)
    for name, body in scripts.items():
        f = bin_dir / name
        f.write_text("#!/bin/sh\n" + body + "\n")
        f.chmod(0o755)
    return bin_dir


def _run_snippet(tmp_path, name: str, call: str, bin_dir, *, system_path: bool = True, **env):
    script = f"set -euo pipefail\n{_snippet(name)}\n{call}\n"
    e = {"PATH": f"{bin_dir}:/usr/bin:/bin" if system_path else str(bin_dir), **env}
    return subprocess.run(["/bin/bash", "-c", script], capture_output=True, text=True, env=e, cwd=tmp_path, timeout=60)


# xcrun falso: cuenta las llamadas a `stapler staple` y falla las primeras $FAILS veces.
_FAKE_XCRUN = (
    'echo "$*" >> "$CALLS"\n'
    'if [ "$2" = staple ]; then\n'
    '  n=$(grep -c "stapler staple" "$CALLS")\n'
    '  [ "$n" -gt "$FAILS" ] || { echo "Error 65 CloudKit" >&2; exit 65; }\n'
    'fi\n'
    'exit 0'
)


@pytest.mark.skipif(shutil.which("bash") is None, reason="requiere bash")
@pytest.mark.parametrize("fails,ok", [(0, True), (2, True), (5, True), (6, False), (7, False)])
def test_t107_staple_retries_then_validates_or_aborts(tmp_path, fails, ok) -> None:
    """APP-23: `stapler staple` se reintenta (6 intentos); 2 fallos → OK + validate; 7 fallos → exit 1."""
    calls = tmp_path / "calls.txt"
    bin_dir = _fake_bin(tmp_path, xcrun=_FAKE_XCRUN)
    r = _run_snippet(tmp_path, "staple-retry", 'staple_with_retry "/x/List Buddy.app"', bin_dir,
                     CALLS=str(calls), FAILS=str(fails), STAPLE_DELAY="0")
    lines = calls.read_text().splitlines()
    staples = [l for l in lines if "stapler staple" in l]
    assert (r.returncode == 0) is ok, r.stdout + r.stderr
    if ok:
        assert len(staples) == fails + 1
        assert lines[-1] == "stapler validate /x/List Buddy.app"
    else:
        assert r.returncode == 1 and len(staples) == 6
        assert not any("validate" in l for l in lines)
        assert "notariz" in r.stderr and "List Buddy.app" in r.stderr


def test_t107_staple_used_for_app_and_dmg_without_bare_calls() -> None:
    outside = _RELEASE.read_text(encoding="utf-8").split("# <<< staple-retry", 1)[1]
    assert re.findall(r"^\s*xcrun stapler (?:staple|validate)", outside, re.M) == []
    assert 'staple_with_retry "$APP"' in outside and 'staple_with_retry "$DMG"' in outside


def test_t107_notary_logs_carry_arch_suffix_and_travel_as_evidence() -> None:
    """APP-25: notary-{app,dmg}-<v><arch>.json no se pisan entre patas y salen como artefacto de evidencia."""
    code = "\n".join(_code_lines(_RELEASE))
    names = re.findall(r"dist/notary-[^\s\"']+\.json", code)
    assert len(names) == 2 and all("${ARCH_SUFFIX}" in n for n in names), names
    text = _WORKFLOW.read_text(encoding="utf-8")
    uploads = re.findall(r"uses: actions/upload-artifact@[^\n]*\n(.*?)(?=\n      - |\n  \w)", text, re.S)
    notary = [u for u in uploads if "notary-" in u]
    assert len(notary) == 1
    assert "${{ matrix.arch }}" in notary[0] and "notary" in notary[0].split("path:")[0]
    assert "if-no-files-found: ignore" in notary[0]   # ad-hoc no genera logs
    assert all("notary-" not in u for u in uploads if u is not notary[0])
    step = _steps("evidencia de notarización")
    assert re.search(r"^\s*if:\s*always\(\)", step, re.M)   # también si el notary rechaza
    # nunca entra al GitHub Release: los assets se listan uno por uno
    assert "notary" not in _step_run("Crear release") and "notary" not in _step_run("Verificar assets")


@pytest.mark.skipif(shutil.which("bash") is None, reason="requiere bash")
@pytest.mark.parametrize("case,macos,policy,rc,expect_rc,expect_text", [
    ("ok", "14.8.8", "exit 0", None, 0, ""),
    ("falla", "15.1", 'echo "ticket" >&2; exit 1', None, 1, "syspolicy_check"),
    ("sin_binario", "15.1", None, None, 0, "AVISO"),
    ("macos13", "13.7", "exit 1", None, 0, "AVISO"),
])
def test_t107_syspolicy_check_distribution(tmp_path, case, macos, policy, rc, expect_rc, expect_text) -> None:
    """APP-27: `syspolicy_check distribution "$APP"` tras el staple; sin binario o macOS < 14 avisa y sigue."""
    fakes = {"sw_vers": f'echo "{macos}"'}
    if policy is not None:
        fakes["syspolicy_check"] = f'echo "$*" >> "$CALLS"\n{policy}'
    bin_dir = _fake_bin(tmp_path, **fakes)
    calls = tmp_path / "calls.txt"
    # Sin /usr/bin en el PATH: ahí vive el syspolicy_check real y «sin_binario» no probaría nada.
    r = _run_snippet(tmp_path, "syspolicy", 'syspolicy_check_app "/x/List Buddy.app"', bin_dir,
                     system_path=False, CALLS=str(calls))
    assert r.returncode == expect_rc, r.stdout + r.stderr
    assert expect_text in r.stdout + r.stderr
    if case in ("ok", "falla"):
        assert calls.read_text().strip() == "distribution /x/List Buddy.app"
    else:
        assert not calls.exists()


def test_t107_syspolicy_runs_after_app_staple_and_before_dmg() -> None:
    text = _RELEASE.read_text(encoding="utf-8").split("# <<< syspolicy", 1)[1]
    assert text.index('staple_with_retry "$APP"') < text.index('syspolicy_check_app "$APP"') < text.index("hdiutil create")


def test_t107_release_docs_cover_min_macos_bindings_warning_and_first_release_order() -> None:
    """APP-28: RELEASE.md explica el mínimo 14.4, el AVISO de los 12 bindings y el orden del primer release."""
    doc = (PROJECT_ROOT / "docs" / "RELEASE.md").read_text(encoding="utf-8")
    section = doc.split("## Requisitos y avisos del log", 1)[1].split("\n## ", 1)[0]
    for needle in ("macOS 14.4", "12 bindings", "minos 26.0", "14.8", "AVISO"):
        assert needle in section, needle
    order = doc.split("## Orden del primer release", 1)[1].split("\n## ", 1)[0]
    positions = [order.index(k) for k in ("D-14", "Developer ID Application", "API key", "environment `release`",
                                          "ruleset", "smoke", "git tag", "Gatekeeper", "Publish release")]
    assert positions == sorted(positions)
    for needle in ("stapler staple", "reintenta", "syspolicy_check", "notary-app-", "--build-only"):
        assert needle in doc, needle


def _mk_dist(tmp_path, names: list[str]):
    dist = tmp_path / "dist"
    dist.mkdir()
    for n in names:
        p = dist / n
        if n.endswith(".app") or n == "List Buddy":
            (p / "Contents").mkdir(parents=True)
            (p / "Contents" / "x").write_text("x")
        else:
            p.write_text("x")
    return dist


_OURS = ["List Buddy.app", "List Buddy", "listBuddy.app", "listBuddy", "listBuddy-1.0.dmg", "ListBuddy-1.0.0-arm64.dmg",
         "ListBuddy-1.0.0-arm64.dmg.sha256", "listbuddy-1.0.0-src.tar.gz", "notary-app-1.0.0.json", ".DS_Store"]


@pytest.mark.skipif(shutil.which("bash") is None, reason="requiere bash")
@pytest.mark.parametrize("skip_build,kept", [(0, []), (1, ["List Buddy.app"])])
def test_t107_clean_dist_removes_our_old_artifacts(tmp_path, skip_build, kept) -> None:
    """TEC-27: los artefactos viejos propios se borran; con --skip-build el .app recién buildeado se conserva."""
    dist = _mk_dist(tmp_path, _OURS)
    r = _run_snippet(tmp_path, "clean-dist", "clean_dist", _fake_bin(tmp_path), SKIP_BUILD=str(skip_build),
                     DRY_RUN="0", APP="dist/List Buddy.app")
    assert r.returncode == 0, r.stderr
    assert sorted(p.name for p in dist.iterdir()) == kept


@pytest.mark.skipif(shutil.which("bash") is None, reason="requiere bash")
def test_t107_clean_dist_aborts_on_foreign_files_and_deletes_nothing(tmp_path) -> None:
    dist = _mk_dist(tmp_path, _OURS + ["tesis-final.pdf"])
    r = _run_snippet(tmp_path, "clean-dist", "clean_dist", _fake_bin(tmp_path), SKIP_BUILD="0", DRY_RUN="0",
                     APP="dist/List Buddy.app")
    assert r.returncode == 1 and "tesis-final.pdf" in r.stderr
    assert len(list(dist.iterdir())) == len(_OURS) + 1


@pytest.mark.skipif(shutil.which("bash") is None, reason="requiere bash")
def test_t107_clean_dist_dry_run_lists_without_touching(tmp_path) -> None:
    dist = _mk_dist(tmp_path, _OURS + ["tesis-final.pdf"])
    r = _run_snippet(tmp_path, "clean-dist", "clean_dist", _fake_bin(tmp_path), SKIP_BUILD="0", DRY_RUN="1",
                     APP="dist/List Buddy.app")
    assert r.returncode == 0
    out = r.stdout + r.stderr
    assert "[dry-run]" in out and "ListBuddy-1.0.0-arm64.dmg" in out and "tesis-final.pdf" in out
    assert len(list(dist.iterdir())) == len(_OURS) + 1


@pytest.mark.skipif(shutil.which("bash") is None, reason="requiere bash")
def test_t107_clean_dist_without_dist_dir_is_noop(tmp_path) -> None:
    r = _run_snippet(tmp_path, "clean-dist", "clean_dist", _fake_bin(tmp_path), SKIP_BUILD="0", DRY_RUN="0",
                     APP="dist/List Buddy.app")
    assert r.returncode == 0 and not (tmp_path / "dist").exists()


# ── T-107 SEC-17/SEC-23: toolchain de build con hashes y build antes de la clave ──

_BUILD_LOCK = PROJECT_ROOT / "requirements-build.txt"


def test_t107_build_lock_is_fully_hashed_and_pins_pyinstaller_6_22() -> None:
    from _reqs import pinned, unhashed
    assert (PROJECT_ROOT / "requirements-build.in").is_file()
    assert unhashed(_BUILD_LOCK) == []
    locked = pinned(_BUILD_LOCK)
    assert re.fullmatch(r"6\.22\.\d+", locked["pyinstaller"])
    # lo que PyInstaller ejecuta en el build y el propio pip van pineados con hash (sin «unsafe» suelto)
    for dep in ("pyinstaller-hooks-contrib", "setuptools", "macholib", "altgraph", "packaging", "pip"):
        assert dep in locked, dep
    text = _BUILD_LOCK.read_text(encoding="utf-8")
    assert "pip-compile" in text and "--generate-hashes" in text


def test_t107_release_script_installs_build_toolchain_only_with_require_hashes() -> None:
    code = "\n".join(_code_lines(_RELEASE))
    installs = [l for l in code.splitlines() if "pip install" in l and "echo" not in l]
    assert installs and all("--require-hashes" in l for l in installs), installs
    assert any("-r requirements-build.txt" in l for l in installs)
    assert any("-r requirements.txt" in l for l in installs)
    assert "PYINSTALLER_PIN" not in code and "pyinstaller==" not in code.lower()


@pytest.mark.skipif(shutil.which("bash") is None, reason="requiere bash")
def test_t107_build_only_and_skip_build_are_exclusive_and_planned(tmp_path) -> None:
    r = subprocess.run(["bash", str(_RELEASE), "--build-only", "--skip-build"], cwd=PROJECT_ROOT,
                       env=_env(tmp_path, "3.14.8"), capture_output=True, text=True, timeout=60)
    assert r.returncode == 2 and "--build-only" in r.stderr
    r = subprocess.run(["bash", str(_RELEASE), "--dry-run", "--build-only"], cwd=PROJECT_ROOT,
                       env=_env(tmp_path, "3.14.8"), capture_output=True, text=True, timeout=60)
    assert r.returncode == 0, r.stderr
    assert "requirements-build.txt" in r.stdout and "--build-only" in r.stdout
    assert "codesign" not in r.stdout and "notarytool" not in r.stdout and "hdiutil" not in r.stdout


def test_t107_build_only_exits_before_any_signing() -> None:
    code = "\n".join(_code_lines(_RELEASE))
    body = code.split("# plutil", 1)[0] + code  # el exit va entre el minos-check y la firma
    text = _RELEASE.read_text(encoding="utf-8")
    assert text.index("# <<< minos-check") < text.rindex('if [ "$BUILD_ONLY" = 1 ]') < text.index("# ── Firma inside-out")
    assert "BUILD_ONLY" in body


def test_t107_workflow_builds_before_certificate_in_two_phases() -> None:
    """D-a / SEC-17: pip y PyInstaller nunca corren con la clave de firma disponible."""
    build = _job_text("build")
    order = [m.group(1) for m in re.finditer(r"^      - name: (.+)$", build, re.M)]
    def at(part: str) -> int:
        idx = [i for i, n in enumerate(order) if part in n]
        assert len(idx) == 1, (part, order)
        return idx[0]
    phase1, cert, creds, strict, phase2 = (at("Build sin credenciales"), at("Importar certificado"),
                                           at("Guardar credenciales"), at("Exigir firma y notarización"),
                                           at("Firma, DMG y notarización"))
    assert phase1 < cert < creds < strict < phase2
    assert at("Exigir secrets de firma en tags") < phase1       # el fail-closed barato sigue antes del build
    run1, run2 = _steps("Build sin credenciales"), _steps("Firma, DMG y notarización")
    assert re.search(r"release_mac\.sh --build-only --arch-suffix", run1)
    assert re.search(r"release_mac\.sh --skip-build --arch-suffix", run2)
    # Nada de secrets, identidad ni keychain en el entorno de la fase 1
    phase1_step = _steps("Build sin credenciales")
    for forbidden in ("secrets.", "DEVELOPER_ID", "NOTARY_", "KEYCHAIN"):
        assert forbidden not in phase1_step, forbidden
    # y los secrets solo se referencian en pasos posteriores al build
    first_secret = build.index("secrets.MACOS_CERT_P12_BASE64 }}\n          MACOS")
    assert first_secret > build.index("- name: Build sin credenciales")
    assert "requirements-build.txt" in _WORKFLOW.read_text(encoding="utf-8").split("pull_request:", 1)[1].split("permissions:", 1)[0]



def test_t107_claude_md_documents_build_lock_regeneration() -> None:
    doc = (PROJECT_ROOT / "CLAUDE.md").read_text(encoding="utf-8")
    assert "pip-compile --generate-hashes --allow-unsafe --strip-extras --output-file=requirements-build.txt requirements-build.in" in doc
    assert "PyInstaller (`==6.20.0`) se instala aparte" not in doc
    assert "--build-only" in doc


# ── T-108: lock de build para Windows (SEC-20) ──────────────────────────────

_WIN_LOCK = PROJECT_ROOT / "requirements-build-windows.txt"
_WIN_IN = PROJECT_ROOT / "requirements-build-windows.in"


def test_t108_windows_build_lock_has_windows_only_deps_and_hashes() -> None:
    """PyInstaller exige pefile y pywin32-ctypes solo en win32; pip-compile corre en macOS y no los resuelve
    solo, así que van explícitos en el .in. Sin ellos `--require-hashes` instala un PyInstaller que no arranca."""
    from _reqs import pinned, unhashed
    assert _WIN_IN.exists() and _WIN_LOCK.exists()
    pins = pinned(_WIN_LOCK)
    assert pins["pyinstaller"] == "6.22.3"
    assert {"pefile", "pywin32-ctypes", "altgraph", "pyinstaller-hooks-contrib", "setuptools", "pip"} <= set(pins)
    assert unhashed(_WIN_LOCK) == []
    assert pinned(PROJECT_ROOT / "requirements-build.txt")["pyinstaller"] == pins["pyinstaller"]
    in_names = {m.group(1).lower() for l in _WIN_IN.read_text(encoding="utf-8").splitlines()
                if (m := re.match(r"^([A-Za-z0-9][A-Za-z0-9._-]*)", l))}
    assert {"pyinstaller", "pefile", "pywin32-ctypes", "pip"} <= in_names


def test_t108_claude_md_documents_windows_lock_regeneration() -> None:
    doc = (PROJECT_ROOT / "CLAUDE.md").read_text(encoding="utf-8")
    section = doc.split("## Empaquetado — Windows", 1)[1].split("\n## ", 1)[0]
    for needle in ("pip-compile --generate-hashes --allow-unsafe --strip-extras",
                   "requirements-build-windows.in", "requirements-build-windows.txt",
                   "pefile", "pywin32-ctypes", "--platform win_amd64"):
        assert needle in section, needle


# ── T-108: check_bundle compartido entre macOS y Windows (LEG-26) ───────────

_FORBIDDEN = PROJECT_ROOT / "scripts" / "bundle_forbidden.txt"
_CHECK_PS1 = PROJECT_ROOT / "scripts" / "check_bundle.ps1"


def _forbidden_patterns() -> list[str]:
    lines = [l.strip() for l in _FORBIDDEN.read_text(encoding="utf-8").splitlines()]
    return [l for l in lines if l and not l.startswith("#")]


def test_t108_forbidden_list_covers_the_audit_names() -> None:
    pats = {p.lower() for p in _forbidden_patterns()}
    for exact in ("pil", "pillow*", "pyqt6*", ".rbe_settings.ini"):        # nombres exactos: `pil` suelto no puede pasar por «pillow»
        assert exact in pats, exact
    low = " ".join(sorted(pats))
    for needle in ("pyrekordbox", "sqlcipher", "sqlalchemy", "qtpdf", "qtwebengine", "qtquick", "qtqml", "virtualkeyboard"):
        assert needle in low, needle


def _plant(tmp_path, name: str):
    root = tmp_path / "listBuddy" / "_internal"
    root.mkdir(parents=True)
    (root / "QtCore.dll").write_bytes(b"")
    (root / "PySide6").mkdir()
    (root / "pillar.txt").write_text("x")           # no debe confundirse con Pillow/PIL
    if name:
        (root / name).mkdir()
    return tmp_path / "listBuddy"


@pytest.mark.skipif(shutil.which("bash") is None, reason="requiere bash")
def test_t108_check_bundle_sh_rejects_every_pattern_of_the_shared_list(tmp_path) -> None:
    """Enumera la lista compartida (no ejemplos a mano): cada patrón, plantado como nombre, debe cortar el chequeo."""
    missed = []
    for i, pat in enumerate(_forbidden_patterns()):
        bundle = _plant(tmp_path / str(i), pat.replace("*", "x"))
        r = subprocess.run(["bash", str(_CHECK), str(bundle)], capture_output=True, text=True)
        if r.returncode != 1:
            missed.append(pat)
    assert missed == []


@pytest.mark.skipif(shutil.which("bash") is None, reason="requiere bash")
def test_t108_check_bundle_sh_accepts_a_clean_bundle_and_reads_the_shared_file(tmp_path) -> None:
    r = subprocess.run(["bash", str(_CHECK), str(_plant(tmp_path, ""))], capture_output=True, text=True)
    assert r.returncode == 0, r.stdout + r.stderr
    code = "\n".join(_code_lines(_CHECK))
    assert "bundle_forbidden.txt" in code
    assert "QtPdf" not in code and "sqlalchemy" not in code      # la lista ya no está duplicada a mano


def test_t108_check_bundle_ps1_uses_the_shared_list_and_fails_closed() -> None:
    code = "\n".join(l for l in _CHECK_PS1.read_text(encoding="utf-8").splitlines() if not l.lstrip().startswith("#"))
    assert "bundle_forbidden.txt" in code
    assert "Get-ChildItem" in code and "-Recurse" in code and "-Force" in code   # -Force: ocultos como .rbe_settings.ini
    assert "-like" in code                                                        # case-insensitive, como -iname
    assert re.search(r"exit 2", code) and re.search(r"exit 1", code)
    assert r"dist\listBuddy" in code
    assert ".Trim()" in code                                # CRLF de checkout con autocrlf
    assert "Set-StrictMode" in code and "$ErrorActionPreference" in code


# ── T-108: build_windows.ps1 con integridad (SEC-20, LEG-26) ────────────────

_BUILD_PS1 = PROJECT_ROOT / "scripts" / "build_windows.ps1"


def _ps1_code() -> list[str]:
    return [l for l in _BUILD_PS1.read_text(encoding="utf-8").splitlines()
            if l.strip() and not l.lstrip().startswith("#")]


def _first(lines: list[str], pattern: str) -> int:
    for i, l in enumerate(lines):
        if re.search(pattern, l):
            return i
    raise AssertionError(f"no hay línea con /{pattern}/")


def test_t108_ps1_uses_a_clean_build_venv_never_the_dev_venv() -> None:
    code = _ps1_code()
    text = "\n".join(code)
    assert ".venv-build" in text
    assert not re.search(r'\.venv(?!-build)', text), "el .ps1 no puede tocar .venv (arrastra Pillow/PyQt6, LEG-26)"
    # se borra antes de crear: un venv viejo no se reutiliza
    assert _first(code, r"Remove-Item.*\$venv") < _first(code, r"-m venv")
    assert _first(code, r'^\$venv = Join-Path \$ROOT "\.venv-build"$') < _first(code, r"-m venv")
    # $py sale SOLO del venv y, después de crearlo, el intérprete del sistema ($Python) no vuelve a aparecer (V1 verifier)
    assert [l for l in code if re.match(r"\$py = ", l)] == [r'$py = Join-Path $venv "Scripts\python.exe"']
    created = _first(code, r"^& \$Python -m venv \$venv$")
    assert [l for l in code if re.match(r"&\s+\$Python -m venv", l)] == [code[created]]
    after = code[created + 1:]
    assert [l for l in after if re.search(r"\$Python\b", l)] == []
    natives = [l for l in after if re.search(r"(^|=\s*)&\s+[\$\(]", l)]
    assert natives and all(l.startswith("& $py ") or l.startswith('& (Join-Path $PSScriptRoot "check_bundle.ps1")')
                           for l in natives), natives


def test_t108_ps1_requires_python_3_14_8_and_explains_install() -> None:
    text = "\n".join(_ps1_code())
    assert '[version]"3.14.8"' in text
    assert re.search(r"\$found -lt \$MinPython", text)
    assert "python.org" in text and "winget install" in text and "-Python" in text
    assert "ALLOW_OLD" not in text.upper()        # sin override: SEC-20 pide que el release no arranque con un expat viejo


def test_t108_ps1_installs_only_from_hashed_locks() -> None:
    code = _ps1_code()
    installs = [l for l in code if l.startswith("&") and "pip install" in l]
    assert len(installs) == 2, installs
    for l in installs:
        assert "--require-hashes" in l and re.search(r"-r \(Join-Path \$ROOT \"requirements", l), l
    assert any("requirements.txt" in l for l in installs)
    assert any("requirements-build-windows.txt" in l for l in installs)
    assert not any(re.search(r"pip install\s+pyinstaller", l, re.I) for l in code)
    assert all("-m pip" in l for l in installs)          # `pip.exe install --upgrade pip` no puede reemplazarse a sí mismo


def test_t108_ps1_checks_exit_code_after_every_native_call() -> None:
    code = _ps1_code()
    body = "\n".join(code)
    m = re.search(r"function Assert-Success.*?\n\}", body, re.S)
    assert m and "$LASTEXITCODE -ne 0" in m.group(0) and "exit 1" in m.group(0)
    native = [i for i, l in enumerate(code) if re.search(r"(^|=\s*)&\s+[\$\(]", l)]
    assert len(native) >= 6, "venv, 2 pip, PyInstaller, check_bundle, versión de Python"
    unchecked = [code[i] for i in native if "Assert-Success" not in code[i + 1]]
    assert unchecked == []


def test_t108_ps1_step_order_gate_build_check_zip_hash() -> None:
    code = _ps1_code()
    order = [r"-lt \$MinPython", r"A DEFINIR POR EL PO", r"-m venv", r"pip install.*requirements\.txt",
             r"pip install.*requirements-build-windows", r"-m PyInstaller", r"check_bundle\.ps1",
             r"CreateFromDirectory", r"Get-FileHash"]
    idx = [_first(code, p) for p in order]
    assert idx == sorted(idx) and len(set(idx)) == len(idx), idx


def test_t108_ps1_gate_d14_covers_the_same_files_as_the_release_gate_test() -> None:
    from test_release_gate import _FILES, _MARKER
    text = "\n".join(_ps1_code())
    for name in _FILES:
        assert f'"{name}"' in text, name
    assert _MARKER in text and "-SimpleMatch" in text and "exit 1" in text
    # la condición REAL (V2 verifier): cualquier marcador pendiente corta; `-gt 99` dejaría pasar hasta 99 archivos
    code = _ps1_code()
    cond = _first(code, r"^if \(\$pending\.Count -gt 0\) \{$")
    assert re.search(r"exit 1", "\n".join(code[cond:cond + 6]))
    assert [l for l in code if re.search(r"\$pending\.Count", l)] == [code[cond]]
    assert re.search(r'\$pending = @\(\$gateFiles \| Where-Object \{', "\n".join(code))
    assert re.search(r"Select-String -LiteralPath \(Join-Path \$ROOT \$_\) -SimpleMatch \"\[A DEFINIR POR EL PO\" -Quiet", text)


def test_t108_ps1_builds_with_pyinstaller_module_and_names_the_artifacts() -> None:
    text = "\n".join(_ps1_code())
    assert "-m PyInstaller rb_exporter.spec --noconfirm --clean" in text
    assert r"dist\listBuddy" in text or '"dist"' in text
    assert "listBuddy-$version-win64.zip" in text
    assert "_APP_VERSION" in text                      # la versión sale de ui.py, como en release_mac.sh
    assert "Compress-Archive" not in text              # entradas con \ en PS 5.1: se usa ZipFile y se reabre para verificar


def test_t108_ps1_writes_sha256_in_shasum_format_without_bom() -> None:
    text = "\n".join(_ps1_code())
    assert "Get-FileHash" in text and "-Algorithm SHA256" in text and ".ToLower()" in text
    assert '"$hash *$(Split-Path -Leaf $zip)' in text
    assert "UTF8Encoding($false)" in text and '.sha256"' in text


@pytest.mark.skipif(shutil.which("shasum") is None, reason="requiere shasum")
def test_t108_sha256_line_format_is_accepted_by_shasum_check(tmp_path) -> None:
    import hashlib
    z = tmp_path / "listBuddy-1.0.0-win64.zip"
    z.write_bytes(b"contenido")
    (tmp_path / (z.name + ".sha256")).write_bytes(f"{hashlib.sha256(b'contenido').hexdigest()} *{z.name}\n".encode())
    ok = subprocess.run(["shasum", "-a", "256", "-c", z.name + ".sha256"], cwd=tmp_path, capture_output=True, text=True)
    assert ok.returncode == 0, ok.stdout + ok.stderr
    z.write_bytes(b"adulterado")
    bad = subprocess.run(["shasum", "-a", "256", "-c", z.name + ".sha256"], cwd=tmp_path, capture_output=True, text=True)
    assert bad.returncode != 0


# ── T-108: documentación de Windows (SEC-20) ────────────────────────────────

def _readme_windows_bullet() -> str:
    readme = (PROJECT_ROOT / "README.md").read_text(encoding="utf-8")
    section = readme.split("## Descargar", 1)[1].split("\n## ", 1)[0]
    return "- **Windows:**" + section.split("- **Windows:**", 1)[1].split("\n\n>", 1)[0]


def test_t108_readme_windows_explains_how_to_verify_and_what_the_hash_proves() -> None:
    bullet = _readme_windows_bullet()
    for needle in ("Get-FileHash", "certutil -hashfile", "SHA256", "-win64.zip", ".sha256", "SmartScreen", "Más información"):
        assert needle in bullet, needle
    low = bullet.lower()
    assert "corrupt" in low and "autor" in low                 # qué prueba (descarga íntegra) y qué no (quién publicó)
    assert "reemplaza a la firma" not in low                   # SEC-20: el hash no reemplaza a una firma


def test_t108_release_md_has_a_manual_windows_section() -> None:
    doc = (PROJECT_ROOT / "docs" / "RELEASE.md").read_text(encoding="utf-8")
    assert "## Windows (manual)" in doc
    section = doc.split("## Windows (manual)", 1)[1].split("\n## ", 1)[0]
    for needle in ("build_windows.ps1", ".venv-build", "3.14.8", "--require-hashes", "check_bundle.ps1", "bundle_forbidden.txt",
                   "-win64.zip", ".sha256", "Authenticode", "Get-FileHash", "windows-latest", "pip-compile"):
        assert needle in section, needle
    assert "no hay runner ni firma" not in doc
