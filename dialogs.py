# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2025-2026 Gabriel Maglia
"""QMessageBox con botones en español rioplatense.

Los botones estándar de Qt salen en inglés si no se empaquetan las
traducciones; acá se crean con texto explícito y no hace falta ninguna.
"""
from __future__ import annotations

from PySide6.QtWidgets import QMessageBox, QPushButton, QWidget

_DETAILS_SHOW = "Mostrar detalles…"
_DETAILS_HIDE = "Ocultar detalles…"


def localize_details_button(box: QMessageBox) -> None:
    """El botón de detalles lo crea Qt; se le pone texto propio y se mantiene al alternar."""
    for btn in box.findChildren(QPushButton):
        if btn.text().lower().startswith(("show details", "hide details")):
            btn.setText(_DETAILS_SHOW)
            btn.clicked.connect(
                lambda _=False, b=btn: b.setText(
                    _DETAILS_HIDE if b.text() == _DETAILS_SHOW else _DETAILS_SHOW
                )
            )
            return


def build_message(
    parent: QWidget | None, icon: QMessageBox.Icon, title: str, text: str,
) -> QMessageBox:
    box = QMessageBox(icon, title, text, QMessageBox.StandardButton.NoButton, parent)
    ok = box.addButton("Aceptar", QMessageBox.ButtonRole.AcceptRole)
    box.setDefaultButton(ok)
    box.setEscapeButton(ok)
    return box


def build_question(parent: QWidget | None, title: str, text: str) -> QMessageBox:
    """Sí/No con «No» por defecto: las confirmaciones de la app son destructivas."""
    box = QMessageBox(
        QMessageBox.Icon.Question, title, text, QMessageBox.StandardButton.NoButton, parent
    )
    box.addButton("Sí", QMessageBox.ButtonRole.YesRole)
    no = box.addButton("No", QMessageBox.ButtonRole.NoRole)
    box.setDefaultButton(no)
    box.setEscapeButton(no)
    return box


def _show(parent: QWidget | None, icon: QMessageBox.Icon, title: str, text: str) -> None:
    build_message(parent, icon, title, text).exec()


def information(parent: QWidget | None, title: str, text: str) -> None:
    _show(parent, QMessageBox.Icon.Information, title, text)


def warning(parent: QWidget | None, title: str, text: str) -> None:
    _show(parent, QMessageBox.Icon.Warning, title, text)


def critical(parent: QWidget | None, title: str, text: str) -> None:
    _show(parent, QMessageBox.Icon.Critical, title, text)


def question(parent: QWidget | None, title: str, text: str) -> bool:
    box = build_question(parent, title, text)
    box.exec()
    clicked = box.clickedButton()
    return clicked is not None and clicked.text() == "Sí"
