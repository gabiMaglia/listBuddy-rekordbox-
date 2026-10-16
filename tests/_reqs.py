"""Lectura de los requirements con hashes (pip-compile --generate-hashes, T-096)."""
from __future__ import annotations

import re
from pathlib import Path


def _norm(name: str) -> str:
    return re.sub(r"[-_.]+", "-", name).lower()


def pinned(path: Path) -> dict[str, str]:
    """{nombre normalizado: versión} de las líneas `nombre==versión` (con o sin hashes)."""
    out: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        m = re.match(r"^([A-Za-z0-9][A-Za-z0-9._-]*)==([^\s\;]+)", line)
        if m:
            out[_norm(m.group(1))] = m.group(2)
    return out


def unhashed(path: Path) -> list[str]:
    """Paquetes del lock que no traen al menos un `--hash=sha256:`."""
    text = path.read_text(encoding="utf-8")
    blocks = re.split(r"\n(?=[A-Za-z0-9][A-Za-z0-9._-]*==)", text)
    return [b.splitlines()[0] for b in blocks if re.match(r"[A-Za-z0-9][A-Za-z0-9._-]*==", b)
            and "--hash=sha256:" not in b]
