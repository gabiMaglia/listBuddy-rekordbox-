"""Intérprete Qt reutilizable para los tests de ventana (T-075 / D-09).

Arrancar Python + PySide6 + fuentes cuesta ~2 s por test; acá se paga una vez por
worker de pytest. Sigue siendo un proceso APARTE del de pytest, así que el
aislamiento de binding (T-033: nunca dos copias de Qt en un proceso) se mantiene.

Protocolo: una línea JSON por pedido por stdin ({"code": ...}) y una línea JSON
de respuesta ({"rc", "stdout", "stderr"}) por el fd original de stdout.
"""
from __future__ import annotations

import contextlib
import io
import json
import os
import sys
import traceback
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QEvent, QTimer  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

import styles  # noqa: E402
import ui  # noqa: E402

app = QApplication([])
_fonts = styles.register_fonts()
styles.register_fonts = lambda: list(_fonts)  # registrar dos veces las mismas fuentes no aporta nada
styles.apply_theme(app, "dark")

def _project_modules() -> dict[str, Any]:
    out = {}
    for name, mod in list(sys.modules.items()):
        f = getattr(mod, "__file__", None)
        if f and Path(f).resolve().parent == ROOT:
            out[name] = mod
    return out


def _classes(mods: dict[str, Any]) -> dict[int, type]:
    found: dict[int, type] = {}
    for mod in mods.values():
        for v in list(vars(mod).values()):
            if isinstance(v, type):
                found[id(v)] = v
    return found


def _snapshot() -> tuple[dict[str, dict[str, Any]], dict[int, tuple[type, dict[str, Any]]]]:
    mods = _project_modules()
    msnap = {n: dict(vars(m)) for n, m in mods.items()}
    csnap = {i: (c, dict(vars(c))) for i, c in _classes(mods).items()}
    return msnap, csnap


def _restore(snap: tuple[dict[str, dict[str, Any]], dict[int, tuple[type, dict[str, Any]]]]) -> None:
    msnap, csnap = snap
    # módulos del proyecto importados por el snippet: se descartan para no heredar sus parches
    for name in set(_project_modules()) - set(msnap):
        sys.modules.pop(name, None)
    for name, saved in msnap.items():
        d = vars(sys.modules[name])
        for k in set(d) - set(saved):
            del d[k]
        for k, v in saved.items():
            if d.get(k, _MISSING) is not v:
                d[k] = v
    for cls, saved in csnap.values():
        now = dict(vars(cls))
        for k in set(now) - set(saved):
            with contextlib.suppress(Exception):
                delattr(cls, k)
        for k, v in saved.items():
            if k.startswith("__") or now.get(k, _MISSING) is v:
                continue
            with contextlib.suppress(Exception):
                setattr(cls, k, v)


_MISSING = object()


def _quiesce() -> None:
    wins = QApplication.topLevelWidgets()
    for w in wins:
        for t in w.findChildren(QTimer):
            t.stop()
        w.hide()
    with contextlib.suppress(Exception):
        app.processEvents()  # que los singleShot pendientes corran con la ventana aún viva
    for w in wins:
        w.deleteLater()
    with contextlib.suppress(Exception):
        app.sendPostedEvents(None, QEvent.Type.DeferredDelete.value)
        app.processEvents()


def _serve() -> None:
    out = os.fdopen(os.dup(1), "w")
    os.dup2(2, 1)  # un print del código de Qt no debe contaminar el canal de respuestas
    base = _snapshot()
    for line in sys.stdin:
        req = json.loads(line)
        buf_out, buf_err = io.StringIO(), io.StringIO()
        rc = 0
        with contextlib.redirect_stdout(buf_out), contextlib.redirect_stderr(buf_err):
            try:
                exec(compile(req["code"], "<snippet>", "exec"), {"__name__": "__main__"})
            except SystemExit as e:
                rc = e.code if isinstance(e.code, int) else 1
            except BaseException:
                traceback.print_exc()
                rc = 1
        try:
            _quiesce()
        finally:
            _restore(base)  # antes de re-aplicar el tema: el snippet pudo espiar load_qss
        styles.apply_theme(app, "dark")
        out.write(json.dumps({"rc": rc, "stdout": buf_out.getvalue(), "stderr": buf_err.getvalue()}) + "\n")
        out.flush()
    os._exit(0)


if __name__ == "__main__":
    _serve()
