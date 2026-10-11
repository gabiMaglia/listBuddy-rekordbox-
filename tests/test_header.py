"""T-062: header (marca, selector, Mantenimiento, ajustes, tema, Apoyar)."""
from __future__ import annotations

from _qt_isolated import PROJECT_ROOT, run_isolated
from _window_boot import BOOT


def run(code: str):
    r = run_isolated(BOOT + code)
    assert r.returncode == 0, r.stderr[-2000:]
    return r.stdout


def test_settings_path_is_injected_and_repo_ini_untouched() -> None:
    repo_ini = PROJECT_ROOT / ".rbe_settings.ini"
    before = repo_ini.stat().st_mtime_ns if repo_ini.exists() else None
    out = run(
        "w, tmp = make()\n"
        "w.settings.setValue('probe', 1); w.settings.sync()\n"
        "print(w.settings.fileName() == str(tmp), tmp.exists())\n"
    )
    assert out.split()[-2:] == ["True", "True"]
    after = repo_ini.stat().st_mtime_ns if repo_ini.exists() else None
    assert before == after
