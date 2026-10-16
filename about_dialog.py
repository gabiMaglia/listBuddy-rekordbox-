"""
about_dialog.py
---------------
«Acerca de»: los avisos legales que la GPLv3 (§0, §5d) pide en una interfaz
interactiva —copyright, licencia, falta de garantía y cómo ver la licencia—
más los avisos de terceros (THIRD_PARTY_NOTICES.md) que viajan en el bundle,
y el aviso legal para usuarios (DISCLAIMER.md), que se muestra resumido al
primer arranque y cada vez que cambia DISCLAIMER_VERSION.

Los textos se leen de disco (ROOT de styles: el repo o sys._MEIPASS). Si
falta un archivo el visor muestra el link al repo en vez de fallar.
"""
from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QSettings, Qt, QUrl
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

from branding import APP_NAME, COPYRIGHT, LICENSE_PRICE_USD, PURCHASE_URL, SOURCE_URL
from styles import ROOT, apply_title_tracking, token

LICENSE_PATH = ROOT / "LICENSE"
NOTICES_PATH = ROOT / "THIRD_PARTY_NOTICES.md"
LICENSES_DIR = ROOT / "licenses"
DISCLAIMER_PATH = ROOT / "DISCLAIMER.md"

# Igual a «Versión del aviso» de DISCLAIMER.md (un test lo verifica). Cambiarla
# vuelve a mostrar el aviso a quien ya lo había aceptado.
DISCLAIMER_VERSION = "2026-10-16.3"
_DISCLAIMER_KEY = "disclaimer_accepted"

_LEGAL_TEXT = (
    f"{APP_NAME} es software libre: podés redistribuirlo y modificarlo bajo los "
    "términos de la Licencia Pública General de GNU (GPL), versión 3 o "
    "posterior, publicada por la Free Software Foundation."
    "<br><br>"
    "Se distribuye <b>SIN NINGUNA GARANTÍA</b>, ni siquiera la garantía "
    "implícita de COMERCIABILIDAD o de APTITUD PARA UN PROPÓSITO PARTICULAR. "
    "Lo usás bajo tu responsabilidad: antes de reparar enlaces, tené una copia "
    "de tu librería."
    "<br><br>"
    "Si compraste tu copia, tenés además los derechos de garantía y devolución "
    "que te reconoce la ley de tu país (ver Aviso legal, sección 5 bis)."
)

_TRADEMARKS_TEXT = (
    "rekordbox es una marca de AlphaTheta Corporation. Pioneer DJ es una marca de "
    "Pioneer Corporation usada bajo licencia. Traktor es una marca de Native "
    f"Instruments GmbH. {APP_NAME} es un proyecto independiente: no es un "
    "producto oficial ni está afiliado, patrocinado ni respaldado por esas "
    "empresas; lee tu librería localmente, para tu propio uso."
)


_SALE_TEXT = (
    f"Licencia de uso y soporte: USD {LICENSE_PRICE_USD}, a través de Polar "
    "(polar.sh), que cobra los impuestos y te factura. El programa se puede "
    "descargar de Releases; lo que se paga es la licencia de uso con soporte, "
    "no una donación."
)


def _link(url: str, text: str, color: str) -> str:
    # El azul por defecto de Qt no se lee sobre el fondo oscuro.
    return f'<a href="{url}" style="color: {color};">{text}</a>'


class TextViewerDialog(QDialog):
    """Visor de solo lectura para LICENSE (texto plano) o los avisos (Markdown)."""

    def __init__(
        self, title: str, path: Path, *, markdown: bool,
        parent: QWidget | None = None, licenses_folder: bool = False,
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
        if licenses_folder and LICENSES_DIR.is_dir():
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
    return TextViewerDialog(
        "Avisos de terceros", NOTICES_PATH, markdown=True, parent=parent, licenses_folder=True,
    )


def disclaimer_dialog(parent: QWidget | None = None) -> TextViewerDialog:
    return TextViewerDialog("Aviso legal", DISCLAIMER_PATH, markdown=True, parent=parent)


def disclaimer_pending(settings: QSettings) -> bool:
    return str(settings.value(_DISCLAIMER_KEY, "") or "") != DISCLAIMER_VERSION


def mark_disclaimer_accepted(settings: QSettings) -> None:
    settings.setValue(_DISCLAIMER_KEY, DISCLAIMER_VERSION)
    settings.sync()


_NOTICE_TEXT = (
    f"{APP_NAME} es software libre (GPL v3) y se ofrece <b>tal cual, sin garantía "
    "comercial</b>. Lo usás bajo tu responsabilidad y con los derechos que te da "
    "la ley de tu país."
    "<br><br>"
    "• Con Rekordbox solo lee el XML que exportás: nunca modifica tu librería ni tu XML. "
    "Las reparaciones se guardan en List Buddy.<br>"
    "• Con Traktor, «Reparar enlaces rotos» y «Restaurar» <b>sobrescriben tu "
    "colección</b> (<code>collection.nml</code>, un archivo tuyo). Hace una copia de "
    "seguridad automática, pero no reemplaza la tuya.<br>"
    "• Una coincidencia automática puede apuntar al archivo equivocado: revisá "
    "tu librería antes de tocar en vivo."
    "<br><br>"
    "No respondemos por la pérdida o corrupción de librerías, playlists, "
    "cue points ni archivos de música más allá de lo que la ley establezca. "
    "<b>Hacé tu propia copia de seguridad</b> antes de reparar o restaurar."
    "<br><br>"
    f"{APP_NAME} no es un producto oficial de AlphaTheta (rekordbox) ni de "
    "Native Instruments (Traktor)."
)


class FirstRunNoticeDialog(QDialog):
    """Resumen del aviso legal. «Entendido» lo da por aceptado; cerrarlo, no."""

    def __init__(self, theme: str = "dark", parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("about_dialog")
        self.setWindowTitle(f"Antes de empezar — {APP_NAME}")
        self.setFixedWidth(460)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(28, 24, 28, 24)
        layout.setSpacing(14)

        title = QLabel("Antes de empezar")
        title.setObjectName("dialog_title")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        apply_title_tracking(title, 17)
        layout.addWidget(title)

        body = QLabel(_NOTICE_TEXT)
        body.setObjectName("about_body")
        body.setWordWrap(True)
        layout.addWidget(body)

        row = QHBoxLayout()
        row.setSpacing(8)
        full_btn = QPushButton("Leer el aviso completo")
        full_btn.setObjectName("close_dialog_btn")
        full_btn.clicked.connect(lambda: disclaimer_dialog(self).exec())
        ok_btn = QPushButton("Entendido")
        ok_btn.setObjectName("kofi_btn")
        ok_btn.setDefault(True)
        ok_btn.clicked.connect(self.accept)
        row.addWidget(full_btn)
        row.addWidget(ok_btn, 1)
        layout.addLayout(row)


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
        source = QLabel(
            f"Código fuente: el código de cada versión está en {repo}. {APP_NAME} es "
            "software libre (GPL v3): podés compilarlo vos."
        )
        source.setObjectName("about_body")
        source.setWordWrap(True)
        source.setOpenExternalLinks(True)
        source.setTextInteractionFlags(Qt.TextInteractionFlag.TextBrowserInteraction)
        layout.addWidget(source)

        sale = QLabel(f"{_SALE_TEXT} {_link(PURCHASE_URL, 'Cómo comprar', token(theme, 'link'))}")
        sale.setObjectName("about_body")
        sale.setWordWrap(True)
        sale.setOpenExternalLinks(True)
        sale.setTextInteractionFlags(Qt.TextInteractionFlag.TextBrowserInteraction)
        layout.addWidget(sale)

        row = QHBoxLayout()
        row.setSpacing(8)
        license_btn = QPushButton("Ver licencia")
        license_btn.setObjectName("close_dialog_btn")
        license_btn.clicked.connect(lambda: license_dialog(self).exec())
        notices_btn = QPushButton("Avisos de terceros")
        notices_btn.setObjectName("close_dialog_btn")
        notices_btn.clicked.connect(lambda: notices_dialog(self).exec())
        disclaimer_btn = QPushButton("Aviso legal")
        disclaimer_btn.setObjectName("close_dialog_btn")
        disclaimer_btn.clicked.connect(lambda: disclaimer_dialog(self).exec())
        row.addWidget(license_btn)
        row.addWidget(notices_btn)
        row.addWidget(disclaimer_btn)
        layout.addLayout(row)

        close_btn = QPushButton("Cerrar")
        close_btn.setObjectName("kofi_btn")
        close_btn.setDefault(True)
        close_btn.clicked.connect(self.accept)
        layout.addWidget(close_btn)
