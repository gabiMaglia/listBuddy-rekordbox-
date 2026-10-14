"""
about_dialog.py
---------------
«Acerca de»: los avisos legales que la GPLv3 (§0, §5d) pide en una interfaz
interactiva —copyright, licencia, falta de garantía y cómo ver la licencia—
más los avisos de terceros (THIRD_PARTY_NOTICES.md) que viajan en el bundle.

Los textos se leen de disco (ROOT de styles: el repo o sys._MEIPASS). Si
falta un archivo el visor muestra el link al repo en vez de fallar.
"""
from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt, QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QPlainTextEdit,
    QPushButton,
    QTextBrowser,
    QVBoxLayout,
    QWidget,
)

from branding import APP_NAME, COPYRIGHT, SOURCE_URL
from styles import ROOT, apply_title_tracking, token

LICENSE_PATH = ROOT / "LICENSE"
NOTICES_PATH = ROOT / "THIRD_PARTY_NOTICES.md"
LICENSES_DIR = ROOT / "licenses"

_LEGAL_TEXT = (
    f"{APP_NAME} es software libre: podés redistribuirlo y modificarlo bajo los "
    "términos de la Licencia Pública General de GNU (GPL), versión 3 o "
    "posterior, publicada por la Free Software Foundation."
    "<br><br>"
    "Se distribuye <b>SIN NINGUNA GARANTÍA</b>, ni siquiera la garantía "
    "implícita de COMERCIABILIDAD o de APTITUD PARA UN PROPÓSITO PARTICULAR. "
    "Lo usás bajo tu responsabilidad: antes de reparar enlaces, tené una copia "
    "de tu librería."
)

_TRADEMARKS_TEXT = (
    "Rekordbox es una marca de AlphaTheta / Pioneer DJ. Traktor es una marca de "
    f"Native Instruments. {APP_NAME} es un proyecto independiente, sin afiliación "
    "ni respaldo de esas empresas; lee tu librería localmente para tu propio uso."
)


def _link(url: str, text: str, color: str) -> str:
    # El azul por defecto de Qt no se lee sobre el fondo oscuro.
    return f'<a href="{url}" style="color: {color};">{text}</a>'


class TextViewerDialog(QDialog):
    """Visor de solo lectura para LICENSE (texto plano) o los avisos (Markdown)."""

    def __init__(
        self, title: str, path: Path, *, markdown: bool, parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("text_viewer_dialog")
        self.setWindowTitle(f"{title} — {APP_NAME}")
        self.resize(680, 560)

        try:
            text = path.read_text(encoding="utf-8")
        except OSError:
            text = f"No se encontró {path.name}.\n\nEl texto completo está en {SOURCE_URL}"
            markdown = False

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        if markdown:
            view = QTextBrowser()
            view.setOpenExternalLinks(True)
            view.setMarkdown(text)
        else:
            view = QPlainTextEdit()
            view.setReadOnly(True)
            view.setPlainText(text)
        view.setObjectName("legal_text")
        layout.addWidget(view, 1)

        row = QHBoxLayout()
        if markdown and LICENSES_DIR.is_dir():
            folder_btn = QPushButton("Abrir carpeta de licencias")
            folder_btn.setObjectName("close_dialog_btn")
            folder_btn.clicked.connect(
                lambda: QDesktopServices.openUrl(QUrl.fromLocalFile(str(LICENSES_DIR)))
            )
            row.addWidget(folder_btn)
        row.addStretch(1)
        close_btn = QPushButton("Cerrar")
        close_btn.setObjectName("close_dialog_btn")
        close_btn.clicked.connect(self.accept)
        row.addWidget(close_btn)
        layout.addLayout(row)


def license_dialog(parent: QWidget | None = None) -> TextViewerDialog:
    return TextViewerDialog("Licencia (GPL v3)", LICENSE_PATH, markdown=False, parent=parent)


def notices_dialog(parent: QWidget | None = None) -> TextViewerDialog:
    return TextViewerDialog("Avisos de terceros", NOTICES_PATH, markdown=True, parent=parent)


class AboutDialog(QDialog):
    def __init__(
        self, version: str, theme: str = "dark", parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("about_dialog")
        self.setWindowTitle(f"Acerca de {APP_NAME}")
        self.setFixedWidth(440)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(28, 24, 28, 24)
        layout.setSpacing(12)

        title = QLabel(APP_NAME)
        title.setObjectName("dialog_title")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        apply_title_tracking(title, 17)
        layout.addWidget(title)

        meta = QLabel(f"Versión {version}<br>{COPYRIGHT}")
        meta.setObjectName("about_meta")
        meta.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(meta)

        for html in (_LEGAL_TEXT, _TRADEMARKS_TEXT):
            label = QLabel(html)
            label.setObjectName("about_body")
            label.setWordWrap(True)
            layout.addWidget(label)

        repo = _link(SOURCE_URL, SOURCE_URL.removeprefix("https://"), token(theme, "link"))
        source = QLabel(f"Código fuente: {repo}")
        source.setObjectName("about_body")
        source.setWordWrap(True)
        source.setOpenExternalLinks(True)
        source.setTextInteractionFlags(Qt.TextInteractionFlag.TextBrowserInteraction)
        layout.addWidget(source)

        row = QHBoxLayout()
        row.setSpacing(8)
        license_btn = QPushButton("Ver licencia")
        license_btn.setObjectName("close_dialog_btn")
        license_btn.clicked.connect(lambda: license_dialog(self).exec())
        notices_btn = QPushButton("Avisos de terceros")
        notices_btn.setObjectName("close_dialog_btn")
        notices_btn.clicked.connect(lambda: notices_dialog(self).exec())
        row.addWidget(license_btn)
        row.addWidget(notices_btn)
        layout.addLayout(row)

        close_btn = QPushButton("Cerrar")
        close_btn.setObjectName("kofi_btn")
        close_btn.setDefault(True)
        close_btn.clicked.connect(self.accept)
        layout.addWidget(close_btn)
