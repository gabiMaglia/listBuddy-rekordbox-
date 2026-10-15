"""T-033 / ADR-003: manifiestos de build sin PyQt6, onedir y sin UPX."""
from __future__ import annotations

import re

from _qt_isolated import PROJECT_ROOT

_SPEC = (PROJECT_ROOT / "rb_exporter.spec").read_text(encoding="utf-8")
_REQS = (PROJECT_ROOT / "requirements.txt").read_text(encoding="utf-8").splitlines()


def test_requirements_pin_pyside6_and_drop_pyqt6() -> None:
    assert "PySide6==6.12.0" in _REQS
    assert "shiboken6==6.12.0" in _REQS
    assert [r for r in _REQS if r.lower().startswith("pyqt")] == []


def test_spec_uses_pyside6_multimedia_and_excludes_pyqt6() -> None:
    assert "'PySide6.QtMultimedia'" in _SPEC
    assert "'PyQt6'" in _SPEC.split("excludes=", 1)[1].split("]", 1)[0]
    assert "PyQt6.QtMultimedia" not in _SPEC


def test_spec_never_enables_upx() -> None:
    # LGPL: comprimir las DLL de Qt complica que el usuario las reemplace.
    assert re.findall(r"upx\s*=\s*True", _SPEC) == []


def test_spec_windows_branch_is_onedir() -> None:
    windows = _SPEC.split("# ── Windows", 1)[1]
    assert "exclude_binaries=True" in windows
    assert "COLLECT(" in windows


def test_spec_bundles_fonts_and_qtsvg() -> None:
    assert "('fonts', 'fonts')" in _SPEC
    assert "'PySide6.QtSvg'" in _SPEC


def test_bundle_version_comes_from_app_version_single_source() -> None:
    # T-087 APP-11: el spec lee _APP_VERSION de ui.py; ningún literal que pueda divergir.
    assert "_APP_VERSION" in _SPEC and "ui.py" in _SPEC
    assert "'CFBundleVersion': APP_VERSION" in _SPEC
    assert "'CFBundleShortVersionString': APP_VERSION" in _SPEC
    assert not re.search(r"'CFBundle(Short)?Version(String)?': '\d", _SPEC)


def test_mac_bundle_uses_visible_brand_name() -> None:
    assert "name='List Buddy.app'" in _SPEC
    assert "'CFBundleDisplayName': 'List Buddy'" in _SPEC


def test_rekordbox_db_stack_is_not_shipped() -> None:
    assert not any(r.lower().startswith(("pyrekordbox", "sqlcipher3")) for r in _REQS)
    excludes = _SPEC.split("excludes=", 1)[1].split("]", 1)[0]
    for mod in ("'pyrekordbox'", "'sqlcipher3'", "'sqlalchemy'"):
        assert mod in excludes, mod
    assert "collect_data_files('pyrekordbox')" not in _SPEC


def test_info_plist_store_and_privacy_keys() -> None:
    # T-087 APP-05/09/10: categoría, motivos TCC (rioplatense) y mínimo real de macOS.
    assert "'LSApplicationCategoryType': 'public.app-category.music'" in _SPEC
    assert "'LSMinimumSystemVersion': '14.0'" in _SPEC
    for key in (
        "NSDesktopFolderUsageDescription", "NSDocumentsFolderUsageDescription",
        "NSDownloadsFolderUsageDescription", "NSRemovableVolumesUsageDescription",
        "NSNetworkVolumesUsageDescription", "NSHumanReadableCopyright",
    ):
        assert f"'{key}'" in _SPEC, key


def test_spec_drops_unused_qt_modules_t096() -> None:
    # TEC-12: QtPdf/QtQuick/QtQml/QtVirtualKeyboard (GPL-3.0) no se usan y pesan >13 MB.
    excludes = _SPEC.split("excludes=", 1)[1].split("]", 1)[0]
    for mod in ("PySide6.QtPdf", "PySide6.QtQuick", "PySide6.QtQml", "PySide6.QtVirtualKeyboard"):
        assert f"'{mod}'" in excludes, mod
    # Los hooks de PySide6 pueden arrastrar frameworks y plugins igual: filtro explícito.
    assert "a.binaries = " in _SPEC and "a.datas = " in _SPEC
    for token in ("qtquick", "qtqml", "qtpdf", "qtvirtualkeyboard", "qpdf"):
        assert f"'{token}'" in _SPEC, token


def test_spec_filter_matches_framework_plugin_and_windows_names() -> None:
    ns: dict[str, object] = {}
    src = _SPEC.split("# --- filtro Qt", 1)[1].split("# --- fin filtro Qt", 1)[0]
    src = src.split("\n", 1)[1].replace("a.binaries = ", "_b = ").replace("a.datas = ", "_d = ")
    src = "\n".join(l for l in src.splitlines() if "_b =" not in l and "_d =" not in l)
    exec(src, ns)  # noqa: S102 - definición pura de la función del spec
    drop = ns["_is_unused_qt"]
    for gone in (
        "PySide6/Qt/lib/QtQuick.framework/Versions/A/QtQuick",
        "PySide6/Qt/lib/QtVirtualKeyboardQml.framework/Versions/A/Resources/Info.plist",
        "PySide6/Qt/plugins/platforminputcontexts/libqtvirtualkeyboardplugin.dylib",
        "PySide6/Qt/plugins/imageformats/libqpdf.dylib",
        "PySide6/Qt6Qml.dll", "PySide6/plugins/platforminputcontexts/qtvirtualkeyboardplugin.dll",
        "PySide6/Qt6Pdf.dll",
    ):
        assert drop(gone), gone
    for kept in (
        "PySide6/Qt/lib/QtCore.framework/Versions/A/QtCore",
        "PySide6/Qt/lib/QtMultimedia.framework/Versions/A/QtMultimedia",
        "PySide6/Qt/plugins/multimedia/libffmpegmediaplugin.dylib",
        "PySide6/Qt/plugins/imageformats/libqsvg.dylib",
        "PySide6/QtWidgets.abi3.so", "PySide6/Qt6Multimedia.dll",
    ):
        assert not drop(kept), kept
