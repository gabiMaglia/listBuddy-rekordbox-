# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2025-2026 Gabriel Maglia
"""T-099 (ADR-007 D5): reescribe en los tests las rutas de acceso que cambian al partir `ui.py`.

Cada renombre de `scripts/t099_renames.toml` cambia el atributo `.old` por `.new` (por ejemplo
`w._start_export()` → `w._export.start()`):
  - en el código, un NAME precedido por un punto (no en sentencias `import`/`from`);
  - en literales de texto, f-strings y comentarios (los snippets de Qt viajan como texto), `.old` aunque haya
    espacios después del punto, salvo en un renglón que empieza con `import`/`from`;
  - en `getattr/setattr/hasattr/delattr(obj, "old")`, `patch.object(obj, "old")` y
    `monkeypatch.setattr/delattr(obj, "old")`: `obj` pasa a `obj.<prefijo>` y el texto, al último tramo.
Falla (exit 2, sin escribir nada) si un `new` terminado en `()` queda como destino de una asignación o `del`,
si queda un `"old"` entre comillas que no sabe reescribir, o si el archivo no se puede tokenizar. Una sola
pasada, sin encadenar renombres: el resultado depende solo del archivo y del mapa.

Uso:
    python scripts/t099_rewrite_tests.py                 # reescribe tests/**/*.py del working tree
    python scripts/t099_rewrite_tests.py --check         # base = merge-base(HEAD, main); compara contra HEAD

`--check` recorre todo `tests/` de la base y `pytest.ini`/`conftest.py`/`pyproject.toml`/`setup.cfg`/
`tox.ini` de la raíz, contra lo commiteado en HEAD:
  - `.py` de `tests/`: HEAD tiene que ser exactamente el codemod de la base;
  - `tests/baselines/t099_ratchets.json`: solo puede bajar (trinquetes) o crecer (`typed_modules`);
  - todo lo demás (fixtures, configuración): idéntico byte a byte;
  - un archivo borrado o un `conftest.py`/configuración nuevos cuentan como diferencia; otros archivos nuevos
    (tests nuevos y sus fixtures) no.
  - un archivo nuevo en `tests/` que se llama como un módulo de la stdlib o de un paquete instalado
    (`tests/ast.py`, `tests/numpy.py`, `tests/pathlib/…`) cuenta como diferencia;
  - un test nuevo que nombra un módulo de barandas (`test_module_size`, `test_import_layers`,
    `test_type_hints`, `_t099_ratchets`, `_t099_measure`, `_t099_guard`) cuenta como diferencia.
Sale con 0 si no hay diferencias, 1 si las hay (mostrando el diff) y 2 ante un error.

Deuda declarada (verificación ciega 2, `engram/qa/T-099-F0-verifier2.md`); hasta cerrarla, lo cubre QA a mano:
  - D-3: `old` solo tiene que ser un identificador; un renombre semántico (`isChecked` → `isEnabled`) cambia
    aserciones y `--check` sale 0. QA revisa que cada entrada del mapa sea una ruta privada (`_…`).
  - D-5: `--check` corre el script y el mapa de HEAD; `scripts/` no se compara contra la base. QA corre el
    `--check` de la base: `git show <merge-base>:scripts/t099_rewrite_tests.py > /tmp/ck.py` y lo ejecuta con
    `--root .`.
  - D-6: CI no corre `--check` y `--check` no mira `.github/`: un `--deselect` en el workflow se ve solo en el
    diff de la PR.
  - D-7: el chequeo de destino no ve tuplas, `for`, `with` ni anotados (`w._x, b = …`, `for w._x in …`), ni
    reescribe kwargs (`SimpleNamespace(_x=1)`) ni rutas en texto (`patch('ui.MainWindow._x')`). Falla ruidosa
    (código inválido o error en runtime), no pasa en verde.
"""
from __future__ import annotations

import argparse
import difflib
import importlib.metadata
import io
import json
import pathlib
import re
import subprocess
import sys
import tokenize
import tomllib
from typing import NamedTuple

REPO = pathlib.Path(__file__).resolve().parents[1]
DEFAULT_RENAMES = pathlib.Path(__file__).with_name("t099_renames.toml")
sys.path.insert(0, str(REPO / "tests"))
from _t099_ratchets import (RATCHETS_REL, BaseUnavailable, base_ratchets, merge_base,  # noqa: E402
                            monotonic_errors, parse)

CONFIG_FILES = ("pytest.ini", "conftest.py", "pyproject.toml", "setup.cfg", "tox.ini")
# Las barandas de T-099. Un test NUEVO no puede nombrarlas (importarlas o parchearlas): si pudiera, dejaría crecer
# `ui.py` en verde. Los archivos que las implementan sí pueden ser nuevos (es la rama que las crea).
GUARD_MODULES = ("test_module_size", "test_import_layers", "test_type_hints", "_t099_ratchets", "_t099_measure",
                 "_t099_guard")
GUARD_FILES = frozenset({f"tests/{m}.py" for m in GUARD_MODULES} | {"tests/test_t099_ratchets.py",
                                                                     "tests/test_t099_rewrite_tests.py",
                                                                     "tests/test_t099_guard_check.py",
                                                                     "tests/test_t099_unmeasured.py",
                                                                     "tests/test_t099_new_layers.py"})


def shadowable_names() -> frozenset[str]:
    """Nombres que un archivo de `tests/` no puede tomar: con `tests/` en `sys.path` (pytest lo pone) taparían a
    la stdlib o a un paquete instalado."""
    installed = set(importlib.metadata.packages_distributions())
    # El paso de CI corre con `-S` y antes de instalar: ahí no hay site-packages, así que se suman los nombres del
    # lock (`requirements*.txt` del repo) y los bindings de Qt, que no se llaman como su distribución.
    for req in REPO.glob("requirements*.txt"):
        for line in req.read_text(encoding="utf-8").splitlines():
            m = re.match(r"([A-Za-z0-9][A-Za-z0-9._-]*)==", line)
            if m:
                installed.add(m.group(1).replace("-", "_"))
    installed |= {"PySide6", "shiboken6", "PyQt6", "xdist", "_pytest", "pytest"}
    return frozenset(n.lower() for n in sys.stdlib_module_names) | frozenset(n.lower() for n in installed)


_GUARD_NAME = re.compile(r"\b(" + "|".join(GUARD_MODULES) + r")\b")

_PATH = re.compile(r"[A-Za-z_]\w*(?:\(\))?(?:\.[A-Za-z_]\w*(?:\(\))?)*")
_KEYS = {"old", "new", "phase", "note"}
_STARTS = {getattr(tokenize, n) for n in ("FSTRING_START", "TSTRING_START") if hasattr(tokenize, n)}
_ENDS = {getattr(tokenize, n) for n in ("FSTRING_END", "TSTRING_END") if hasattr(tokenize, n)}
_ATTR_CALLS = r"(?:getattr|setattr|hasattr|delattr|patch\.object|monkeypatch\.setattr|monkeypatch\.delattr)"
_ASSIGN_AFTER = re.compile(r"[ \t]*(?:\*\*|//|<<|>>|[-+*/%&|^@])?=(?!=)")


class Rename(NamedTuple):
    old: str
    new: str


class RewriteError(ValueError):
    pass


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


def _segment_before(source: str, pos: int) -> str:
    """Texto del «renglón» de código que termina en `pos`, cortando también en `\\n` escrito dentro de un
    literal, en comillas y en `;` (así sirve igual para código y para snippets en texto)."""
    cut = max(source.rfind(c, 0, pos) for c in ("\n", "\\n", '"', "'", ";"))
    return source[cut + 1:pos] if cut >= 0 else source[:pos]


def rewrite(source: str, renames: list[Rename], filename: str = "<src>") -> str:
    if not renames:
        return source
    table = {r.old: r.new for r in renames}
    alternatives = "|".join(re.escape(o) for o in sorted(table, key=len, reverse=True))
    in_text = re.compile(rf"\.[ \t]*({alternatives})(?!\w)")
    quoted = re.compile(rf"\\?(['\"])({alternatives})\\?\1")
    attr_call = re.compile(
        rf"\b{_ATTR_CALLS}\(\s*([A-Za-z_][\w.]*(?:\[[^\[\]()\n]*\])*)(\s*,\s*)(\\?(['\"])({alternatives})\\?\4)")
    line_start = [0] + [m.end() for m in re.finditer("\n", source)]

    def offset(pos: tuple[int, int]) -> int:
        return line_start[pos[0] - 1] + pos[1]

    def line_of(pos: int) -> int:
        return source.count("\n", 0, pos) + 1

    edits: list[tuple[int, int, str]] = []

    def store_check(start: int, end: int, old: str) -> None:
        if not table[old].endswith("()"):
            return
        if _ASSIGN_AFTER.match(source, end) or re.search(r"\bdel[ \t]+\S*$", _segment_before(source, start)):
            raise RewriteError(f"{filename}:{line_of(start)}: «{old}» → «{table[old]}» quedaría como destino de "
                               "una asignación o `del`: hace falta otra ruta en el mapa")

    def text_region(start: int, end: int) -> None:
        for m in in_text.finditer(source, start, end):
            if re.match(r"\s*(?:import|from)\s", _segment_before(source, m.start())):
                continue
            store_check(m.start(1), m.end(1), m.group(1))
            edits.append((m.start(1), m.end(1), table[m.group(1)]))

    try:
        tokens = list(tokenize.generate_tokens(io.StringIO(source, newline="\n").readline))
    except (tokenize.TokenError, SyntaxError) as e:
        raise RewriteError(f"{filename}: no se puede tokenizar ({e})") from e

    depth = 0
    region = 0
    prev: tokenize.TokenInfo | None = None
    in_import = False
    for tok in tokens:
        if tok.type in (tokenize.NEWLINE, tokenize.ENDMARKER) or (tok.type == tokenize.OP and tok.string == ";"):
            in_import = False
        elif (tok.type == tokenize.NAME and tok.string in ("import", "from") and not depth
              and (prev is None or prev.type in (tokenize.NEWLINE, tokenize.INDENT, tokenize.DEDENT)
                   or (prev.type == tokenize.OP and prev.string == ";"))):
            in_import = True
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
        elif (tok.type == tokenize.NAME and tok.string in table and not in_import and prev is not None
              and prev.type == tokenize.OP and prev.string == "."):
            store_check(offset(tok.start), offset(tok.end), tok.string)
            edits.append((offset(tok.start), offset(tok.end), table[tok.string]))
        if tok.type not in (tokenize.NL, tokenize.COMMENT) and not depth:
            prev = tok

    handled: set[int] = set()
    for m in attr_call.finditer(source):
        old = m.group(5)
        *prefix, last = table[old].split(".")
        if last.endswith("()"):
            raise RewriteError(f"{filename}:{line_of(m.start())}: «{old}» → «{table[old]}» por texto en "
                               f"`{m.group(0)}`: el último tramo es una llamada, hace falta otra ruta")
        if prefix:
            edits.append((m.end(1), m.end(1), "." + ".".join(prefix)))
        lit = m.group(3)
        edits.append((m.start(3), m.end(3), lit.replace(old, last, 1)))
        handled.add(m.start(3))
    for m in quoted.finditer(source):
        if m.start() not in handled:
            raise RewriteError(f"{filename}:{line_of(m.start())}: «{m.group(0)}» nombra por texto un atributo "
                               "renombrado y el codemod no sabe reescribir ese uso: hacelo a mano o cambiá el mapa")

    out = source
    for start, end, new in sorted(edits, reverse=True):
        out = out[:start] + new + out[end:]
    return out


def _git(root: pathlib.Path, *args: str) -> bytes:
    r = subprocess.run(["git", "-C", str(root), *args], capture_output=True)
    if r.returncode != 0:
        raise RewriteError(f"git {' '.join(args)} falló: {r.stderr.decode(errors='replace').strip()}")
    return r.stdout


def _tree(root: pathlib.Path, rev: str) -> set[str]:
    paths = set(_git(root, "ls-tree", "-r", "--name-only", rev, "--", "tests").decode("utf-8").splitlines())
    paths |= set(_git(root, "ls-tree", "--name-only", rev, "--", *CONFIG_FILES).decode("utf-8").splitlines())
    return paths


def _diff(expected: str, actual: str, base: str, rel: str) -> None:
    sys.stdout.writelines(difflib.unified_diff(
        expected.splitlines(keepends=True), actual.splitlines(keepends=True),
        fromfile=f"codemod({base[:10]}:{rel})", tofile=f"HEAD:{rel}",
    ))


def check(root: pathlib.Path, ref: str, renames: list[Rename]) -> int:
    refs = (ref, "origin/main") if ref == "main" else (ref,)
    base = merge_base(root, refs)
    before, after = _tree(root, base), _tree(root, "HEAD")
    bad = 0
    for rel in sorted(before):
        if rel not in after:
            print(f"✗ {rel}: existe en la base y HEAD lo borró")
            bad += 1
            continue
        if rel == RATCHETS_REL:
            continue   # se valida abajo, también en la rama que lo crea
        old_b, new_b = _git(root, "show", f"{base}:{rel}"), _git(root, "show", f"HEAD:{rel}")
        if rel.startswith("tests/") and rel.endswith(".py"):
            expected = rewrite(old_b.decode("utf-8"), renames, f"{base[:10]}:{rel}")
            actual = new_b.decode("utf-8")
            if actual != expected:
                _diff(expected, actual, base, rel)
                bad += 1
        elif old_b != new_b:
            print(f"✗ {rel}: no es un test .py y cambió (tiene que quedar idéntico byte a byte)")
            try:
                _diff(old_b.decode("utf-8"), new_b.decode("utf-8"), base, rel)
            except UnicodeDecodeError:
                pass
            bad += 1
    if RATCHETS_REL in after:
        # Mismo ancla que tests/test_t099_ratchets.py: el merge-base o, si ahí no existe, el commit que lo agregó.
        anchor, old_data = base_ratchets(root, refs)
        errors = monotonic_errors(old_data, parse(_git(root, "show", f"HEAD:{RATCHETS_REL}").decode("utf-8")))
        for e in errors:
            print(f"✗ {RATCHETS_REL} (contra {anchor[:10]}): {e}")
        bad += bool(errors)
    shadow = shadowable_names()
    for rel in sorted(after - before):
        first = rel.split("/")[1] if rel.startswith("tests/") and rel.count("/") >= 1 else ""
        top = first[:-3] if first.endswith(".py") else first
        if top.lower() in shadow and (rel.endswith(".py") or "/" in rel[len("tests/"):]):
            print(f"✗ {rel}: se llama como un módulo de la stdlib o de un paquete instalado ({top}): con `tests/` "
                  "en el path lo taparía")
            bad += 1
            continue
        if rel.rsplit("/", 1)[-1] in CONFIG_FILES:
            print(f"✗ {rel}: configuración de pytest nueva (cambia qué se recolecta o cómo corre)")
            bad += 1
        elif rel.startswith("tests/") and rel.endswith(".py") and rel not in GUARD_FILES:
            hit = _GUARD_NAME.search(_git(root, "show", f"HEAD:{rel}").decode("utf-8", errors="replace"))
            if hit:
                print(f"✗ {rel}: test nuevo que nombra un módulo de barandas ({hit.group(1)}): no puede "
                      "importarlo ni parchearlo")
                bad += 1
    status = subprocess.run(["git", "-C", str(root), "status", "--porcelain", "--", "tests", *CONFIG_FILES],
                            capture_output=True, text=True).stdout.strip()
    if status:
        print("aviso: hay cambios sin commitear en tests/ o en la configuración; --check mira solo HEAD")
    if bad:
        print(f"✗ {bad} archivos difieren de la base {base[:10]} + codemod")
        return 1
    print(f"OK: {len(before)} archivos de la base {base[:10]} ({ref}), {len(renames)} renombres, diff vacío")
    return 0


def apply(files: list[pathlib.Path], renames: list[Rename]) -> int:
    new_text: dict[pathlib.Path, str] = {}
    for f in files:   # todo o nada: si un archivo da error no se escribe ninguno
        before = f.read_bytes().decode("utf-8")
        after = rewrite(before, renames, str(f))
        if after != before:
            new_text[f] = after
    for f, text in new_text.items():
        f.write_bytes(text.encode("utf-8"))
        print(f"reescrito: {f}")
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("files", nargs="*", type=pathlib.Path, help="archivos a reescribir (default: tests/**/*.py)")
    ap.add_argument("--check", action="store_true", help="comparar HEAD con el codemod aplicado a la base")
    ap.add_argument("--base", default="main", help="ref cuyo merge-base con HEAD es la base (default: main)")
    ap.add_argument("--renames", type=pathlib.Path, default=DEFAULT_RENAMES)
    ap.add_argument("--root", type=pathlib.Path, default=REPO, help="raíz del repo (default: la de este script)")
    args = ap.parse_args(argv)
    try:
        renames = load_renames(args.renames)
        if args.check:
            return check(args.root, args.base, renames)
        files = args.files or sorted((args.root / "tests").rglob("*.py"))
        return apply(files, renames)
    except (RewriteError, BaseUnavailable, ValueError) as e:
        print(f"error: {e}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
