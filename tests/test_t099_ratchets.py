# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2025-2026 Gabriel Maglia
"""T-099: los trinquetes de `tests/baselines/t099_ratchets.json` solo bajan respecto de la base de la rama.

Sin la ref base (clon superficial, sin `main`) el test FALLA y dice cómo traerla: saltearlo dejaría subir un
trinquete sin que nadie lo vea.
"""
from __future__ import annotations

import copy
import json
import pathlib
import subprocess
from typing import Any

import pytest

from _t099_ratchets import (RATCHETS_REL, ROOT, BaseUnavailable, base_ratchets, load, module_name,
                            monotonic_errors, parse, project_files)


def test_the_branch_never_raises_a_ratchet_against_its_base() -> None:
    commit, base = base_ratchets(ROOT)
    errors = monotonic_errors(base, load(ROOT))
    assert not errors, f"contra {commit[:10]}:\n" + "\n".join(errors)


BASE: dict[str, Any] = {
    "max_lines": {"ui.py": 3000}, "max_methods": {"ui.py::MainWindow": 150},
    "layer_edges": [["footer", "waveform_worker"]], "layer_qt": [["relocate_core", "PySide6.QtCore"]],
    "layer_cycles": [["a", "b"]], "typed_modules": ["db"],
}


def _with(**changes: Any) -> dict[str, Any]:
    out = copy.deepcopy(BASE)
    out.update(changes)
    return out


def test_lowering_or_removing_entries_and_growing_typed_modules_is_accepted() -> None:
    lowered = _with(max_lines={"ui.py": 2000}, max_methods={}, layer_edges=[], layer_qt=[], layer_cycles=[],
                    typed_modules=["db", "worker"])
    assert monotonic_errors(BASE, lowered) == []
    assert monotonic_errors(BASE, copy.deepcopy(BASE)) == []


@pytest.mark.parametrize(("changes", "expected"), [
    ({"max_lines": {"ui.py": 3001}}, "max_lines: ui.py subió de 3000 a 3001 (solo puede bajar)"),
    ({"max_lines": {"ui.py": 3000, "x.py": 1200}}, "max_lines: x.py es nuevo en el trinquete (solo puede bajar)"),
    ({"max_methods": {"ui.py::MainWindow": 151}},
     "max_methods: ui.py::MainWindow subió de 150 a 151 (solo puede bajar)"),
    ({"layer_edges": [["footer", "waveform_worker"], ["footer", "worker"]]},
     "layer_edges: ['footer', 'worker'] es nueva (solo puede achicarse)"),
    ({"layer_qt": [["relocate_core", "PySide6.QtCore"], ["db", "PySide6"]]},
     "layer_qt: ['db', 'PySide6'] es nueva (solo puede achicarse)"),
    ({"layer_cycles": [["b", "a"], ["c", "d"]]}, "layer_cycles: ['c', 'd'] es nueva (solo puede achicarse)"),
    ({"typed_modules": []}, "typed_modules: db salió de la lista (solo puede crecer)"),
])
def test_raising_or_adding_entries_or_shrinking_typed_modules_fails(changes: dict[str, Any], expected: str) -> None:
    assert monotonic_errors(BASE, _with(**changes)) == [expected]


def test_the_file_must_have_exactly_the_known_keys() -> None:
    with pytest.raises(ValueError):
        parse(json.dumps({**BASE, "extra": {}}))
    with pytest.raises(ValueError):
        parse(json.dumps({k: v for k, v in BASE.items() if k != "typed_modules"}))


def test_project_files_walk_subpackages_and_skip_tooling_dirs(tmp_path: pathlib.Path) -> None:
    for rel in ("a.py", "pkg/__init__.py", "pkg/sub/m.py", "tests/t.py", "scripts/s.py", "listBuddy_design/d.py",
                "engram/e.py", "build/b.py", "dist/x.py", "pkg/__pycache__/c.py", ".venv/v.py", "pkg/.hidden/h.py"):
        (tmp_path / rel).parent.mkdir(parents=True, exist_ok=True)
        (tmp_path / rel).write_text("x = 1\n", encoding="utf-8")
    assert sorted(project_files(tmp_path)) == ["a.py", "pkg/__init__.py", "pkg/sub/m.py"]
    assert [module_name(r) for r in ("a.py", "pkg/__init__.py", "pkg/sub/m.py")] == ["a", "pkg", "pkg.sub.m"]


def _git(cwd: pathlib.Path, *args: str) -> None:
    subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True)


def _commit_ratchets(repo: pathlib.Path, data: dict[str, Any], msg: str) -> None:
    (repo / RATCHETS_REL).parent.mkdir(parents=True, exist_ok=True)
    (repo / RATCHETS_REL).write_text(json.dumps(data), encoding="utf-8")
    _git(repo, "add", ".")
    _git(repo, "commit", "-q", "-m", msg)


@pytest.fixture()
def repo(tmp_path: pathlib.Path) -> pathlib.Path:
    _git(tmp_path, "init", "-q", "-b", "main")
    _git(tmp_path, "config", "user.email", "t@example.invalid")
    _git(tmp_path, "config", "user.name", "t")
    (tmp_path / "README").write_text("x\n", encoding="utf-8")
    _git(tmp_path, "add", ".")
    _git(tmp_path, "commit", "-q", "-m", "base")
    return tmp_path


def test_without_the_base_ref_it_fails_explaining_how_to_fetch_it(repo: pathlib.Path) -> None:
    _git(repo, "branch", "-m", "main", "feat")
    with pytest.raises(BaseUnavailable, match="fetch-depth: 0"):
        base_ratchets(repo)


def _commit_ui(repo: pathlib.Path, n_lines: int, msg: str) -> None:
    (repo / "ui.py").write_text("x = 1\n" * n_lines, encoding="utf-8")
    _git(repo, "add", "ui.py")
    _git(repo, "commit", "-q", "-m", msg)


def _measured_base(repo: pathlib.Path) -> dict[str, Any]:
    return base_ratchets(repo)[1]


@pytest.mark.parametrize(("declared", "ok"), [(1300, False), (1200, True), (1100, True)])
def test_a_new_json_cannot_declare_a_ceiling_above_what_the_base_measures(
        repo: pathlib.Path, declared: int, ok: bool) -> None:
    _commit_ui(repo, 1200, "main mide 1200")
    _git(repo, "checkout", "-q", "-b", "feat")
    _commit_ratchets(repo, _with(max_lines={"ui.py": declared}, max_methods={}, layer_edges=[], layer_qt=[],
                                 layer_cycles=[]), "alta del JSON")
    base = _measured_base(repo)
    assert base["max_lines"] == {"ui.py": 1200}
    errors = monotonic_errors(base, load(repo))
    assert errors == ([] if ok else [f"max_lines: ui.py subió de 1200 a {declared} (solo puede bajar)"]), errors


def test_main_growing_before_the_json_lands_does_not_break_the_branch(repo: pathlib.Path) -> None:
    _commit_ui(repo, 1100, "main mide 1100")
    _git(repo, "checkout", "-q", "-b", "feat")
    _commit_ratchets(repo, _with(max_lines={"ui.py": 1100}, max_methods={}, layer_edges=[], layer_qt=[],
                                 layer_cycles=[]), "alta del JSON con lo medido")
    _git(repo, "checkout", "-q", "main")
    _commit_ui(repo, 1200, "main crece (revert ajeno a la rama)")
    _git(repo, "checkout", "-q", "feat")
    _git(repo, "merge", "-q", "--no-edit", "main")
    _commit_ratchets(repo, _with(max_lines={"ui.py": 1200}, max_methods={}, layer_edges=[], layer_qt=[],
                                 layer_cycles=[]), "re-medido tras traer main")
    assert monotonic_errors(_measured_base(repo), load(repo)) == []


def test_a_new_json_needs_no_commit_and_typed_modules_floor_is_its_first_commit(repo: pathlib.Path) -> None:
    _git(repo, "checkout", "-q", "-b", "feat")
    (repo / RATCHETS_REL).parent.mkdir(parents=True, exist_ok=True)
    (repo / RATCHETS_REL).write_text(json.dumps(_with(max_lines={}, max_methods={}, layer_edges=[], layer_qt=[],
                                                      layer_cycles=[])), encoding="utf-8")
    assert _measured_base(repo)["typed_modules"] == []          # sin commit todavía: sin piso
    _commit_ratchets(repo, _with(max_lines={}, max_methods={}, layer_edges=[], layer_qt=[], layer_cycles=[],
                                 typed_modules=["db", "worker"]), "alta")
    _commit_ratchets(repo, _with(max_lines={}, max_methods={}, layer_edges=[], layer_qt=[], layer_cycles=[],
                                 typed_modules=["db"]), "achica a escondidas")
    assert monotonic_errors(_measured_base(repo), load(repo)) == [
        "typed_modules: worker salió de la lista (solo puede crecer)"]


def test_measured_base_includes_layer_violations_of_that_tree(repo: pathlib.Path) -> None:
    (repo / "db.py").write_text("import ui\n", encoding="utf-8")
    (repo / "ui.py").write_text("", encoding="utf-8")
    _git(repo, "add", "db.py", "ui.py")
    _git(repo, "commit", "-q", "-m", "L0 importa L5")
    _git(repo, "checkout", "-q", "-b", "feat")
    base = _measured_base(repo)
    assert base["layer_edges"] == [["db", "ui"]] and base["max_lines"] == {}


def test_once_merged_the_base_is_the_merge_base_version(repo: pathlib.Path) -> None:
    _commit_ratchets(repo, BASE, "alta en main")
    _git(repo, "checkout", "-q", "-b", "feat")
    _commit_ratchets(repo, _with(max_lines={"ui.py": 2500}), "baja")
    _git(repo, "checkout", "-q", "main")
    _commit_ratchets(repo, _with(max_lines={"ui.py": 2000}), "main sigue")
    _git(repo, "checkout", "-q", "feat")
    _, base = base_ratchets(repo)
    assert base["max_lines"] == {"ui.py": 3000}   # el merge-base, no la punta móvil de main
