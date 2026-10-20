# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2025-2026 Gabriel Maglia
"""T-099: trinquetes compartidos por los tests estáticos y el codemod.

Los valores viven en `tests/baselines/t099_ratchets.json` y no en los tests: así bajar un trinquete no es
«cambiar un test» (ADR-007 D5) y se puede verificar contra la base que solo bajó. La base es
`git merge-base HEAD main`. Si ahí el JSON ya existe, manda ese JSON. Si todavía no existe (la rama que lo
crea), manda lo MEDIDO sobre el árbol del merge-base (ADR-007 Addendum 1, nota): un JSON nuevo no puede
declarar un techo mayor que la realidad de main, y lo que main cambie antes de que el JSON entre no rompe
nada. `typed_modules` no se puede medir (es un compromiso, no una medida): su piso es el primer JSON
commiteado en la rama.
"""
from __future__ import annotations

import json
import os
import pathlib
import subprocess
import sys
from typing import Any, Callable

ROOT = pathlib.Path(__file__).resolve().parents[1]
RATCHETS_REL = "tests/baselines/t099_ratchets.json"
BASE_REFS = ("main", "origin/main")

# Mismas exclusiones que T-120: lo que no es código de la app no se mide. `build/` y `dist/` son salidas de
# PyInstaller y solo se saltean cuando no están en git (ignoradas): si alguien los commitea con `git add -f`,
# son paquetes importables como cualquier otro y se miden.
EXCLUDED_DIRS = frozenset({"tests", "scripts", "listBuddy_design", "engram", "__pycache__"})
BUILD_DIRS = frozenset({"build", "dist"})
# Carpetas que no se miden pero son importables (namespace packages): si un módulo medido trae código de ahí, ese
# código esquivaría tamaño, capas y conteo de métodos. Importarlas desde la app es una violación.
UNMEASURED_DIRS = frozenset((EXCLUDED_DIRS - {"__pycache__"}) | BUILD_DIRS)

SIZE_KINDS = ("max_lines", "max_methods")
SET_KINDS = ("layer_edges", "layer_qt", "layer_cycles")
GROWING_KINDS = ("typed_modules",)
# Capas de módulos NUEVOS, declaradas por la PR que los crea (Y9). Una vez en la base no cambian ni se quitan.
LAYER_KIND = "module_layers"
KINDS = frozenset(SIZE_KINDS + SET_KINDS + GROWING_KINDS + (LAYER_KIND,))


class BaseUnavailable(RuntimeError):
    pass


def project_files(root: pathlib.Path = ROOT) -> dict[str, str]:
    """`ruta/relativa.py` → fuente, recorriendo subpaquetes.

    En un repo git mide lo que se commitearía: lo trackeado (aunque esté ignorado, `git add -f`) más lo nuevo
    no ignorado. Fuera de git recorre el disco y saltea `build/`/`dist/` del primer nivel."""
    top = _git(root, "rev-parse", "--show-toplevel")
    if top.returncode == 0 and pathlib.Path(top.stdout.decode().strip()).resolve() == root.resolve():
        listed = _git(root, "ls-files", "-z", "--cached", "--others", "--exclude-standard").stdout
        out_git: dict[str, str] = {}
        for rel in sorted(set(listed.decode("utf-8").split("\0")) - {""}):
            path = root / rel
            if rel.endswith(".py") and not _excluded(rel) and path.is_file():
                out_git[rel] = path.read_text(encoding="utf-8")
        return out_git
    out: dict[str, str] = {}
    for dirpath, dirnames, filenames in os.walk(root):
        first_level = pathlib.Path(dirpath) == root
        dirnames[:] = sorted(d for d in dirnames if d not in EXCLUDED_DIRS and not d.startswith(".")
                             and not (first_level and d in BUILD_DIRS))
        for name in sorted(filenames):
            if name.endswith(".py"):
                path = pathlib.Path(dirpath, name)
                out[path.relative_to(root).as_posix()] = path.read_text(encoding="utf-8")
    return out


def unmeasured_import(name: str, modules: set[str] | frozenset[str]) -> str | None:
    """Si `name` (`a.b.c`) apunta a código de una carpeta no medida, devuelve esa carpeta; si no, None.

    Un módulo o paquete medido que lo cubra (`build.ctl` commiteado) gana; un nombre ajeno (`numpy.testing`)
    no cuenta."""
    parts = name.split(".")
    for k in range(len(parts), 0, -1):
        prefix = ".".join(parts[:k])
        if prefix in modules or any(m.startswith(prefix + ".") for m in modules):
            return parts[k] if k < len(parts) and parts[k] in UNMEASURED_DIRS else None
    return parts[0] if parts[0] in UNMEASURED_DIRS else None


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
    for mod, layer in sorted(base[LAYER_KIND].items()):
        if mod not in current[LAYER_KIND]:
            errors.append(f"{LAYER_KIND}: {mod} salió (una capa declarada no se quita)")
        elif current[LAYER_KIND][mod] != layer:
            errors.append(f"{LAYER_KIND}: {mod} cambió de L{layer} a L{current[LAYER_KIND][mod]} "
                          "(reclasificar no se puede desde la PR)")
    for mod, layer in sorted(current[LAYER_KIND].items()):
        if not isinstance(layer, int) or not 0 <= layer <= 6:
            errors.append(f"{LAYER_KIND}: {mod} tiene una capa inválida ({layer!r}): va de 0 a 6")
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


def _excluded(rel: str) -> bool:
    return any(d in EXCLUDED_DIRS or d.startswith(".") for d in rel.split("/")[:-1])


def tree_files(root: pathlib.Path, rev: str) -> dict[str, str]:
    """Lo mismo que `project_files`, pero del árbol de `rev` en git."""
    listed = _git(root, "ls-tree", "-r", "--name-only", rev).stdout.decode("utf-8").splitlines()
    return {rel: _git(root, "show", f"{rev}:{rel}").stdout.decode("utf-8")
            for rel in sorted(listed) if rel.endswith(".py") and not _excluded(rel)}


Measure = Callable[[dict[str, str]], dict[str, Any]]


def base_ratchets(root: pathlib.Path = ROOT, refs: tuple[str, ...] = BASE_REFS,
                  measure: Measure | None = None) -> tuple[str, dict[str, Any]]:
    """(commit, trinquetes) contra los que se compara la rama: el JSON del merge-base o, si ahí no existe,
    lo medido sobre ese árbol."""
    base = merge_base(root, refs)
    shown = _git(root, "show", f"{base}:{RATCHETS_REL}")
    if shown.returncode == 0:
        return base, parse(shown.stdout.decode("utf-8"))
    if measure is None:
        from _t099_measure import measure_ratchets   # perezoso: _t099_measure importa los tests que usan este módulo
        measure = measure_ratchets
    measured = measure(tree_files(root, base))
    added = _git(root, "log", "--diff-filter=A", "--format=%H", "--reverse", "HEAD", "--", RATCHETS_REL)
    first = added.stdout.decode().split()
    measured["typed_modules"] = (
        # Sin parse(): el primer JSON de la rama puede tener un esquema anterior (sin `module_layers`).
        json.loads(_git(root, "show", f"{first[0]}:{RATCHETS_REL}").stdout.decode("utf-8"))["typed_modules"]
        if first else []
    )
    return base, parse(json.dumps(measured))


GUARD_SCRIPT = pathlib.Path(__file__).with_name("_t099_guard.py")


def run_guard(kind: str, root: pathlib.Path = ROOT) -> list[str]:
    """Corre una baranda en un intérprete propio (`python -I`): nada que otro test haga en este proceso
    (parchear `root_sources`, las constantes, los módulos) llega a la medición. El resultado sí se lee desde el
    proceso de pytest, que un test puede sabotear (`subprocess.run`): por eso la garantía es el paso de CI
    `scripts/t099_guard_check.py`, no esto."""
    r = subprocess.run([sys.executable, "-I", str(GUARD_SCRIPT), kind, str(root)], capture_output=True,
                       text=True, encoding="utf-8", timeout=300)
    if r.returncode != 0:
        return [f"la baranda {kind} no corrió (exit {r.returncode}): {r.stderr.strip()[-2000:]}"]
    return json.loads(r.stdout)


def new_layer_errors(root: pathlib.Path, base: str, base_data: dict[str, Any], current: dict[str, Any]) -> list[str]:
    """Las entradas de `module_layers` que agrega la PR solo valen para módulos que la PR crea."""
    added = sorted(set(current[LAYER_KIND]) - set(base_data[LAYER_KIND]))
    if not added:
        return []
    in_base = {module_name(rel) for rel in tree_files(root, base)}
    in_head = {module_name(rel) for rel in project_files(root)}
    errors: list[str] = []
    for mod in added:
        if mod in in_base:
            errors.append(f"{LAYER_KIND}: {mod} ya existe en la base (reclasificar no se puede desde la PR)")
        elif mod not in in_head:
            errors.append(f"{LAYER_KIND}: {mod} no existe en HEAD (capa sin módulo)")
    return errors
