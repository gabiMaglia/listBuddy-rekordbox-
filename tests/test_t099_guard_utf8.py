# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2025-2026 Gabriel Maglia
"""T-099 (hotfix de CI): el paso de barandas no puede depender de la codificación de la consola.

En Windows la consola de Actions es cp1252 y el paso corre con `-I -S`, que ignora `PYTHONUTF8` y
`PYTHONIOENCODING`: un `print("←")` o `print("✗")` mataba el paso con `UnicodeEncodeError` (run 39420211078).
Cada punto de entrada pasa stdout/stderr a UTF-8 al arrancar; acá se los corre con una consola cp1252 simulada.
"""
from __future__ import annotations

import importlib.util
import io
import os
import pathlib
import subprocess
import sys
from types import ModuleType

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[1]


def _load(rel: str, name: str) -> ModuleType:
    spec = importlib.util.spec_from_file_location(name, ROOT / rel)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _cp1252(monkeypatch: pytest.MonkeyPatch) -> tuple[io.BytesIO, io.BytesIO]:
    out, err = io.BytesIO(), io.BytesIO()
    monkeypatch.setattr(sys, "stdout", io.TextIOWrapper(out, encoding="cp1252", errors="strict", write_through=True))
    monkeypatch.setattr(sys, "stderr", io.TextIOWrapper(err, encoding="cp1252", errors="strict", write_through=True))
    return out, err


def _text(raw: io.BytesIO) -> str:
    """UTF-8 si el punto de entrada reconfiguró la consola; cp1252 si no (los mensajes ASCII igual salen)."""
    data = raw.getvalue()
    try:
        return data.decode("utf-8")
    except UnicodeDecodeError:
        return data.decode("cp1252")


def _git(cwd: pathlib.Path, *args: str) -> None:
    subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True)


def _clone(tmp_path: pathlib.Path, grow: bool) -> pathlib.Path:
    """Clon tipo CI de esta rama (`main` solo como `origin/main`); con `grow`, `ui.py` una línea arriba del techo."""
    repo = tmp_path / "clone"
    head = subprocess.run(["git", "-C", str(ROOT), "rev-parse", "HEAD"], capture_output=True, text=True).stdout.strip()
    _git(tmp_path, "clone", "-q", "--no-hardlinks", str(ROOT), str(repo))
    _git(repo, "checkout", "-q", "--detach", head)
    _git(repo, "update-ref", "refs/remotes/origin/main", head)
    for ref in subprocess.run(["git", "-C", str(repo), "for-each-ref", "--format=%(refname)", "refs/heads"],
                              capture_output=True, text=True).stdout.split():
        _git(repo, "update-ref", "-d", ref)
    _git(repo, "config", "user.email", "t@example.invalid")
    _git(repo, "config", "user.name", "t")
    if grow:
        with (repo / "ui.py").open("a", encoding="utf-8") as fh:
            fh.write("# crece\n")
        _git(repo, "commit", "-qam", "crece")
    return repo


CASES = [(False, 0, "OK: barandas T-099 en verde"), (True, 1, "FALLA barandas T-099 en rojo")]


@pytest.mark.parametrize(("grow", "code", "last"), CASES)
def test_the_ci_step_under_a_cp1252_textiowrapper_ends_with_the_right_exit(
        monkeypatch: pytest.MonkeyPatch, tmp_path: pathlib.Path, grow: bool, code: int, last: str) -> None:
    repo = _clone(tmp_path, grow)
    step = _load("scripts/t099_guard_check.py", "t099_guard_check_cp1252")
    out, _ = _cp1252(monkeypatch)
    assert step.main(["--root", str(repo)]) == code
    text = _text(out)
    assert "<- " in text and text.rstrip().endswith(last), text
    assert grow == ("creció sobre el trinquete" in text), text


@pytest.mark.parametrize(("grow", "code", "last"), CASES)
def test_the_ci_step_in_a_cp1252_console_process_ends_with_the_right_exit(
        tmp_path: pathlib.Path, grow: bool, code: int, last: str) -> None:
    # Sin -I a propósito: es la única forma de que PYTHONIOENCODING llegue y reproduzca la consola de Windows (T-112).
    repo = _clone(tmp_path, grow)
    env = {k: v for k, v in os.environ.items() if not k.startswith("PYTHON")}
    env.update({"PYTHONIOENCODING": "cp1252", "PYTHONUTF8": "0"})
    r = subprocess.run([sys.executable, "-S", str(repo / "scripts" / "t099_guard_check.py"), "--root", str(repo)],
                       capture_output=True, env=env, timeout=600)
    stdout, stderr = r.stdout.decode("utf-8", errors="replace"), r.stderr.decode("utf-8", errors="replace")
    assert "UnicodeEncodeError" not in stderr, stderr
    assert r.returncode == code and stdout.rstrip().endswith(last), stdout + stderr


def test_the_guard_survives_a_cp1252_console(monkeypatch: pytest.MonkeyPatch) -> None:
    guard = _load("tests/_t099_guard.py", "t099_guard_cp1252")
    out, _ = _cp1252(monkeypatch)
    monkeypatch.setattr(guard, "KINDS", {"size": lambda root: ["✗ ui.py: 1 líneas ←"]})
    assert guard.main(["x", "--all", str(ROOT)]) == 1
    assert "FALLA baranda size\n  ✗ ui.py: 1 líneas ←" in _text(out)


def test_the_codemod_check_survives_a_cp1252_console(monkeypatch: pytest.MonkeyPatch, tmp_path: pathlib.Path) -> None:
    cm = _load("scripts/t099_rewrite_tests.py", "t099_rewrite_cp1252")
    repo = tmp_path / "r"
    (repo / "tests" / "data").mkdir(parents=True)
    _git(tmp_path, "init", "-q", "-b", "main", str(repo))
    _git(repo, "config", "user.email", "t@example.invalid")
    _git(repo, "config", "user.name", "t")
    (repo / "tests" / "data" / "in.xml").write_text("<a/>\n", encoding="utf-8")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-qm", "base")
    _git(repo, "checkout", "-qb", "feat")
    (repo / "tests" / "data" / "in.xml").write_text("<b>←</b>\n", encoding="utf-8")   # el diff trae un no-cp1252
    _git(repo, "commit", "-qam", "cambia un fixture")
    (tmp_path / "r.toml").write_text("", encoding="utf-8")
    out, _ = _cp1252(monkeypatch)
    assert cm.main(["--check", "--root", str(repo), "--renames", str(tmp_path / "r.toml")]) == 1
    text = _text(out)
    assert "FALLA tests/data/in.xml" in text and "+<b>←</b>" in text, text
