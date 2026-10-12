"""T-070: mide cuánto tarda MainWindow._apply_theme con playlists marcadas y vista previa llena.

Uso: python scripts/measure_theme_switch.py [--n 8] [--rounds 6] [--json out.json]
Solo lectura sobre la librería real (Rekordbox/Traktor según el ini del usuario NO se toca:
se usa un ini temporal y la DB se abre como la abre la app). No persiste nada.
"""
from __future__ import annotations

import argparse
import json
import os
import statistics
import sys
import tempfile
import time
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))
os.chdir(REPO)

from PySide6.QtCore import QEventLoop, QTimer  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

import styles  # noqa: E402
import ui  # noqa: E402


def pump(app: QApplication, ms: int) -> None:
    loop = QEventLoop()
    QTimer.singleShot(ms, loop.quit)
    loop.exec()


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=8)
    ap.add_argument("--rounds", type=int, default=6)
    ap.add_argument("--json", type=Path)
    args = ap.parse_args()

    app = QApplication(sys.argv)
    styles.register_fonts()
    styles.apply_theme(app, "dark")
    ui.MainWindow._start_update_check = lambda self: None
    win = ui.MainWindow(settings_path=Path(tempfile.mkdtemp()) / "s.ini")
    win.resize(1180, 780)
    win.show()
    pump(app, 1500)

    cards = [c for c in win._all_cards if not c._empty]
    cards.sort(key=lambda c: -c._track_count)
    picked = cards[: args.n]
    for c in picked:
        c.setChecked(True)
    win._update_order_numbers()
    pump(app, 8000)  # debounce + worker + render por tandas
    from ui_components import FileRow
    rows = len(win.findChildren(FileRow))
    print(f"playlists marcadas={len(picked)} filas de vista previa={rows} widgets={len(win.findChildren(ui.QWidget))}")

    # Desglose por fase: se envuelven los pasos de _apply_theme.
    phases: dict[str, list[float]] = {}
    orig_set_ss = app.setStyleSheet

    def timed_set_ss(s: str) -> None:
        t = time.perf_counter(); orig_set_ss(s)
        phases.setdefault("app.setStyleSheet", []).append((time.perf_counter() - t) * 1000)

    app.setStyleSheet = timed_set_ss  # type: ignore[method-assign]
    for name in ("_retint_icons", "_sync_source_buttons", "_sync_theme_toggle"):
        fn = getattr(win, name)

        def wrap(*a, _fn=fn, _n=name):
            t = time.perf_counter(); r = _fn(*a)
            phases.setdefault(_n, []).append((time.perf_counter() - t) * 1000)
            return r
        setattr(win, name, wrap)

    apply_ms: list[float] = []
    settle_ms: list[float] = []
    theme = "dark"
    for _ in range(args.rounds):
        theme = "light" if theme == "dark" else "dark"
        t0 = time.perf_counter()
        win._apply_theme(theme)
        t1 = time.perf_counter()
        app.processEvents()
        win.repaint()
        t2 = time.perf_counter()
        apply_ms.append((t1 - t0) * 1000)
        settle_ms.append((t2 - t0) * 1000)
        pump(app, 200)
    win._apply_theme("dark")

    def stat(xs: list[float]) -> dict[str, float]:
        return {"median": round(statistics.median(xs), 1), "min": round(min(xs), 1), "max": round(max(xs), 1)}

    res = {
        "playlists": len(picked), "preview_rows": rows,
        "apply_theme_ms": stat(apply_ms), "apply_plus_paint_ms": stat(settle_ms),
        "phases_ms": {k: stat(v) for k, v in phases.items()},
    }
    print(json.dumps(res, indent=2))
    if args.json:
        args.json.write_text(json.dumps(res, indent=2))


if __name__ == "__main__":
    main()
