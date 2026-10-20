# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2025-2026 Gabriel Maglia
"""T-120: guía para que los módulos de la app no abran rutas por fuera de `file_access.py`.

Una versión con sandbox (Mac App Store, ADR-008) necesita que todo acceso a una ruta del usuario
pase por un único punto. El test recorre el AST de cada módulo del proyecto, así un módulo nuevo
(Buddy) queda vigilado sin tener que anotarlo. Lo que queda afuera está en `ALLOWLIST` con su
motivo, y una entrada que ya no hace falta también falla.

Es una GUÍA, no una garantía: atrapa las formas habituales, pero un análisis sintáctico no puede
decidir qué hace cada expresión en Python. Huecos conocidos (informe `engram/qa/T-120-verifier.md`):

- `Path.open()` sin argumentos (se ignora para no confundirlo con `QDialog.open()`).
- `tree.write(dest)` cuando `tree` no está anotado o llega de otra función (`self.tree`, un helper).
- `ET.ElementTree(file=ruta)` y `xml.dom.minidom.parse(ruta)`.
- Dependencias inyectadas por parámetro (`opener=open`, `replace=os.replace`).
- `functools.partial(open, ...)` y alias en un atributo de clase (`_open = staticmethod(open)`).
- `tempfile` (`mkstemp`/`mkdtemp` en una carpeta del usuario).
- `os.link`, `os.symlink` y `os.truncate`.
- La API de archivos de Qt (`QFile`, `QSaveFile`, `QSettings`, `QDir`, `QImage.save`…).
- Las carpetas excluidas (`tests`, `scripts`, `build`…) se saltean a cualquier profundidad, así que
  `buddy/build/` o `buddy/tests/` quedan fuera.
- La allowlist no es un trinquete: vive en este mismo archivo y el PR que agrega una excepción
  puede aflojarla.

La garantía es T-124 (guardia de auditoría en runtime + AST de la API de Qt, rama
`feat/t120-file-access`).
"""
from __future__ import annotations

import ast
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LAYER = "file_access"

# Fuera del escaneo: tests y herramientas de build, prototipos de diseño, documentación/evidencia
# de engram (no viaja en la app), entornos virtuales y artefactos de PyInstaller.
_SKIP_DIRS = {"tests", "scripts", "listBuddy_design", "engram", "build", "dist", "__pycache__"}

_BUILTIN_IO = {"open"}
_BANNED = {
    "builtins.open", "io.open", "_pyio.open", "codecs.open", "os.open", "os.fdopen",
    "os.replace", "os.rename", "os.renames", "os.remove", "os.unlink", "os.rmdir", "os.removedirs",
    "os.mkdir", "os.makedirs",
}  # + shutil.copy*, shutil.move, shutil.rmtree (ver _banned)
_ET_MODULES = ("xml.etree.ElementTree", "xml.etree.cElementTree")
_PARSERS = {f"{m}.{f}" for m in _ET_MODULES for f in ("parse", "iterparse")}
_ET_CLASS = {f"{m}.ElementTree" for m in _ET_MODULES}
_TREE_WRITE_KW = {"xml_declaration", "default_namespace", "short_empty_elements", "method"}
_LAYER_HANDLES = {f"{LAYER}.open_read", f"{LAYER}.atomic_write"}
# Métodos de pathlib.Path (o de un objeto sin resolver) que tocan el disco.
_PATH_METHODS = {
    "open", "fdopen", "read_text", "read_bytes", "write_text", "write_bytes", "mkdir", "unlink",
    "rmdir", "touch", "replace", "rename", "hardlink_to", "symlink_to",
}

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
    ("app_paths", "data_dir"):
        "crea la carpeta de datos propia de la app (settings, reparaciones); en un sandbox es el container.",
    ("app_logging", "log_dir"):
        "crea la carpeta de logs propia de la app; fuera de T-120 (otro agente en paralelo).",
    ("about_dialog", "TextViewerDialog.__init__"):
        "lee LICENSE y THIRD_PARTY_NOTICES empaquetados con la app (recursos propios).",
    ("single_instance", "_probe_owner"):
        "abre el lock propio en solo lectura para sondear su flock sin tomarlo (T-098); la capa no da fds.",
}


def _modules(root: Path = ROOT) -> list[tuple[str, Path]]:
    """Todo `.py` del proyecto, también en subpaquetes (un `buddy/` nuevo queda vigilado).
    Se saltean las herramientas y lo que no viaja en la app."""
    out: list[tuple[str, Path]] = []
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = sorted(d for d in dirnames if d not in _SKIP_DIRS and not d.startswith("."))
        for fn in sorted(filenames):
            if not fn.endswith(".py"):
                continue
            parts = list((Path(dirpath) / fn).relative_to(root).with_suffix("").parts)
            if parts[-1] == "__init__":
                parts = parts[:-1]
            name = ".".join(parts)
            if name != LAYER:
                out.append((name, Path(dirpath) / fn))
    return out


def _string_annotation(node: ast.expr | None) -> ast.expr | None:
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        try:
            return ast.parse(node.value, mode="eval").body
        except SyntaxError:
            return None
    return node


class _Scanner(ast.NodeVisitor):
    """Clasifica cada llamada por su nombre canónico: los imports (`import os as _os`,
    `from shutil import copy2`) y los alias simples (`o = open`) se resuelven antes."""

    def __init__(self, tree: ast.Module) -> None:
        self.aliases: dict[str, str] = {}
        self.stack: list[tuple[str, str]] = []
        self.handles: list[set[str]] = [set()]
        self.trees: list[set[str]] = [set()]
        self.hits: list[tuple[str, int, str]] = []
        self._collect_aliases(tree)

    # ── nombres ──
    def _collect_aliases(self, tree: ast.Module) -> None:
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for a in node.names:
                    if a.asname:
                        self.aliases[a.asname] = a.name
                    else:
                        head = a.name.split(".")[0]
                        self.aliases[head] = head
            elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
                for a in node.names:
                    self.aliases[a.asname or a.name] = f"{node.module}.{a.name}"
        for _ in range(2):                              # `o = open`, `c = shutil.copy2`, encadenados
            for node in ast.walk(tree):
                if isinstance(node, ast.Assign) and len(node.targets) == 1 \
                        and isinstance(node.targets[0], ast.Name):
                    canon = self.canon(node.value)
                    if canon and (_banned(canon) or canon in _PARSERS or canon in _ET_CLASS):
                        self.aliases[node.targets[0].id] = canon

    def canon(self, node: ast.expr) -> str | None:
        if isinstance(node, ast.Name):
            if node.id in self.aliases:
                return self.aliases[node.id]
            return f"builtins.{node.id}" if node.id in _BUILTIN_IO else None
        if isinstance(node, ast.Attribute):
            base = self.canon(node.value)
            return f"{base}.{node.attr}" if base else None
        return None

    def _is_handle(self, node: ast.expr | None) -> bool:
        return isinstance(node, ast.Name) and node.id in self.handles[-1]

    # ── ámbitos ──
    def _where(self) -> str:
        if not self.stack:
            return "<módulo>"
        if self.stack[0][0] == "class" and len(self.stack) > 1:
            return f"{self.stack[0][1]}.{self.stack[1][1]}"
        return self.stack[0][1]

    def _enter(self, kind: str, node: ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef) -> None:
        self.stack.append((kind, node.name))
        self.handles.append(set(self.handles[-1]))
        trees = set(self.trees[-1])
        if not isinstance(node, ast.ClassDef):
            a = node.args
            for arg in [*a.posonlyargs, *a.args, *a.kwonlyargs]:
                if self.canon(_string_annotation(arg.annotation) or ast.Constant(None)) in _ET_CLASS:
                    trees.add(arg.arg)
        self.trees.append(trees)
        self.generic_visit(node)
        self.trees.pop()
        self.handles.pop()
        self.stack.pop()

    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        self._enter("class", node)

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        self._enter("def", node)

    visit_AsyncFunctionDef = visit_FunctionDef      # type: ignore[assignment]

    def visit_With(self, node: ast.With) -> None:
        for item in node.items:
            expr = item.context_expr
            if isinstance(expr, ast.Call) and self.canon(expr.func) in _LAYER_HANDLES \
                    and isinstance(item.optional_vars, ast.Name):
                self.handles[-1].add(item.optional_vars.id)
        self.generic_visit(node)

    def visit_Assign(self, node: ast.Assign) -> None:
        v = node.value
        if isinstance(v, ast.Call) and self.canon(v.func) in (_PARSERS | _ET_CLASS):
            for t in node.targets:
                if isinstance(t, ast.Name):
                    self.trees[-1].add(t.id)
        self.generic_visit(node)

    # ── llamadas ──
    def visit_Call(self, node: ast.Call) -> None:
        kind = self._kind(node)
        if kind:
            self.hits.append((self._where(), node.lineno, kind))
        self.generic_visit(node)

    def _kind(self, call: ast.Call) -> str | None:
        f = call.func
        first = call.args[0] if call.args else None
        canon = self.canon(f)
        if canon:
            if canon.startswith(LAYER + "."):
                return None
            if canon in _PARSERS:
                return None if self._is_handle(first) else f"{canon}()"
            if _banned(canon):
                return f"{canon}()"
            if canon.startswith("pathlib.Path.") and canon.rsplit(".", 1)[1] in _PATH_METHODS:
                return f"{canon}()"
            if isinstance(f, ast.Name):
                return None
        if not isinstance(f, ast.Attribute):
            return None
        attr = f.attr
        if attr == "write":
            recv = f.value
            is_tree = (isinstance(recv, ast.Call) and self.canon(recv.func) in _ET_CLASS) or (
                isinstance(recv, ast.Name) and recv.id in self.trees[-1]) or any(
                k.arg in _TREE_WRITE_KW for k in call.keywords)
            return ".write(<ruta>) de un ElementTree" if is_tree and first is not None \
                and not self._is_handle(first) else None
        if canon:                                       # receptor resuelto a un módulo: ya se decidió arriba
            return None
        if attr not in _PATH_METHODS:
            return None
        if attr in ("open", "fdopen") and not (call.args or call.keywords):
            return None                                 # QDialog/QMenu.open() de Qt, no un archivo
        if attr in ("replace", "rename") and (len(call.args) != 1 or call.keywords):
            return None                                 # str.replace(a, b), datetime.replace(tzinfo=…)
        return f".{attr}()"


def _banned(canon: str) -> bool:
    mod, _, name = canon.rpartition(".")
    if mod == "shutil":
        return name.startswith("copy") or name in ("move", "rmtree")
    return canon in _BANNED


def scan_source(src: str) -> list[tuple[str, int, str]]:
    tree = ast.parse(src)
    s = _Scanner(tree)
    s.visit(tree)
    return s.hits


def _allowed(module: str, where: str) -> bool:
    return (module, "*") in ALLOWLIST or (module, where) in ALLOWLIST


def _all_hits() -> list[tuple[str, str, int, str]]:
    out = []
    for name, p in _modules():
        for where, line, kind in scan_source(p.read_text(encoding="utf-8")):
            out.append((name, where, line, kind))
    return out


def test_no_module_touches_user_paths_outside_file_access() -> None:
    bad = [f"{m}:{line} {kind} en {where}" for m, where, line, kind in _all_hits()
           if not _allowed(m, where)]
    assert not bad, "acceso a disco fuera de file_access.py (usá la capa o justificalo en ALLOWLIST):\n" + "\n".join(bad)


def test_every_allowlist_entry_is_still_needed() -> None:
    hits = _all_hits()
    stale = [k for k in ALLOWLIST
             if not any(m == k[0] and k[1] in ("*", where) for m, where, _, _ in hits)]
    assert not stale, f"entradas de ALLOWLIST que ya no hacen falta (sacalas): {stale}"


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
    assert scan_source(src) == [("W.run", 4, "builtins.open()")]


# ── Intento 2 (QA D1/D3/G4/G5): formas que el detector tiene que ver resolviendo imports. ──

_EVASIONS = {
    "from shutil import copy2": "from shutil import copy2\ndef f(p, q):\n    copy2(p, q)\n",
    "from shutil import ... as": "from shutil import copyfile as _c\ndef f(p, q):\n    _c(p, q)\n",
    "from os import replace": "from os import replace\ndef f(p, q):\n    replace(p, q)\n",
    "from ET import parse": "from xml.etree.ElementTree import parse\ndef f(p):\n    parse(p)\n",
    "import shutil as sh": "import shutil as sh\ndef f(p, q):\n    sh.copy2(p, q)\n",
    "import os as _os": "import os as _os\ndef f(p, q):\n    _os.replace(p, q)\n",
    "import ...ElementTree as X": "import xml.etree.ElementTree as X\ndef f(p):\n    X.parse(str(p))\n",
    "import xml.etree.ElementTree": "import xml.etree.ElementTree\ndef f(p):\n    xml.etree.ElementTree.parse(p)\n",
    "alias de open": "def f(p):\n    o = open\n    o(p, 'w')\n",
    "io.open": "import io\ndef f(p):\n    io.open(p, 'w')\n",
    "Path(...).open('w')": "from pathlib import Path\ndef f(p):\n    Path(p).open('w')\n",
    "ElementTree(...).write(ruta)":
        "from xml.etree import ElementTree as ET\ndef f(r, p):\n    ET.ElementTree(r).write(p, encoding='UTF-8')\n",
    "tree.write(ruta) tras parse":
        "import file_access\nfrom xml.etree import ElementTree as ET\ndef f(p):\n"
        "    with file_access.open_read(p) as fh:\n        tree = ET.parse(fh)\n    tree.write(str(p))\n",
    "tree.write(ruta) parámetro anotado":
        "from xml.etree import ElementTree as ET\ndef f(tree: ET.ElementTree, p):\n    tree.write(str(p))\n",
    "Path.mkdir": "def f(d):\n    d.mkdir(parents=True, exist_ok=True)\n",
    "os.makedirs": "import os\ndef f(d):\n    os.makedirs(d, exist_ok=True)\n",
    "Path.unlink": "def f(p):\n    p.unlink(missing_ok=True)\n",
    "os.remove": "import os\ndef f(p):\n    os.remove(p)\n",
    "os.unlink": "from os import unlink\ndef f(p):\n    unlink(p)\n",
    "shutil.rmtree": "import shutil\ndef f(p):\n    shutil.rmtree(p)\n",
    "Path.rmdir": "def f(p):\n    p.rmdir()\n",
}


def test_detector_sees_through_imports_aliases_and_tree_writes() -> None:
    missed = [name for name, src in _EVASIONS.items() if not scan_source(src)]
    assert not missed, f"el detector no ve: {missed}"


def test_detector_accepts_tree_write_to_a_layer_handle() -> None:
    src = (
        "import file_access\nfrom xml.etree import ElementTree as ET\n"
        "def f(r, p):\n"
        "    with file_access.atomic_write(p) as fh:\n"
        "        ET.ElementTree(r).write(fh, encoding='unicode')\n"
        "    buf.write(b'x')\n"
    )
    assert scan_source(src) == []


def test_allowlist_matches_the_declared_qualified_name_only() -> None:
    """D3: ("styles", "load_qss") no exime un `Otra.load_qss` del mismo módulo."""
    assert _allowed("styles", "load_qss")
    assert not _allowed("styles", "Otra.load_qss")
    assert not _allowed("worker", "Clase._copy_atomic")
    assert _allowed("worker", "_copy_atomic")


def test_scan_reaches_subpackages_and_skips_tooling(tmp_path: Path) -> None:
    """G5: un paquete nuevo (p. ej. `buddy/`) queda vigilado; tests/, scripts/ y compañía no."""
    for rel in ("buddy/__init__.py", "buddy/store.py", "tests/t.py", "scripts/s.py",
                "listBuddy_design/d.py", ".venv/lib/x.py", ".venv-build/y.py", "build/b.py",
                "dist/z.py", "engram/e.py", "app.py"):
        f = tmp_path / rel
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_text("def f(p):\n    open(p, 'w')\n", encoding="utf-8")
    assert sorted(m for m, _ in _modules(tmp_path)) == ["app", "buddy", "buddy.store"]
