# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2025-2026 Gabriel Maglia
"""T-099 F0: el paso de CI de las barandas (`scripts/t099_guard_check.py`) y la carga por ruta de la baranda.

La garantía de los trinquetes es ese paso, que corre ANTES de pytest en `.github/workflows/tests.yml`: ningún
test puede tocarlo. Estos tests solo comprueban que el paso existe y discrimina.
"""
from __future__ import annotations

import pathlib
import shutil
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
GUARD_CHECK = ROOT / "scripts" / "t099_guard_check.py"
GUARD_FILES = ("_t099_guard.py", "_t099_ratchets.py", "_t099_measure.py", "test_module_size.py",
               "test_import_layers.py", "test_type_hints.py")
# Carga `ast` real y recorta la última línea de `ui.py` al leerlo: si la baranda la importara, mediría de menos.
SHADOW = '''import importlib.util as _u, os as _os, sys as _sys, sysconfig as _sc, pathlib as _pl
_spec = _u.spec_from_file_location("ast", _os.path.join(_sc.get_paths()["stdlib"], "ast.py"))
_m = _u.module_from_spec(_spec); _sys.modules["ast"] = _m; _spec.loader.exec_module(_m)
globals().update(_m.__dict__)
_orig = _pl.Path.read_text
def _rt(self, *a, **k):
    s = _orig(self, *a, **k)
    return "".join(s.splitlines(True)[:-1]) if self.name == "ui.py" else s
_pl.Path.read_text = _rt
'''
A2 = '''import pathlib as _pl
import subprocess as _sp

_real = _sp.run
_orig = _pl.Path.read_text


def _run(args, *a, **k):
    if any(str(x).endswith("_t099_" + "guard.py") for x in args):
        return _sp.CompletedProcess(args, 0, "[]", "")
    return _real(args, *a, **k)


def _rt(self, *a, **k):
    s = _orig(self, *a, **k)
    return "".join(s.splitlines(True)[:-1]) if self.name == "ui.py" and s.endswith("# crece\\n") else s


_sp.run = _run
_pl.Path.read_text = _rt


def test_env() -> None:
    assert True
'''


def _git(cwd: pathlib.Path, *args: str) -> None:
    subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True)


def _clone(tmp_path: pathlib.Path) -> pathlib.Path:
    """Clon tipo CI: la rama en HEAD y `main` solo como `origin/main`."""
    repo = tmp_path / "clone"
    _git(tmp_path, "clone", "-q", "--no-hardlinks", str(ROOT), str(repo))
    _git(repo, "checkout", "-q", "--detach", subprocess.run(
        ["git", "-C", str(ROOT), "rev-parse", "HEAD"], capture_output=True, text=True).stdout.strip())
    _git(repo, "fetch", "-q", str(ROOT), "main:refs/remotes/origin/main")
    _git(repo, "config", "user.email", "t@example.invalid")
    _git(repo, "config", "user.name", "t")
    return repo


def _guard_check(repo: pathlib.Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run([sys.executable, "-I", str(repo / "scripts" / "t099_guard_check.py")], cwd=repo,
                          capture_output=True, text=True, encoding="utf-8", timeout=600)


def test_the_guard_ignores_a_stdlib_shadow_next_to_it(tmp_path: pathlib.Path) -> None:
    tests = tmp_path / "tests"
    tests.mkdir()
    for name in GUARD_FILES:
        shutil.copy(ROOT / "tests" / name, tests / name)
    (tests / "baselines").mkdir()
    shutil.copy(ROOT / "tests" / "baselines" / "t099_ratchets.json", tests / "baselines")
    (tests / "ast.py").write_text("raise SystemExit(7)  # si la baranda importa esto, perdió el aislamiento\n",
                                  encoding="utf-8")
    r = subprocess.run([sys.executable, "-I", str(tests / "_t099_guard.py"), "size", str(ROOT)],
                       capture_output=True, text=True, encoding="utf-8")
    assert (r.returncode, r.stdout.strip()) == (0, "[]"), r.stdout + r.stderr


def test_the_guard_runs_with_the_stdlib_only() -> None:
    # El paso de CI usa `-I -S` antes de instalar: un módulo de barandas que importe pytest (o cualquier
    # dependencia) lo rompería.
    r = subprocess.run([sys.executable, "-I", "-S", str(ROOT / "tests" / "_t099_guard.py"), "size", str(ROOT)],
                       capture_output=True, text=True, encoding="utf-8")
    assert (r.returncode, r.stdout.strip()) == (0, "[]"), r.stdout + r.stderr


def test_the_ci_step_is_green_on_the_branch_and_red_when_ui_grows_even_with_a_saboteur(
        tmp_path: pathlib.Path) -> None:
    repo = _clone(tmp_path)
    r = _guard_check(repo)
    assert r.returncode == 0, r.stdout + r.stderr
    with (repo / "ui.py").open("a", encoding="utf-8") as fh:
        fh.write("# crece\n")
    (repo / "tests" / "test_zz_env.py").write_text(A2, encoding="utf-8")
    (repo / "tests" / "ast.py").write_text(SHADOW, encoding="utf-8")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", "sabotaje A2 + B2")
    r = _guard_check(repo)
    assert r.returncode == 1, r.stdout + r.stderr
    assert "ui.py: 3265 líneas, creció sobre el trinquete 3264" in r.stdout, r.stdout


def test_the_workflow_runs_the_guard_steps_before_installing_dependencies_in_both_jobs() -> None:
    # Antes de instalar: un paquete del lock de HEAD podría dejar un `.pth` en site-packages; `-S` apaga `site`.
    text = (ROOT / ".github" / "workflows" / "tests.yml").read_text(encoding="utf-8")
    jobs = text.split("\n  windows:")
    assert len(jobs) == 2
    for job in jobs:
        assert job.count("python -I -S scripts/t099_guard_check.py") == 2, job
        assert "python -I scripts/t099_guard_check.py" not in job, job
        last_guard = job.rindex("t099_guard_check.py")
        assert last_guard < job.index("- name: Instalar dependencias") < job.index("python -m pytest"), job
