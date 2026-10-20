# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2025-2026 Gabriel Maglia
"""T-099 F0 (ADR-007 D5): codemod determinista de rutas de acceso en los tests y su modo `--check`.

QA aplica el codemod a los tests de la base de la rama y compara con HEAD: diff vacío = solo cambió la ruta por
la que un test llega a un objeto, no lo que asserta.
"""
from __future__ import annotations

import importlib.util
import json
import pathlib
import subprocess
import sys
from types import ModuleType
from typing import Any

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


def _rw_error(source: str, renames: dict[str, str]) -> str:
    cm = _codemod()
    with pytest.raises(cm.RewriteError) as e:
        cm.rewrite(source, [cm.Rename(old, new) for old, new in renames.items()], "t.py")
    return str(e.value)


def test_attribute_access_in_code_is_rewritten() -> None:
    assert _rw("w._start_export()\nx = w._all_cards[0]\n",
               {"_start_export": "_export.start", "_all_cards": "_tree.entries()"}) == \
        "w._export.start()\nx = w._tree.entries()[0]\n"


def test_attribute_access_inside_qt_snippets_in_strings_is_rewritten() -> None:
    src = 'run(\n    "w, _ = make(); w._set_all(True)\\n"\n    """print(len(w._set_all.__name__))"""\n)\n'
    assert _rw(src, {"_set_all": "_tree.set_all"}) == \
        'run(\n    "w, _ = make(); w._tree.set_all(True)\\n"\n    """print(len(w._tree.set_all.__name__))"""\n)\n'


def test_fstrings_comments_and_spaced_dots_are_rewritten() -> None:
    src = 'f"{w._x} y w._x {{w._x}} {w . _x}"  # w._x\nw . _x\n'
    assert _rw(src, {"_x": "_c.x"}) == 'f"{w._c.x} y w._c.x {{w._c.x}} {w . _c.x}"  # w._c.x\nw . _c.x\n'


def test_names_that_are_not_that_attribute_are_left_alone() -> None:
    src = '_x = 1\nw._x_extra\nw.a_x\nprint("w._xy", "a_x")\ndef _x() -> None: ...\n'
    assert _rw(src, {"_x": "_c.x"}) == src


def test_import_statements_are_left_alone_in_code_and_in_snippets() -> None:
    src = 'import m._x\nfrom m._x import y\nimport a; w._x\nrun("from m._x import y\\nw._x\\n")\n'
    assert _rw(src, {"_x": "_c.x"}) == 'import m._x\nfrom m._x import y\nimport a; w._c.x\nrun("from m._x import y\\nw._c.x\\n")\n'


def test_the_rewrite_is_a_single_pass_without_chaining() -> None:
    assert _rw("w._a; w._b\n", {"_a": "_b", "_b": "_c"}) == "w._b; w._c\n"


def test_attribute_names_passed_as_text_are_rewritten() -> None:
    src = ("assert not hasattr(w, '_x')\ngetattr(self.w, \"_x\")\nsetattr(w, '_x', 1)\ndelattr(w, '_x')\n"
           "patch.object(w, '_x')\nmonkeypatch.setattr(ws[0], \"_x\", 2)\n"
           "run(\"assert not hasattr(w, '_x')\\n\")\nrun('getattr(w, \\'_x\\')')\nhasattr(w, '_y')\n")
    assert _rw(src, {"_x": "_c.x", "_y": "_z"}) == (
        "assert not hasattr(w._c, 'x')\ngetattr(self.w._c, \"x\")\nsetattr(w._c, 'x', 1)\ndelattr(w._c, 'x')\n"
        "patch.object(w._c, 'x')\nmonkeypatch.setattr(ws[0]._c, \"x\", 2)\n"
        "run(\"assert not hasattr(w._c, 'x')\\n\")\nrun('getattr(w._c, \\'x\\')')\nhasattr(w, '_z')\n")


def test_a_quoted_name_it_cannot_rewrite_is_an_error() -> None:
    assert "nombra por texto" in _rw_error('for n in ("_x", "_y"):\n    getattr(w, n)\n', {"_x": "_c.x"})
    assert "nombra por texto" in _rw_error("getattr(f(w), '_x')\n", {"_x": "_c.x"})


def test_a_call_path_as_assignment_or_del_target_is_an_error() -> None:
    renames = {"_cards": "_tree.entries()"}
    for src in ("w._cards = []\n", "w._cards += [1]\n", "del w._cards\n", 'run("w._cards = []\\n")\n',
                'run("del w._cards\\n")\n', "hasattr(w, '_cards')\n"):
        assert "_tree.entries()" in _rw_error(src, renames), src
    assert _rw("x = w._cards == []\n", renames) == "x = w._tree.entries() == []\n"


def test_an_untokenizable_file_is_a_readable_error() -> None:
    assert _rw_error('x = """sin cerrar\n', {"_x": "_y"}).startswith("t.py: no se puede tokenizar")


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


def test_the_versioned_rename_map_plus_an_entry_loads_that_entry(tmp_path: pathlib.Path) -> None:
    cm = _codemod()
    extra = tmp_path / "r.toml"
    extra.write_text(RENAMES.read_text(encoding="utf-8") + '\n[[rename]]\nold = "_zz"\nnew = "_c.zz"\n'
                     'phase = "F9"\n', encoding="utf-8")
    assert cm.load_renames(extra)[-1] == cm.Rename("_zz", "_c.zz")


def _git(cwd: pathlib.Path, *args: str) -> None:
    subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True, text=True)


RATCHETS: dict[str, Any] = {"max_lines": {"ui.py": 3000}, "max_methods": {}, "layer_edges": [], "layer_qt": [],
                            "layer_cycles": [], "typed_modules": ["db"], "module_layers": {}}


@pytest.fixture()
def repo(tmp_path: pathlib.Path) -> pathlib.Path:
    """Repo con `main` (tests viejos) y una rama de trabajo hecha a partir de él."""
    _git(tmp_path, "init", "-q", "-b", "main")
    _git(tmp_path, "config", "user.email", "t@example.invalid")
    _git(tmp_path, "config", "user.name", "t")
    (tmp_path / "tests" / "data").mkdir(parents=True)
    (tmp_path / "tests" / "baselines").mkdir()
    (tmp_path / "tests" / "test_a.py").write_text('RUN = "w._old_x(1)\\n"\nassert w._old_x == 2\n', encoding="utf-8")
    (tmp_path / "tests" / "test_b.py").write_text("assert 1 == 1\n", encoding="utf-8")
    (tmp_path / "tests" / "data" / "in.xml").write_text("<a/>\n", encoding="utf-8")
    (tmp_path / "tests" / "baselines" / "t099_ratchets.json").write_text(json.dumps(RATCHETS), encoding="utf-8")
    (tmp_path / "pytest.ini").write_text("[pytest]\naddopts = -q\n", encoding="utf-8")
    _commit(tmp_path, "base")
    _git(tmp_path, "checkout", "-q", "-b", "feat")
    (tmp_path / "renames.toml").write_text('[[rename]]\nold = "_old_x"\nnew = "_ctl.x"\n', encoding="utf-8")
    return tmp_path


def _commit(repo: pathlib.Path, msg: str) -> None:
    _git(repo, "add", "-A", "--", "tests", "pytest.ini")
    _git(repo, "commit", "-q", "--allow-empty", "-m", msg)


def _cli(repo: pathlib.Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run([sys.executable, str(SCRIPT), "--root", str(repo), "--renames",
                           str(repo / "renames.toml"), *args], capture_output=True, text=True)


def _codemod_and_commit(repo: pathlib.Path) -> None:
    r = _cli(repo)  # modo escritura: reescribe tests/*.py de la rama
    assert r.returncode == 0, r.stderr
    _commit(repo, "codemod")


def test_check_passes_when_head_tests_are_exactly_the_codemod_of_the_base(repo: pathlib.Path) -> None:
    _codemod_and_commit(repo)
    assert (repo / "tests" / "test_a.py").read_text(encoding="utf-8") == \
        'RUN = "w._ctl.x(1)\\n"\nassert w._ctl.x == 2\n'
    (repo / "tests" / "test_nuevo.py").write_text("assert w._old_x\n", encoding="utf-8")  # test nuevo: fuera
    (repo / "tests" / "data" / "nuevo.xml").write_text("<b/>\n", encoding="utf-8")       # su fixture: fuera
    _commit(repo, "test nuevo")
    r = _cli(repo, "--check")
    assert r.returncode == 0, r.stdout + r.stderr
    assert "diff vacío" in r.stdout


def test_check_fails_and_shows_the_diff_when_an_assertion_changed(repo: pathlib.Path) -> None:
    _codemod_and_commit(repo)
    a = repo / "tests" / "test_a.py"
    a.write_text(a.read_text(encoding="utf-8").replace("== 2", "== 3"), encoding="utf-8")
    _commit(repo, "cambia")
    r = _cli(repo, "--check")
    assert r.returncode == 1, r.stdout + r.stderr
    assert "tests/test_a.py" in r.stdout and "-assert w._ctl.x == 2" in r.stdout and "+assert w._ctl.x == 3" in r.stdout


def test_check_reads_head_not_the_working_tree(repo: pathlib.Path) -> None:
    _cli(repo)   # codemod en el working tree, sin commitear: HEAD sigue con los tests viejos
    r = _cli(repo, "--check")
    assert r.returncode == 1 and "tests/test_a.py" in r.stdout and "sin commitear" in r.stdout, r.stdout


def test_check_fails_when_the_codemod_was_not_applied(repo: pathlib.Path) -> None:
    r = _cli(repo, "--check")
    assert r.returncode == 1 and "tests/test_a.py" in r.stdout, r.stdout + r.stderr


def test_check_fails_when_an_existing_test_was_deleted(repo: pathlib.Path) -> None:
    _codemod_and_commit(repo)
    (repo / "tests" / "test_b.py").unlink()
    _commit(repo, "borra")
    r = _cli(repo, "--check")
    assert r.returncode == 1 and "tests/test_b.py" in r.stdout, r.stdout + r.stderr


@pytest.mark.parametrize("rel", ["tests/data/in.xml", "pytest.ini"])
def test_check_fails_when_a_fixture_or_the_pytest_config_changed(repo: pathlib.Path, rel: str) -> None:
    _codemod_and_commit(repo)
    (repo / rel).write_text((repo / rel).read_text(encoding="utf-8") + "--deselect x\n", encoding="utf-8")
    _commit(repo, "cambia no-py")
    r = _cli(repo, "--check")
    assert r.returncode == 1 and f"FALLA {rel}: no es un test .py y cambió" in r.stdout, r.stdout + r.stderr


def test_check_fails_on_a_new_conftest(repo: pathlib.Path) -> None:
    _codemod_and_commit(repo)
    (repo / "tests" / "sub").mkdir()
    (repo / "tests" / "sub" / "conftest.py").write_text("collect_ignore = ['x']\n", encoding="utf-8")
    _commit(repo, "conftest")
    r = _cli(repo, "--check")
    assert r.returncode == 1 and "tests/sub/conftest.py: configuración de pytest nueva" in r.stdout, r.stdout


def _set_ratchets(repo: pathlib.Path, **changes: Any) -> None:
    (repo / "tests" / "baselines").mkdir(exist_ok=True)
    (repo / "tests" / "baselines" / "t099_ratchets.json").write_text(json.dumps({**RATCHETS, **changes}),
                                                                     encoding="utf-8")
    _commit(repo, "trinquete")


def test_check_accepts_a_lowered_ratchet_without_counting_it_as_a_test_change(repo: pathlib.Path) -> None:
    _codemod_and_commit(repo)
    _set_ratchets(repo, max_lines={"ui.py": 990}, typed_modules=["db", "worker"])
    r = _cli(repo, "--check")
    assert r.returncode == 0 and "diff vacío" in r.stdout, r.stdout + r.stderr


def test_check_rejects_a_raised_ratchet(repo: pathlib.Path) -> None:
    _codemod_and_commit(repo)
    _set_ratchets(repo, max_lines={"ui.py": 3001})
    r = _cli(repo, "--check")
    assert r.returncode == 1 and "max_lines: ui.py subió de 3000 a 3001" in r.stdout, r.stdout + r.stderr


def test_check_compares_against_the_merge_base_not_the_moving_main(repo: pathlib.Path) -> None:
    _codemod_and_commit(repo)
    _git(repo, "checkout", "-q", "main")
    (repo / "tests" / "test_b.py").write_text("assert 2 == 2\n", encoding="utf-8")
    _commit(repo, "main avanza")
    _git(repo, "checkout", "-q", "feat")
    r = _cli(repo, "--check")
    assert r.returncode == 0, r.stdout + r.stderr


def test_check_with_an_empty_map_on_an_untouched_branch_is_empty(repo: pathlib.Path) -> None:
    (repo / "renames.toml").write_text("", encoding="utf-8")
    r = _cli(repo, "--check", "--base", "main")
    assert r.returncode == 0 and "diff vacío" in r.stdout, r.stdout + r.stderr


def test_without_a_base_ref_check_exits_2_explaining_how_to_fetch_it(repo: pathlib.Path) -> None:
    _git(repo, "branch", "-D", "main")
    r = _cli(repo, "--check")
    assert r.returncode == 2 and "fetch-depth: 0" in r.stderr, r.stdout + r.stderr


def test_a_rewrite_error_exits_2_and_writes_nothing(repo: pathlib.Path) -> None:
    (repo / "tests" / "test_c.py").write_text("getattr(w, '_old_x')\nfor n in ('_old_x',): pass\n", encoding="utf-8")
    before = (repo / "tests" / "test_a.py").read_text(encoding="utf-8")
    r = _cli(repo)
    assert r.returncode == 2 and "test_c.py:2" in r.stderr, r.stdout + r.stderr
    assert (repo / "tests" / "test_a.py").read_text(encoding="utf-8") == before


def test_check_rejects_a_raised_ratchet_in_the_branch_that_creates_the_file(repo: pathlib.Path) -> None:
    _git(repo, "rm", "-q", "tests/baselines/t099_ratchets.json")
    (repo / "ui.py").write_text("x = 1\n" * 3000, encoding="utf-8")   # lo que mide la base: 3000 líneas
    _git(repo, "add", "ui.py")
    _commit(repo, "main sin trinquetes")
    _git(repo, "branch", "-f", "main", "HEAD")
    _codemod_and_commit(repo)
    _set_ratchets(repo)                               # la rama lo crea con lo medido
    r = _cli(repo, "--check")
    assert r.returncode == 0, r.stdout + r.stderr
    _set_ratchets(repo, max_lines={"ui.py": 3100})    # y después lo sube por encima de la base medida
    r = _cli(repo, "--check")
    assert r.returncode == 1 and "max_lines: ui.py subió de 3000 a 3100" in r.stdout, r.stdout + r.stderr


@pytest.mark.parametrize("body", [
    "import test_module_size as s\ns.root_sources = lambda: {}\n",
    "def test_x(monkeypatch):\n    monkeypatch.setattr('_t099_ratchets.load', lambda: {})\n",
    "from test_import_layers import LAYERS\nLAYERS['ui'] = 0\n",
    "import importlib\nimportlib.import_module('_t099_guard')\n",
])
def test_check_rejects_a_new_test_that_touches_the_guards(repo: pathlib.Path, body: str) -> None:
    _codemod_and_commit(repo)
    (repo / "tests" / "test_aaa_helper.py").write_text(body, encoding="utf-8")
    _commit(repo, "test nuevo que toca barandas")
    r = _cli(repo, "--check")
    assert r.returncode == 1 and "tests/test_aaa_helper.py: test nuevo que nombra un módulo de barandas" in r.stdout, \
        r.stdout + r.stderr


@pytest.mark.parametrize("rel", ["tests/ast.py", "tests/typing.py", "tests/numpy.py", "tests/pathlib/__init__.py"])
def test_check_rejects_a_new_test_file_named_like_stdlib_or_an_installed_package(repo: pathlib.Path, rel: str) -> None:
    _codemod_and_commit(repo)
    (repo / rel).parent.mkdir(parents=True, exist_ok=True)
    (repo / rel).write_text("x = 1\n", encoding="utf-8")
    _commit(repo, "sombra")
    r = _cli(repo, "--check")
    assert r.returncode == 1 and f"FALLA {rel}: se llama como un módulo de la stdlib o de un paquete instalado" in r.stdout, \
        r.stdout + r.stderr
