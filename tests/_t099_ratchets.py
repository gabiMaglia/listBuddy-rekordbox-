# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2025-2026 Gabriel Maglia
"""T-099: trinquetes compartidos por los tests estáticos y el codemod.

Los valores viven en `tests/baselines/t099_ratchets.json` y no en los tests: así bajar un trinquete no es
«cambiar un test» (ADR-007 D5) y se puede verificar contra la base que solo bajó. La base es
`git merge-base HEAD main`; si ahí el archivo todavía no existe (la rama que lo crea), se compara contra el
commit que lo agregó.
"""
from __future__ import annotations

import json
import os
import pathlib
import subprocess
from typing import Any

ROOT = pathlib.Path(__file__).resolve().parents[1]
RATCHETS_REL = "tests/baselines/t099_ratchets.json"
BASE_REFS = ("main", "origin/main")

# Mismas exclusiones que T-120: lo que no es código de la app no se mide.
EXCLUDED_DIRS = frozenset({"tests", "scripts", "listBuddy_design", "engram", "build", "dist", "__pycache__"})

SIZE_KINDS = ("max_lines", "max_methods")
SET_KINDS = ("layer_edges", "layer_qt", "layer_cycles")
GROWING_KINDS = ("typed_modules",)
KINDS = frozenset(SIZE_KINDS + SET_KINDS + GROWING_KINDS)


class BaseUnavailable(RuntimeError):
    pass


def project_files(root: pathlib.Path = ROOT) -> dict[str, str]:
    """`ruta/relativa.py` → fuente, recorriendo subpaquetes."""
    out: dict[str, str] = {}
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = sorted(d for d in dirnames if d not in EXCLUDED_DIRS and not d.startswith("."))
        for name in sorted(filenames):
            if name.endswith(".py"):
                path = pathlib.Path(dirpath, name)
                out[path.relative_to(root).as_posix()] = path.read_text(encoding="utf-8")
    return out


def module_name(rel: str) -> str:
    parts = rel[:-3].split("/")
    if parts[-1] == "__init__":
        parts.pop()
    return ".".join(parts)


def parse(text: str) -> dict[str, Any]:
    data = json.loads(text)
    if not isinstance(data, dict) or set(data) != KINDS:
        raise ValueError(f"{RATCHETS_REL}: claves esperadas {sorted(KINDS)}, encontradas {sorted(data)}")
    return data


def load(root: pathlib.Path = ROOT) -> dict[str, Any]:
    return parse((root / RATCHETS_REL).read_text(encoding="utf-8"))


def _as_set(kind: str, value: list[Any]) -> set[Any]:
    if kind == "layer_cycles":
        return {frozenset(c) for c in value}
    if kind in SET_KINDS:
        return {tuple(e) for e in value}
    return set(value)


def monotonic_errors(base: dict[str, Any], current: dict[str, Any]) -> list[str]:
    """Lo que `current` hizo mal respecto de `base`: los techos y las allowlists solo bajan, la lista de
    módulos tipados solo crece."""
    errors: list[str] = []
    for kind in SIZE_KINDS:
        for key, value in sorted(current[kind].items()):
            if key not in base[kind]:
                errors.append(f"{kind}: {key} es nuevo en el trinquete (solo puede bajar)")
            elif value > base[kind][key]:
                errors.append(f"{kind}: {key} subió de {base[kind][key]} a {value} (solo puede bajar)")
    for kind in SET_KINDS:
        for item in sorted(_as_set(kind, current[kind]) - _as_set(kind, base[kind]), key=lambda x: sorted(x)):
            errors.append(f"{kind}: {sorted(item) if kind == 'layer_cycles' else list(item)} es nueva (solo puede achicarse)")
    for kind in GROWING_KINDS:
        for mod in sorted(set(base[kind]) - set(current[kind])):
            errors.append(f"{kind}: {mod} salió de la lista (solo puede crecer)")
    return errors


def _git(root: pathlib.Path, *args: str) -> subprocess.CompletedProcess[bytes]:
    return subprocess.run(["git", "-C", str(root), *args], capture_output=True)


def merge_base(root: pathlib.Path = ROOT, refs: tuple[str, ...] = BASE_REFS) -> str:
    for ref in refs:
        if _git(root, "rev-parse", "--verify", "--quiet", f"{ref}^{{commit}}").returncode != 0:
            continue
        r = _git(root, "merge-base", "HEAD", ref)
        if r.returncode == 0:
            return r.stdout.decode().strip()
    shallow = _git(root, "rev-parse", "--is-shallow-repository").stdout.decode().strip() == "true"
    raise BaseUnavailable(
        f"no encuentro la base de la rama (probé {', '.join(refs)}{'; el clon es superficial' if shallow else ''}). "
        "Traela con `git fetch origin main:main` (o `git fetch --unshallow`); en CI, `actions/checkout` con "
        "`fetch-depth: 0`."
    )


def base_ratchets(root: pathlib.Path = ROOT, refs: tuple[str, ...] = BASE_REFS) -> tuple[str, dict[str, Any]]:
    """(commit, trinquetes) contra los que se compara la rama."""
    base = merge_base(root, refs)
    shown = _git(root, "show", f"{base}:{RATCHETS_REL}")
    if shown.returncode == 0:
        return base, parse(shown.stdout.decode("utf-8"))
    added = _git(root, "log", "--diff-filter=A", "--format=%H", "--reverse", "HEAD", "--", RATCHETS_REL)
    first = added.stdout.decode().split()
    if not first:
        raise BaseUnavailable(f"{RATCHETS_REL} no está commiteado: commitealo para fijar la línea de base")
    return first[0], parse(_git(root, "show", f"{first[0]}:{RATCHETS_REL}").stdout.decode("utf-8"))
