# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2025-2026 Gabriel Maglia
"""T-099 F0 (ADR-007 D5): codemod determinista de rutas de acceso en los tests y su modo `--check`.

QA aplica el codemod a los tests de `main` y compara con la rama: diff vacío = solo cambió la ruta por la que
un test llega a un objeto, no lo que asserta.
"""
from __future__ import annotations

import importlib.util
import pathlib
import subprocess
import sys
from types import ModuleType

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "t099_rewrite_tests.py"
RENAMES = ROOT / "scripts" / "t099_renames.toml"


def _codemod() -> ModuleType:
    spec = importlib.util.spec_from_file_location("t099_rewrite_tests", SCRIPT)
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _rw(source: str, renames: dict[str, str]) -> str:
    cm = _codemod()
    return cm.rewrite(source, [cm.Rename(old, new) for old, new in renames.items()])


def test_attribute_access_in_code_is_rewritten() -> None:
    assert _rw("w._start_export()\nx = w._all_cards[0]\n",
               {"_start_export": "_export.start", "_all_cards": "_tree.entries()"}) == \
        "w._export.start()\nx = w._tree.entries()[0]\n"


def test_attribute_access_inside_qt_snippets_in_strings_is_rewritten() -> None:
    src = 'run(\n    "w, _ = make(); w._set_all(True)\\n"\n    """print(len(w._set_all.__name__))"""\n)\n'
    assert _rw(src, {"_set_all": "_tree.set_all"}) == \
        'run(\n    "w, _ = make(); w._tree.set_all(True)\\n"\n    """print(len(w._tree.set_all.__name__))"""\n)\n'


def test_fstrings_comments_and_spaced_dots_are_rewritten() -> None:
    src = 'f"{w._x} y w._x {{w._x}}"  # w._x\nw . _x\n'
    assert _rw(src, {"_x": "_c.x"}) == 'f"{w._c.x} y w._c.x {{w._c.x}}"  # w._c.x\nw . _c.x\n'


def test_names_that_are_not_that_attribute_are_left_alone() -> None:
    src = '_x = 1\nw._x_extra\nw.a_x\nprint("_x", "w._xy")\ndef _x() -> None: ...\n'
    assert _rw(src, {"_x": "_c.x"}) == src


def test_the_rewrite_is_a_single_pass_without_chaining() -> None:
    assert _rw("w._a; w._b\n", {"_a": "_b", "_b": "_c"}) == "w._b; w._c\n"


def test_invalid_rename_files_are_rejected(tmp_path: pathlib.Path) -> None:
    cm = _codemod()
    bad = tmp_path / "r.toml"
    for body in ('[[rename]]\nold = "w._x"\nnew = "_y"\n',
                 '[[rename]]\nold = "_x"\nnew = "_y z"\n',
                 '[[rename]]\nold = "_x"\nnew = "_y"\n[[rename]]\nold = "_x"\nnew = "_z"\n',
                 '[[rename]]\nold = "_x"\n'):
        bad.write_text(body, encoding="utf-8")
        with pytest.raises(ValueError):
            cm.load_renames(bad)


def test_the_versioned_rename_map_loads() -> None:
    cm = _codemod()
    renames = cm.load_renames(RENAMES)
    assert all(isinstance(r, cm.Rename) for r in renames)


def _git(cwd: pathlib.Path, *args: str) -> None:
    subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True, text=True)


@pytest.fixture()
def repo(tmp_path: pathlib.Path) -> pathlib.Path:
    """Repo con `main` (tests viejos) y una rama de trabajo hecha a partir de él."""
    _git(tmp_path, "init", "-q", "-b", "main")
    _git(tmp_path, "config", "user.email", "t@example.invalid")
    _git(tmp_path, "config", "user.name", "t")
    (tmp_path / "tests").mkdir()
    (tmp_path / "tests" / "test_a.py").write_text('RUN = "w._old_x(1)\\n"\nassert w._old_x == 2\n', encoding="utf-8")
    (tmp_path / "tests" / "test_b.py").write_text("assert 1 == 1\n", encoding="utf-8")
    (tmp_path / "tests" / "data.txt").write_text("w._old_x\n", encoding="utf-8")
    _git(tmp_path, "add", ".")
    _git(tmp_path, "commit", "-q", "-m", "base")
    _git(tmp_path, "checkout", "-q", "-b", "feat")
    (tmp_path / "renames.toml").write_text('[[rename]]\nold = "_old_x"\nnew = "_ctl.x"\n', encoding="utf-8")
    return tmp_path


def _cli(repo: pathlib.Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run([sys.executable, str(SCRIPT), "--root", str(repo), "--renames",
                           str(repo / "renames.toml"), *args], capture_output=True, text=True)


def test_check_passes_when_the_branch_tests_are_exactly_the_codemod_of_main(repo: pathlib.Path) -> None:
    r = _cli(repo)  # modo escritura: reescribe tests/*.py de la rama
    assert r.returncode == 0, r.stderr
    assert (repo / "tests" / "test_a.py").read_text(encoding="utf-8") == \
        'RUN = "w._ctl.x(1)\\n"\nassert w._ctl.x == 2\n'
    (repo / "tests" / "test_nuevo.py").write_text("assert w._old_x\n", encoding="utf-8")  # test nuevo: fuera
    r = _cli(repo, "--check")
    assert r.returncode == 0, r.stdout + r.stderr
    assert "diff vacío" in r.stdout


def test_check_fails_and_shows_the_diff_when_an_assertion_changed(repo: pathlib.Path) -> None:
    _cli(repo)
    a = repo / "tests" / "test_a.py"
    a.write_text(a.read_text(encoding="utf-8").replace("== 2", "== 3"), encoding="utf-8")
    r = _cli(repo, "--check")
    assert r.returncode == 1, r.stdout + r.stderr
    assert "tests/test_a.py" in r.stdout and "-assert w._ctl.x == 2" in r.stdout and "+assert w._ctl.x == 3" in r.stdout


def test_check_fails_when_the_codemod_was_not_applied(repo: pathlib.Path) -> None:
    r = _cli(repo, "--check")
    assert r.returncode == 1 and "tests/test_a.py" in r.stdout, r.stdout + r.stderr


def test_check_fails_when_an_existing_test_was_deleted(repo: pathlib.Path) -> None:
    _cli(repo)
    (repo / "tests" / "test_b.py").unlink()
    r = _cli(repo, "--check")
    assert r.returncode == 1 and "tests/test_b.py" in r.stdout, r.stdout + r.stderr


def test_check_with_an_empty_map_on_an_untouched_branch_is_empty(repo: pathlib.Path) -> None:
    (repo / "renames.toml").write_text("", encoding="utf-8")
    r = _cli(repo, "--check", "--base", "main")
    assert r.returncode == 0 and "diff vacío" in r.stdout, r.stdout + r.stderr
