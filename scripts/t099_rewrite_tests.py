# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2025-2026 Gabriel Maglia
"""T-099 (ADR-007 D5): reescribe en los tests las rutas de acceso que cambian al partir `ui.py`.

Cada renombre de `scripts/t099_renames.toml` cambia el atributo `.old` por `.new` (por ejemplo
`w._start_export()` → `w._export.start()`). Trabaja por tokens: en el código toca solo un NAME precedido por
un punto; en los literales de texto, f-strings y comentarios (los snippets de Qt viajan como texto) cambia
`.old` cuando no sigue un carácter de identificador. Una sola pasada, sin encadenar renombres: el resultado
depende únicamente del archivo de entrada y del mapa.

Uso:
    python scripts/t099_rewrite_tests.py                 # reescribe tests/**/*.py en el lugar
    python scripts/t099_rewrite_tests.py --check         # aplica el mapa a `main:tests/` y compara con la rama
    python scripts/t099_rewrite_tests.py --check --base origin/main

`--check` sale con 0 si cada test que existe en la base, reescrito, es idéntico al de la rama (los tests
nuevos de la rama no cuentan), y con 1 mostrando el diff si no.
"""
from __future__ import annotations

import argparse
import difflib
import io
import pathlib
import re
import subprocess
import sys
import tokenize
import tomllib
from typing import NamedTuple

REPO = pathlib.Path(__file__).resolve().parents[1]
DEFAULT_RENAMES = pathlib.Path(__file__).with_name("t099_renames.toml")

_PATH = re.compile(r"[A-Za-z_]\w*(?:\(\))?(?:\.[A-Za-z_]\w*(?:\(\))?)*")
_KEYS = {"old", "new", "phase", "note"}
_STARTS = {getattr(tokenize, n) for n in ("FSTRING_START", "TSTRING_START") if hasattr(tokenize, n)}
_ENDS = {getattr(tokenize, n) for n in ("FSTRING_END", "TSTRING_END") if hasattr(tokenize, n)}
_SKIP_FOR_PREV = {tokenize.NL, tokenize.NEWLINE, tokenize.COMMENT, tokenize.INDENT, tokenize.DEDENT}


class Rename(NamedTuple):
    old: str
    new: str


def load_renames(path: pathlib.Path) -> list[Rename]:
    with path.open("rb") as fh:
        data = tomllib.load(fh)
    out: list[Rename] = []
    seen: set[str] = set()
    for i, entry in enumerate(data.get("rename", [])):
        where = f"{path.name}: rename #{i + 1}"
        if not isinstance(entry, dict) or not {"old", "new"} <= set(entry) or set(entry) - _KEYS:
            raise ValueError(f"{where}: hace falta exactamente old/new (y opcionales phase/note)")
        old, new = entry["old"], entry["new"]
        if not isinstance(old, str) or not old.isidentifier():
            raise ValueError(f"{where}: old={old!r} tiene que ser un nombre de atributo")
        if not isinstance(new, str) or not _PATH.fullmatch(new):
            raise ValueError(f"{where}: new={new!r} tiene que ser una ruta tipo `_ctl.metodo` o `_ctl.items()`")
        if old in seen:
            raise ValueError(f"{where}: old={old!r} repetido")
        seen.add(old)
        out.append(Rename(old, new))
    return out


def rewrite(source: str, renames: list[Rename]) -> str:
    if not renames:
        return source
    table = {r.old: r.new for r in renames}
    alternatives = "|".join(re.escape(o) for o in sorted(table, key=len, reverse=True))
    in_text = re.compile(rf"(?<=\.)({alternatives})(?!\w)")
    # Columnas de tokenize = posición dentro de la línea tal como la corta readline (solo en "\n").
    line_start = [0] + [m.end() for m in re.finditer("\n", source)]

    def offset(pos: tuple[int, int]) -> int:
        return line_start[pos[0] - 1] + pos[1]

    edits: list[tuple[int, int, str]] = []

    def text_region(start: int, end: int) -> None:
        for m in in_text.finditer(source, start, end):
            edits.append((m.start(), m.end(), table[m.group(1)]))

    depth = 0
    region = 0
    prev: tokenize.TokenInfo | None = None
    for tok in tokenize.generate_tokens(io.StringIO(source, newline="\n").readline):
        if tok.type in _STARTS:
            if depth == 0:
                region = offset(tok.start)
            depth += 1
        elif tok.type in _ENDS:
            depth -= 1
            if depth == 0:
                text_region(region, offset(tok.end))
        elif depth:
            continue  # dentro de un f-string: lo cubre text_region entero
        elif tok.type in (tokenize.STRING, tokenize.COMMENT):
            text_region(offset(tok.start), offset(tok.end))
        elif (tok.type == tokenize.NAME and tok.string in table and prev is not None
              and prev.type == tokenize.OP and prev.string == "."):
            edits.append((offset(tok.start), offset(tok.end), table[tok.string]))
        if tok.type not in _SKIP_FOR_PREV and not depth:
            prev = tok

    out = source
    for start, end, new in sorted(edits, reverse=True):
        out = out[:start] + new + out[end:]
    return out


def _git(root: pathlib.Path, *args: str) -> str:
    r = subprocess.run(["git", "-C", str(root), *args], capture_output=True, encoding="utf-8")
    if r.returncode != 0:
        raise SystemExit(f"git {' '.join(args)} falló: {r.stderr.strip()}")
    return r.stdout


def check(root: pathlib.Path, base: str, renames: list[Rename]) -> int:
    paths = [p for p in _git(root, "ls-tree", "-r", "--name-only", base, "--", "tests").splitlines()
             if p.endswith(".py")]
    bad = 0
    for rel in paths:
        expected = rewrite(_git(root, "show", f"{base}:{rel}"), renames)
        target = root / rel
        if not target.is_file():
            print(f"✗ {rel}: existe en {base} y la rama lo borró")
            bad += 1
            continue
        actual = target.read_bytes().decode("utf-8")
        if actual != expected:
            bad += 1
            sys.stdout.writelines(difflib.unified_diff(
                expected.splitlines(keepends=True), actual.splitlines(keepends=True),
                fromfile=f"codemod({base}:{rel})", tofile=rel,
            ))
    if bad:
        print(f"✗ {bad} de {len(paths)} archivos de tests difieren de la salida del codemod")
        return 1
    print(f"OK: {len(paths)} archivos de tests de {base}, {len(renames)} renombres, diff vacío")
    return 0


def apply(files: list[pathlib.Path], renames: list[Rename]) -> int:
    for f in files:
        before = f.read_bytes().decode("utf-8")
        after = rewrite(before, renames)
        if after != before:
            f.write_bytes(after.encode("utf-8"))
            print(f"reescrito: {f}")
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("files", nargs="*", type=pathlib.Path, help="archivos a reescribir (default: tests/**/*.py)")
    ap.add_argument("--check", action="store_true", help="comparar la rama con el codemod aplicado a --base")
    ap.add_argument("--base", default="main", help="ref de git de referencia para --check (default: main)")
    ap.add_argument("--renames", type=pathlib.Path, default=DEFAULT_RENAMES)
    ap.add_argument("--root", type=pathlib.Path, default=REPO, help="raíz del repo (default: la de este script)")
    args = ap.parse_args(argv)
    renames = load_renames(args.renames)
    if args.check:
        return check(args.root, args.base, renames)
    files = args.files or sorted((args.root / "tests").rglob("*.py"))
    return apply(files, renames)


if __name__ == "__main__":
    sys.exit(main())
