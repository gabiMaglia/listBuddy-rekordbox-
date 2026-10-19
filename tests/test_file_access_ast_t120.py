# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2025-2026 Gabriel Maglia
"""T-120: ningún módulo de la app abre rutas por fuera de `file_access.py`.

Una versión con sandbox (Mac App Store, ADR-008) necesita que todo acceso a una ruta del usuario
pase por un único punto. El test recorre el AST de cada módulo de la raíz, así un módulo nuevo
(Buddy) queda vigilado sin tener que anotarlo. Lo que queda afuera está en `ALLOWLIST` con su
motivo, y una entrada que ya no hace falta también falla: la lista solo puede achicarse.
"""
from __future__ import annotations

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LAYER = "file_access"

_ET_NAMES = {"ET", "ElementTree", "etree", "cElementTree"}
_PATH_IO = {"read_text", "read_bytes", "write_text", "write_bytes"}

# (módulo, función que lo contiene) -> motivo. "*" = el módulo entero.
ALLOWLIST: dict[tuple[str, str], str] = {
    ("worker", "_copy_atomic"):
        "copia del audio al destino: por bloques, cancelable y con `.part` en O_EXCL contra symlinks "
        "plantados; no es XML/NML ni backup. Se envuelve con el permiso de la carpeta en T-102 F2-a.",
    ("app_paths", "make_private"):
        "crea vacío el archivo propio de la carpeta de datos (settings.ini) para fijarle 0600; la capa "
        "se apoya en esta función y app_paths queda fuera de T-120.",
    ("rekordbox_export", "export_playlist"):
        "lógica base validada que no se modifica (regla del proyecto); la app no llama a esta función.",
    ("styles", "_tick_url"):
        "PNG del tilde generado en la carpeta temporal del sistema; no es una ruta del usuario.",
    ("styles", "load_qss"):
        "lee la hoja QSS empaquetada con la app (recurso propio, no ruta del usuario).",
    ("about_dialog", "TextViewerDialog"):
        "lee LICENSE y THIRD_PARTY_NOTICES empaquetados con la app (recursos propios).",
}


def _is_open_read(call: ast.expr) -> bool:
    if not isinstance(call, ast.Call):
        return False
    f = call.func
    return (isinstance(f, ast.Attribute) and f.attr == "open_read"
            and isinstance(f.value, ast.Name) and f.value.id == LAYER) or (
        isinstance(f, ast.Name) and f.id == "open_read")


def _receiver(node: ast.Attribute) -> str | None:
    return node.value.id if isinstance(node.value, ast.Name) else None


def _kind(call: ast.Call, layer_handles: set[str]) -> str | None:
    """Nombre de la operación de disco prohibida que hace `call`, o None."""
    f = call.func
    if isinstance(f, ast.Name):
        return "open()" if f.id == "open" else None
    if not isinstance(f, ast.Attribute):
        return None
    recv, attr = _receiver(f), f.attr
    if recv == LAYER:
        return None
    # Sin argumentos es QDialog/QMenu.open() de Qt, no un archivo; webbrowser.open() es una URL.
    if attr in ("open", "fdopen") and recv != "webbrowser" and (call.args or call.keywords or recv == "os"):
        return f"{recv or '<expr>'}.{attr}()"
    if attr in _PATH_IO:
        return f".{attr}()"
    if recv == "os" and attr in ("replace", "rename", "renames"):
        return f"os.{attr}()"
    if recv == "shutil" and (attr.startswith("copy") or attr == "move"):
        return f"shutil.{attr}()"
    # Path.replace/rename(destino): un solo argumento posicional (str.replace pide dos).
    if attr in ("replace", "rename") and recv != "os" and len(call.args) == 1 and not call.keywords:
        return f".{attr}()"
    if recv in _ET_NAMES and attr in ("parse", "iterparse"):
        first = call.args[0] if call.args else None
        if isinstance(first, ast.Name) and first.id in layer_handles:
            return None                                # parsea un archivo que abrió la capa
        return f"{recv}.{attr}()"
    return None


class _Scanner(ast.NodeVisitor):
    def __init__(self) -> None:
        self.stack: list[str] = []
        self.handles: list[set[str]] = [set()]
        self.hits: list[tuple[str, int, str]] = []

    def _scope(self, node: ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef) -> None:
        self.stack.append(node.name)
        self.handles.append(set())
        self.generic_visit(node)
        self.handles.pop()
        self.stack.pop()

    visit_FunctionDef = visit_AsyncFunctionDef = visit_ClassDef = _scope

    def visit_With(self, node: ast.With) -> None:
        for item in node.items:
            if _is_open_read(item.context_expr) and isinstance(item.optional_vars, ast.Name):
                self.handles[-1].add(item.optional_vars.id)
        self.generic_visit(node)

    def visit_Call(self, node: ast.Call) -> None:
        kind = _kind(node, self.handles[-1])
        if kind:
            # Se reporta la función de primer nivel (o el método) que lo contiene.
            where = ".".join(self.stack[:2]) if self.stack else "<módulo>"
            self.hits.append((where, node.lineno, kind))
        self.generic_visit(node)


def scan_source(src: str) -> list[tuple[str, int, str]]:
    s = _Scanner()
    s.visit(ast.parse(src))
    return s.hits


def _modules() -> list[Path]:
    return sorted(p for p in ROOT.glob("*.py") if p.stem != LAYER)


def _allowed(module: str, where: str) -> bool:
    if (module, "*") in ALLOWLIST:
        return True
    return any((module, w) in ALLOWLIST for w in (where, where.split(".")[0], where.split(".")[-1]))


def _all_hits() -> list[tuple[str, str, int, str]]:
    out = []
    for p in _modules():
        for where, line, kind in scan_source(p.read_text(encoding="utf-8")):
            out.append((p.stem, where, line, kind))
    return out


def test_no_module_touches_user_paths_outside_file_access() -> None:
    bad = [f"{m}.py:{line} {kind} en {where}" for m, where, line, kind in _all_hits()
           if not _allowed(m, where)]
    assert not bad, "acceso a disco fuera de file_access.py (usá la capa o justificalo en ALLOWLIST):\n" + "\n".join(bad)


def test_every_allowlist_entry_is_still_needed() -> None:
    hits = _all_hits()
    stale = [k for k in ALLOWLIST
             if not any(m == k[0] and (k[1] == "*" or _allowed_exact(k, where)) for m, where, _, _ in hits)]
    assert not stale, f"entradas de ALLOWLIST que ya no hacen falta (sacalas): {stale}"


def _allowed_exact(key: tuple[str, str], where: str) -> bool:
    return key[1] in (where, where.split(".")[0], where.split(".")[-1])


def test_migrated_modules_have_no_allowlist_except_audio_copy() -> None:
    """Los módulos que migró T-120 no pueden volver a abrir rutas solos."""
    migrated = {"rekordbox_xml", "traktor_db", "traktor_relocate", "relocate_core", "rekordbox_fixes",
                "rekordbox_xml_relocate", "library_load_worker", "worker"}
    extra = {k for k in ALLOWLIST if k[0] in migrated} - {("worker", "_copy_atomic")}
    assert not extra


def test_the_layer_exists_and_is_used_by_the_readers_and_writers() -> None:
    assert (ROOT / f"{LAYER}.py").is_file()
    for m in ("rekordbox_xml", "traktor_db", "traktor_relocate", "relocate_core", "rekordbox_fixes", "worker"):
        tree = ast.parse((ROOT / f"{m}.py").read_text(encoding="utf-8"))
        names = {a.name for n in ast.walk(tree) if isinstance(n, ast.Import) for a in n.names}
        froms = {n.module for n in ast.walk(tree) if isinstance(n, ast.ImportFrom)}
        assert LAYER in names | froms, f"{m}.py no usa {LAYER}"


# ── El detector mismo: si deja de ver una forma, el test de arriba pasa en falso. ──

def test_detector_flags_every_banned_form() -> None:
    src = '''
import os, shutil
from xml.etree import ElementTree as ET
def f(p, q):
    open(p)
    p.open("rb")
    p.open(mode="w")
    os.open(p, 0)
    os.fdopen(3)
    p.read_text()
    p.read_bytes()
    p.write_text("x")
    p.write_bytes(b"x")
    os.replace(p, q)
    os.rename(p, q)
    shutil.copy(p, q)
    shutil.copy2(p, q)
    shutil.copyfile(p, q)
    shutil.move(p, q)
    p.replace(q)
    ET.parse(str(p))
    ET.iterparse(p)
'''
    assert len(scan_source(src)) == 18


def test_detector_ignores_safe_forms() -> None:
    src = '''
import file_access, webbrowser
from xml.etree import ElementTree as ET
def f(p, s):
    s.replace("a", "b")
    webbrowser.open("https://x")
    with file_access.open_read(p) as fh:
        ET.parse(fh)
        ET.iterparse(fh)
    file_access.read_text(p)
    d.replace(tzinfo=None)
    dialog.open()
'''
    assert scan_source(src) == []


def test_detector_reports_the_enclosing_function() -> None:
    src = "class W:\n    def run(self, p):\n        def inner():\n            open(p)\n"
    assert scan_source(src) == [("W.run", 4, "open()")]
