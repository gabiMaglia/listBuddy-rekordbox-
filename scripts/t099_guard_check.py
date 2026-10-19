# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2025-2026 Gabriel Maglia
"""T-099: paso de CI de las barandas, fuera de pytest (corre ANTES de pytest en `.github/workflows/tests.yml`).

Por qué existe: cualquier chequeo que corra dentro de pytest lo puede sabotear otro test del mismo repo (parchear
`subprocess.run` o `Path.read_text` al importarse, tapar la stdlib desde `tests/`). Este script es un proceso
propio (`python -I`) que no importa nada de `tests/`:
  1. Calcula el merge-base de HEAD con `main` (o `origin/main`).
  2. Saca de git, a una carpeta temporal, el código de las barandas (`tests/_t099_guard.py`, `_t099_ratchets.py`,
     `_t099_measure.py`, `test_module_size.py`, `test_import_layers.py`, `test_type_hints.py`) y el
     `scripts/t099_rewrite_tests.py` en la versión de la BASE. Si la base todavía no los tiene (la rama que los
     crea), usa los de HEAD, también desde git y no del working tree. Los trinquetes y el mapa de renombres van
     de HEAD: son los datos que se están revisando.
  3. Corre las seis barandas (`_t099_guard.py --all`, que carga los módulos por ruta) sobre el árbol del repo.
  4. Con `--with-check` (ramas `feat/t099-*`) corre también el `--check` del codemod de la BASE (ADR-007 D5;
     cierra D-5 de la verificación ciega 2) y, si la base ya tiene las barandas, exige `.github/` idéntico a la
     base (D-6).
Sale 0 si todo está en verde y 1 si no (2 ante un error de entorno, por ejemplo sin la ref base).

Límite: el workflow y este script se ejecutan en la versión de HEAD. Que una PR no los vacíe lo cuida la revisión
del diff de `.github/` y `scripts/t099_guard_check.py` (y, en ramas T-099, el punto 4).
"""
from __future__ import annotations

import argparse
import pathlib
import subprocess
import sys
import tempfile

REPO = pathlib.Path(__file__).resolve().parents[1]
GUARD_TESTS = ("_t099_guard.py", "_t099_ratchets.py", "_t099_measure.py", "test_module_size.py",
               "test_import_layers.py", "test_type_hints.py")
CHECK_SCRIPT = "scripts/t099_rewrite_tests.py"
RATCHETS = "tests/baselines/t099_ratchets.json"
RENAMES = "scripts/t099_renames.toml"


def _git(root: pathlib.Path, *args: str) -> subprocess.CompletedProcess[bytes]:
    return subprocess.run(["git", "-C", str(root), *args], capture_output=True)


def merge_base(root: pathlib.Path, ref: str) -> str:
    refs = (ref, "origin/main") if ref == "main" else (ref,)
    for r in refs:
        if _git(root, "rev-parse", "--verify", "--quiet", f"{r}^{{commit}}").returncode == 0:
            mb = _git(root, "merge-base", "HEAD", r)
            if mb.returncode == 0:
                return mb.stdout.decode().strip()
    raise SystemExit(f"error: no encuentro la base (probé {', '.join(refs)}). Traela con `git fetch origin main:main`;"
                     " en CI, `actions/checkout` con `fetch-depth: 0`.")


def _blob(root: pathlib.Path, rev: str, rel: str) -> bytes | None:
    r = _git(root, "show", f"{rev}:{rel}")
    return r.stdout if r.returncode == 0 else None


def _materialize(root: pathlib.Path, base: str, out: pathlib.Path) -> None:
    for rel in [f"tests/{n}" for n in GUARD_TESTS] + [CHECK_SCRIPT]:
        data = _blob(root, base, rel)
        origin = f"base {base[:10]}"
        if data is None:
            data, origin = _blob(root, "HEAD", rel), "HEAD (la base todavía no lo tiene)"
        if data is None:
            raise SystemExit(f"error: {rel} no está ni en la base ni en HEAD")
        print(f"· {rel} ← {origin}")
        (out / rel).parent.mkdir(parents=True, exist_ok=True)
        (out / rel).write_bytes(data)
    for rel in (RATCHETS, RENAMES):
        data = _blob(root, "HEAD", rel)
        if data is None:
            raise SystemExit(f"error: {rel} no está commiteado en HEAD")
        (out / rel).parent.mkdir(parents=True, exist_ok=True)
        (out / rel).write_bytes(data)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--base", default="main", help="ref cuyo merge-base con HEAD es la base (default: main)")
    ap.add_argument("--root", type=pathlib.Path, default=REPO)
    ap.add_argument("--with-check", action="store_true", help="correr también el --check del codemod de la base")
    args = ap.parse_args(argv)
    root = args.root.resolve()
    base = merge_base(root, args.base)
    failed = False
    with tempfile.TemporaryDirectory(prefix="t099-guard-") as tmp:
        work = pathlib.Path(tmp)
        _materialize(root, base, work)
        guard = subprocess.run([sys.executable, "-I", str(work / "tests" / "_t099_guard.py"), "--all", str(root)],
                               capture_output=True, text=True, encoding="utf-8")
        sys.stdout.write(guard.stdout)
        sys.stderr.write(guard.stderr)
        failed |= guard.returncode != 0
        if args.with_check:
            check = subprocess.run([sys.executable, "-I", str(work / CHECK_SCRIPT), "--check", "--root", str(root),
                                    "--base", args.base, "--renames", str(work / RENAMES)],
                                   capture_output=True, text=True, encoding="utf-8")
            sys.stdout.write(check.stdout)
            sys.stderr.write(check.stderr)
            failed |= check.returncode != 0
            if _blob(root, base, "tests/_t099_guard.py") is not None:
                if _git(root, "diff", "--quiet", base, "HEAD", "--", ".github").returncode != 0:
                    print("✗ .github/ cambió respecto de la base: una rama T-099 no toca CI (D-6)")
                    failed = True
    print("✗ barandas T-099 en rojo" if failed else "OK: barandas T-099 en verde")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
