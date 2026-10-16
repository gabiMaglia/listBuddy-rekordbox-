"""Marcadores `qt` y `posix` por convención (T-108, TEC-29), sin tocar 60 archivos de test.

El job de Windows corre `-m "not qt and not posix"`:
  qt    el test (o un helper/fixture que usa) abre GUI de Qt en otro intérprete (GUI_SNIPPET de _qt_isolated). Los que
        solo usan QtCore vía run_isolated (ExportWorker, sanitize, _safe_filename, os.replace) SÍ corren en Windows.
  posix el test depende de herramientas o permisos de macOS/Linux: bash, shasum, plutil, chmod/st_mode, symlinks, uid.
El job exporta LISTBUDDY_NO_QT=1: si un test mal clasificado intenta lanzar Qt, run_isolated falla fuerte.
"""
from __future__ import annotations

import inspect
import re
from types import FunctionType
from typing import Any, Callable

import pytest

from _qt_isolated import GUI_SNIPPET as _QT
_POSIX = re.compile(
    r"""["']bash["']|\bshasum\b|\bplutil\b|\bchmod\b|\bst_mode\b|\bS_IMODE\b|0o[0-7]{3}\b|\bsymlink|\bos\.link\b|\bgetuid\b|\bfcntl\b"""
)


def _src(fn: Callable[..., Any]) -> str:
    try:
        return inspect.getsource(fn)
    except (OSError, TypeError):
        return ""


def _closure(fn: Callable[..., Any], module_funcs: dict[str, FunctionType], consts: dict[str, str]) -> str:
    """Código de `fn` más el de los helpers del módulo que invoca (transitivo) y las constantes de texto que cita
    (los snippets de Qt suelen vivir en un `_PRE = \"\"\"...\"\"\"` del módulo)."""
    seen: set[str] = set()
    out: list[str] = []
    todo = [fn]
    while todo:
        cur = todo.pop()
        text = _src(cur)
        out.append(text)
        for name in set(re.findall(r"[A-Za-z_]\w*", text)):
            if name in consts and name not in seen:
                seen.add(name)
                out.append(consts[name])
            helper = module_funcs.get(name)
            if helper is not None and name not in seen:
                seen.add(name)
                todo.append(helper)
    return "\n".join(out)


def pytest_collection_modifyitems(config: pytest.Config, items: list[pytest.Item]) -> None:
    cache: dict[Any, tuple[dict[str, FunctionType], dict[str, str]]] = {}
    for item in items:
        fn = getattr(item, "function", None)
        module = getattr(item, "module", None)
        if fn is None or module is None:
            continue
        funcs, consts = cache.setdefault(module, (
            {n: f for n, f in vars(module).items() if isinstance(f, FunctionType) and f.__module__ == module.__name__},
            {n: v for n, v in vars(module).items() if isinstance(v, str)},
        ))
        text = _closure(fn, funcs, consts)
        # parámetros de texto (p. ej. nombre de módulo a importar): un `footer` parametrizado es GUI
        params = getattr(getattr(item, "callspec", None), "params", {})
        text += "\n" + "\n".join(f"import {v}" for v in params.values() if isinstance(v, str))
        fm = item.session._fixturemanager  # type: ignore[attr-defined]
        for name in getattr(item, "fixturenames", ()):
            for fdef in fm.getfixturedefs(name, item) or ():
                if getattr(fdef.func, "__module__", "") == module.__name__ or "conftest" in getattr(fdef.func, "__module__", ""):
                    text += "\n" + _closure(fdef.func, funcs, consts)
        if _QT.search(text):
            item.add_marker(pytest.mark.qt)
        if _POSIX.search(text):
            item.add_marker(pytest.mark.posix)
