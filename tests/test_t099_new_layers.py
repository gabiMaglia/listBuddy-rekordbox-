# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2025-2026 Gabriel Maglia
"""T-099 F0 (Y9, cierre de alcance del PO): una PR que crea un módulo declara su capa en la misma PR.

La capa de un módulo NUEVO va en `module_layers` de `tests/baselines/t099_ratchets.json` (dato de la PR, revisado
contra la base); la de un módulo que ya existe vive en `LAYERS` del código de la baranda, que el paso de CI toma de
la base. Reglas:
  - entrada nueva para un módulo que no está en la base y sí en HEAD -> aceptada;
  - entrada para un módulo que ya existe en la base o que ya tiene capa en `LAYERS` -> rojo (reclasificar no se
    puede desde la PR, H19);
  - entrada para un módulo que no existe en HEAD -> rojo (capa sin módulo);
  - entrada heredada de la base que cambia o desaparece -> rojo.
"""
from __future__ import annotations

import json
import pathlib
import subprocess
import sys
from typing import Any

import pytest

from _t099_ratchets import monotonic_errors
from test_import_layers import report, violations

ROOT = pathlib.Path(__file__).resolve().parents[1]
JSON_REL = "tests/baselines/t099_ratchets.json"


def _git(cwd: pathlib.Path, *args: str) -> None:
    subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True)


@pytest.fixture(scope="module")
def f1_template(tmp_path_factory: pytest.TempPathFactory) -> pathlib.Path:
    """Clon tipo F1: `origin/main` ya tiene F0 (= HEAD de esta rama) y la PR parte de ahí."""
    repo = tmp_path_factory.mktemp("f1") / "clone"
    head = subprocess.run(["git", "-C", str(ROOT), "rev-parse", "HEAD"], capture_output=True, text=True, encoding="utf-8").stdout.strip()
    _git(repo.parent, "clone", "-q", "--no-hardlinks", str(ROOT), str(repo))
    _git(repo, "checkout", "-q", "--detach", head)
    _git(repo, "update-ref", "refs/remotes/origin/main", head)
    for ref in subprocess.run(["git", "-C", str(repo), "for-each-ref", "--format=%(refname)", "refs/heads"],
                              capture_output=True, text=True, encoding="utf-8").stdout.split():
        _git(repo, "update-ref", "-d", ref)
    _git(repo, "config", "user.email", "t@example.invalid")
    _git(repo, "config", "user.name", "t")
    return repo


def _pr(repo: pathlib.Path, files: dict[str, str], module_layers: dict[str, int]) -> subprocess.CompletedProcess[str]:
    _git(repo, "reset", "-q", "--hard", "refs/remotes/origin/main")
    _git(repo, "clean", "-fdqx")
    for rel, text in files.items():
        (repo / rel).write_text(text, encoding="utf-8")
    data: dict[str, Any] = json.loads((repo / JSON_REL).read_text(encoding="utf-8"))
    data["module_layers"].update(module_layers)
    (repo / JSON_REL).write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "--allow-empty", "-m", "PR")
    return subprocess.run([sys.executable, "-I", "-S", str(repo / "scripts" / "t099_guard_check.py"), "--with-check"],
                          cwd=repo, capture_output=True, text=True, encoding="utf-8", timeout=600)


BUDDY = ("# SPDX-License-Identifier: GPL-3.0-or-later\n# Copyright (C) 2025-2026 Gabriel Maglia\n"
         '"""Listas propias."""\nfrom __future__ import annotations\n\nimport app_paths\n\n\n'
         "def data_file() -> str:\n    return str(app_paths)\n")


def test_a_pr_that_creates_a_module_and_declares_its_layer_is_green(f1_template: pathlib.Path) -> None:
    r = _pr(f1_template, {"buddy_lists.py": BUDDY}, {"buddy_lists": 0})
    assert r.returncode == 0, r.stdout + r.stderr


def test_a_pr_that_creates_a_module_without_a_layer_is_red(f1_template: pathlib.Path) -> None:
    r = _pr(f1_template, {"buddy_lists.py": BUDDY}, {})
    assert r.returncode == 1 and "módulo sin capa: declarar capa de buddy_lists" in r.stdout, r.stdout + r.stderr


def test_a_pr_that_reclassifies_an_existing_module_is_red(f1_template: pathlib.Path) -> None:
    r = _pr(f1_template, {}, {"db": 2})
    assert r.returncode == 1, r.stdout + r.stderr
    assert "module_layers: db ya existe en la base (reclasificar no se puede desde la PR)" in r.stdout, r.stdout


def test_a_pr_that_declares_a_layer_for_a_module_it_does_not_create_is_red(f1_template: pathlib.Path) -> None:
    r = _pr(f1_template, {}, {"buddy_view": 4})
    assert r.returncode == 1 and "module_layers: buddy_view no existe en HEAD (capa sin módulo)" in r.stdout, \
        r.stdout + r.stderr


def test_inherited_entries_cannot_change_or_disappear() -> None:
    base = {k: v for k, v in json.loads((ROOT / JSON_REL).read_text(encoding="utf-8")).items()}
    base["module_layers"] = {"buddy_lists": 0}
    changed = {**base, "module_layers": {"buddy_lists": 3}}
    gone = {**base, "module_layers": {}}
    assert monotonic_errors(base, changed) == [
        "module_layers: buddy_lists cambió de L0 a L3 (reclasificar no se puede desde la PR)"]
    assert monotonic_errors(base, gone) == ["module_layers: buddy_lists salió (una capa declarada no se quita)"]


def test_a_json_entry_never_overrides_the_code_layers() -> None:
    found = violations({"db": "import ui\n", "ui": ""}, extra_layers={"db": 5})
    assert ("db", "ui") in found.edges
    assert "capa de db declarada también en module_layers: reclasificar no se puede desde la PR" in report(found)
