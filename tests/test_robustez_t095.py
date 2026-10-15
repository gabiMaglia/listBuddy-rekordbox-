"""T-095: robustez de export y preview (TEC-08/09/10/18 y deudas D-16..D-22 de QA)."""
from __future__ import annotations

from _qt_isolated import run_isolated
from _window_boot import BOOT
from test_export_integrity import _PRE


def _run(body: str, pre: str = _PRE, timeout: float = 60.0) -> str:
    r = run_isolated(pre + body, timeout=timeout)
    assert r.returncode == 0, r.stderr[-3000:]
    return r.stdout.strip().splitlines()[-1]


def _win(body: str) -> str:
    r = run_isolated(BOOT + body)
    assert r.returncode == 0, r.stderr[-3000:]
    return r.stdout.strip().splitlines()[-1]


# ── TEC-08 ────────────────────────────────────────────────────────────────

def test_incremental_reexport_to_a_nearly_full_disk_does_not_abort() -> None:
    out = _run(
        "p = pl('Mix', [track(1, 1), track(2, 2)])\n"
        "logs, done = export([p])\n"
        "import collections\n"
        "free = 500_000\n"
        "worker.shutil.disk_usage = lambda _p: collections.namedtuple('U', 'total used free')(10**9, 10**9 - free, free)\n"
        "logs, done = export([p])\n"
        "print(done[3], done[0], done[2])\n"
    )
    assert out == "ok 0 2"
