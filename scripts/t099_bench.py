# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2025-2026 Gabriel Maglia
"""T-099 F0: línea de base de rendimiento para comparar cada fase del split de `ui.py`.

Mide dos cosas con la ventana real (`tests/_window_boot.BOOT`, sin DB ni red, ini temporal):
  click10   10 playlists de 200 pistas; se tildan 9 y se mide la 10.ª: CPU del hilo de UI desde el tilde hasta
            que la vista previa queda quieta (incluye el fade), reloj de pared y widgets nuevos.
  pop800    poblado del árbol con 800 playlists (mitad sueltas, mitad en 20 carpetas) con el watchdog de 5 ms
            de `tests/test_preview_scale_t106.py`: peor hueco de CPU del hilo de UI entre dos disparos.

Cada corrida va en un proceso nuevo (en un intérprete reusado el hueco medido crece con lo anterior, T-106).

Uso: python scripts/t099_bench.py [--repeat 3] [--platform offscreen]
"""
from __future__ import annotations

import argparse
import json
import os
import pathlib
import platform
import statistics
import subprocess
import sys
import time
from typing import Any, Callable

REPO = pathlib.Path(__file__).resolve().parents[1]
CASES = ("click10", "pop800")
# El fade de una tarjeta nueva dura 180 ms: la cola de 300 ms lo deja terminar dentro de la medición.
TAIL_MS = 300


def _boot() -> dict[str, Any]:
    sys.path[:0] = [str(REPO), str(REPO / "tests")]
    os.chdir(REPO)
    from _window_boot import BOOT  # el mismo arranque que usan los tests

    ns: dict[str, Any] = {}
    exec(BOOT, ns)
    return ns


def _pump(ms: int) -> None:
    from PySide6.QtCore import QEventLoop, QTimer

    loop = QEventLoop()
    QTimer.singleShot(ms, loop.quit)
    loop.exec()   # bloquea sin girar: la espera ociosa no suma CPU al hilo de UI


def _wait(cond: Callable[[], bool], timeout: float = 120.0) -> bool:
    end = time.monotonic() + timeout
    while not cond() and time.monotonic() < end:
        _pump(5)
    return cond()


def _warm_up(app: Any) -> None:
    # El primer processEvents de una ventana nueva paga el pulido de estilos (~300 ms, una vez).
    for _ in range(5):
        app.processEvents()
        time.sleep(0.02)


def bench_click10() -> dict[str, float]:
    ns = _boot()
    app, make = ns["app"], ns["make"]
    from types import SimpleNamespace

    from PySide6.QtCore import Qt
    from PySide6.QtTest import QTest
    from PySide6.QtWidgets import QWidget

    from preview_worker import GroupData, TrackRow
    from ui_components import PlaylistCard

    w, _ = make()
    n, tracks = 10, 200
    cards = []
    for g in range(n):
        pl = SimpleNamespace(Name=f"P{g}", uuid=f"u{g}", Songs=[object()] * tracks)
        c = PlaylistCard(pl, tracks, g)
        c.toggled.connect(w._on_card_toggled)
        w._all_cards.append(c)
        cards.append(c)
        for i in range(tracks):
            w._exists_cache[f"/x/{g}/{i}.mp3"] = True

    def extract(selected: list[Any]) -> list[Any]:
        out = []
        for idx, c in enumerate(selected):
            g = int(c.playlist.uuid[1:])
            tr = [TrackRow(str(i + 1).zfill(3), f"T{g}-{i}", "Art", ".mp3", f"/x/{g}/{i}.mp3") for i in range(tracks)]
            out.append(GroupData(c.playlist.Name, idx + 1, tracks, tr, card=c))
        return out

    w._extract_preview_data = extract

    def settled(k: int) -> Callable[[], bool]:
        def done() -> bool:
            busy = any(x.isRunning() for x in w._preview_workers)
            return (len(w._preview_cards) == k and not w._render_queue and not w._feed_queue and not busy
                    and not w._preview_debounce.isActive())
        return done

    _warm_up(app)
    for k, c in enumerate(cards[:-1], start=1):
        QTest.mouseClick(c, Qt.MouseButton.LeftButton)
        assert _wait(settled(k)), f"no se asentó el tilde {k}"
        _pump(TAIL_MS)
    widgets = len(w.findChildren(QWidget))
    cpu0, wall0 = time.thread_time(), time.perf_counter()
    QTest.mouseClick(cards[-1], Qt.MouseButton.LeftButton)   # el mismo camino que un click real
    assert _wait(settled(n)), "no se asentó el click 10"
    wall = time.perf_counter() - wall0
    _pump(TAIL_MS)
    cpu = time.thread_time() - cpu0
    return {"click10_ui_cpu_ms": cpu * 1000, "click10_wall_ms": wall * 1000,
            "click10_new_widgets": float(len(w.findChildren(QWidget)) - widgets)}


def bench_pop800() -> dict[str, float]:
    ns = _boot()
    app, make = ns["app"], ns["make"]
    from types import SimpleNamespace

    from PySide6.QtCore import QTimer

    def node(name: str, kids: list[dict[str, Any]] | None = None) -> dict[str, Any]:
        return {"playlist": SimpleNamespace(Name=name, is_folder=kids is not None), "children": kids or []}

    tree: list[dict[str, Any]] = []
    for i in range(400):
        tree.append(node(f"S{i}"))
        if i % 20 == 19:
            tree.append(node(f"F{i}", [node(f"F{i}-{j}") for j in range(20)]))

    gaps: list[float] = []
    last = [time.thread_time()]

    def tick() -> None:
        now = time.thread_time()
        gaps.append(now - last[0])
        last[0] = now

    w, _ = make()
    _warm_up(app)
    dog = QTimer()
    dog.setInterval(5)
    dog.timeout.connect(tick)
    last[0] = time.thread_time()
    dog.start()
    done: list[int] = []
    wall0 = time.perf_counter()
    w._populate_playlists(tree, lambda pl: 5, on_done=lambda: done.append(1))
    end = time.monotonic() + 240
    while not done and time.monotonic() < end:
        app.processEvents()
        time.sleep(0.001)
    wall = time.perf_counter() - wall0
    dog.stop()
    assert done and len(w._all_cards) == 800, f"poblado incompleto: {len(w._all_cards)}"
    return {"pop800_worst_gap_ms": max(gaps) * 1000, "pop800_wall_ms": wall * 1000, "pop800_ticks": float(len(gaps))}


def _run_one(case: str, qpa: str) -> dict[str, float]:
    env = {**os.environ, "QT_QPA_PLATFORM": qpa, "PYTHONUTF8": "1"}
    r = subprocess.run([sys.executable, str(pathlib.Path(__file__).resolve()), "--one", case],
                       capture_output=True, text=True, env=env, timeout=600)
    if r.returncode != 0:
        raise SystemExit(f"{case} falló:\n{r.stderr[-3000:]}")
    return json.loads(r.stdout.strip().splitlines()[-1])


def _head() -> str:
    r = subprocess.run(["git", "-C", str(REPO), "rev-parse", "--short", "HEAD"], capture_output=True, text=True)
    return r.stdout.strip() or "?"


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--repeat", type=int, default=3)
    ap.add_argument("--platform", default=os.environ.get("QT_QPA_PLATFORM", "offscreen"))
    ap.add_argument("--one", choices=CASES, help=argparse.SUPPRESS)
    args = ap.parse_args(argv)
    if args.one:
        result = bench_click10() if args.one == "click10" else bench_pop800()
        print(json.dumps(result))
        return 0

    import PySide6

    load = os.getloadavg()[0] if hasattr(os, "getloadavg") else float("nan")
    print(f"t099_bench · HEAD {_head()} · {platform.platform()} · Python {platform.python_version()} · "
          f"PySide6 {PySide6.__version__} · QPA {args.platform} · load1 {load:.2f} · {args.repeat} corridas")
    runs: dict[str, list[float]] = {}
    for case in CASES:
        for i in range(args.repeat):
            res = _run_one(case, args.platform)
            print(f"  {case} #{i + 1}: " + "  ".join(f"{k}={v:.0f}" for k, v in res.items()))
            for k, v in res.items():
                runs.setdefault(k, []).append(v)
    print("mediana: " + "  ".join(f"{k}={statistics.median(v):.0f}" for k, v in runs.items()))
    return 0


if __name__ == "__main__":
    sys.exit(main())
