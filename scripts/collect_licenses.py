"""
scripts/collect_licenses.py
---------------------------
Copia a `licenses/` el texto de licencia de cada paquete Python que viaja
dentro del ejecutable, tal cual viene en su `dist-info` del venv. Correrlo
después de cambiar cualquier versión de `requirements.txt` y revisar que
THIRD_PARTY_NOTICES.md siga diciendo las mismas versiones.

Los textos estándar (GPL-3.0, LGPL-3.0, LGPL-2.1, MPL-2.0, Apache-2.0) y los
de componentes nativos sin dist-info (Python, OpenSSL) están
versionados a mano en `licenses/` y este script no los toca.

    python scripts/collect_licenses.py
"""
from __future__ import annotations

import importlib.metadata as md
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "licenses"

# distribución de PyPI → nombre del archivo en licenses/
PACKAGES: dict[str, str] = {
    "numpy": "numpy.txt",
    "certifi": "certifi.txt",
    "qrcode": "qrcode.txt",
}


def _license_files(dist: md.Distribution) -> list[Path]:
    files = [
        Path(str(dist.locate_file(f)))
        for f in dist.files or []
        if Path(f).name.upper().startswith(("LICENSE", "COPYING"))
    ]
    return sorted(p for p in files if p.is_file())


def main() -> None:
    OUT.mkdir(exist_ok=True)
    for name, target in PACKAGES.items():
        dist = md.distribution(name)
        files = _license_files(dist)
        if not files:
            raise SystemExit(f"{name}: no se encontró archivo de licencia en dist-info")
        header = f"{name} {dist.version}\n{'=' * 72}\n\n"
        body = "\n\n".join(
            (f"--- {p.name} ---\n\n" if len(files) > 1 else "")
            + p.read_text(encoding="utf-8").strip()
            for p in files
        )
        (OUT / target).write_text(header + body + "\n", encoding="utf-8")
        print(f"{target}: {name} {dist.version} ({len(files)} archivo/s)")


if __name__ == "__main__":
    main()
