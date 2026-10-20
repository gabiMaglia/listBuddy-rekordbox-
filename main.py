# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2025-2026 Gabriel Maglia
"""
main.py
-------
Entry point de listBuddy.
"""
from __future__ import annotations

import logging
import sys
from types import ModuleType, SimpleNamespace

import startup_guard
from startup_guard import guarded_import


def _load_single_instance() -> ModuleType:
    # Solo QtCore: la segunda instancia sale antes de cargar la UI.
    import single_instance
    return single_instance


def _load_qt_stack() -> SimpleNamespace:
    # Todo lo que arrastra PySide6 se importa acá para que la guarda lo cubra.
    from PySide6.QtGui import QFont
    from PySide6.QtWidgets import QApplication

    from app_logging import install_excepthook, setup_logging
    from styles import apply_theme, register_fonts
    from ui import MainWindow, _APP_VERSION

    return SimpleNamespace(
        QFont=QFont, QApplication=QApplication, install_excepthook=install_excepthook,
        setup_logging=setup_logging, apply_theme=apply_theme, register_fonts=register_fonts,
        MainWindow=MainWindow, version=_APP_VERSION,
    )


def main() -> None:
    si = guarded_import(_load_single_instance)
    # Antes del log y de settings.ini: una segunda instancia no tiene que tocarlos (T-098).
    guard = si.acquire_in_data_dir()
    if guard.status is si.LockStatus.ALREADY_RUNNING:
        startup_guard.show_native_alert(
            startup_guard.ALREADY_RUNNING_TITLE, startup_guard.already_running_message(), "informational")
        raise SystemExit(0)
    if guard.status is si.LockStatus.FOREIGN_HOST:
        startup_guard.show_native_alert(
            startup_guard.FOREIGN_HOST_TITLE,
            startup_guard.foreign_host_message(guard.host, guard.path, same_name=guard.same_name), "warning")
        raise SystemExit(0)
    if guard.status is si.LockStatus.NO_SPACE:
        startup_guard.show_native_alert(
            startup_guard.NO_SPACE_TITLE, startup_guard.no_space_message(guard.path), "warning")
        raise SystemExit(0)
    if guard.status is si.LockStatus.CANT_CREATE:
        startup_guard.show_native_alert(
            startup_guard.CANT_CREATE_TITLE, startup_guard.cant_create_message(guard.path, guard.detail), "warning")
        raise SystemExit(0)
    if guard.status is si.LockStatus.STUCK_LOCK:
        startup_guard.show_native_alert(
            startup_guard.STUCK_LOCK_TITLE, startup_guard.stuck_lock_message(guard.path, owner_unknown=guard.owner_unknown), "warning")
        raise SystemExit(0)

    qt = guarded_import(_load_qt_stack)
    qt.setup_logging(qt.version)
    if guard.status is si.LockStatus.UNAVAILABLE:
        logging.getLogger("listBuddy").warning("Sin guarda de instancia única: %s", guard.detail)
    # Instalar el excepthook ANTES de crear la ventana: así también captura
    # cualquier error durante el arranque, no solo en los slots en runtime.
    qt.install_excepthook()

    app = qt.QApplication(sys.argv)
    # Antes del tema: la QSS referencia las familias por nombre.
    qt.register_fonts()
    app.setFont(qt.QFont('Public Sans', 13))
    qt.apply_theme(app, 'dark')
    win = qt.MainWindow()
    win.show()
    rc = app.exec()
    guard.release()
    sys.exit(rc)


if __name__ == "__main__":
    main()
