"""styles.py — listBuddy design tokens + QSS loader."""
from __future__ import annotations

import logging
import sys
import tempfile
from pathlib import Path
from typing import Dict

from PySide6.QtGui import QFont, QFontDatabase
from PySide6.QtWidgets import QApplication, QLabel


# En modo frozen (PyInstaller) los recursos quedan en sys._MEIPASS
if getattr(sys, 'frozen', False) and hasattr(sys, '_MEIPASS'):
    ROOT = Path(sys._MEIPASS)
else:
    ROOT = Path(__file__).parent

FONTS_DIR = ROOT / 'fonts'
_log = logging.getLogger(__name__)

# Tokens «Mezcla Cálida» (T-061): única fuente de colores de la app
THEMES: Dict[str, Dict[str, str]] = {
    'dark': {
        'bg': '#161513',
        'header': '#1e1c19',
        'surface': '#1e1c19',
        'surface2': '#282520',
        'inset': '#121110',
        'line': '#3a362f',
        'row_line': '#2b2823',
        'text': '#f2ede4',
        'muted': '#aca59a',
        'accent': '#f0a93b',
        'on_accent': '#1a1408',
        'link': '#f0b24d',
        'sel_bg': '#2a251b',
        'danger': '#f2a79a',
        'danger_soft': '#3a2823',
        'broken_bg': '#2a1e1b',
        'broken_chip': '#3a2823',
        'ok': '#9fd6ad',
        'chip_text': '#c9c1b4',
    },
    'light': {
        'bg': '#f3efe7',
        'header': '#fbf9f4',
        'surface': '#fbf9f4',
        'surface2': '#ebe6db',
        'inset': '#f3efe7',
        'line': '#d6cfc1',
        'row_line': '#ebe6db',
        'text': '#1c1915',
        'muted': '#5b554b',
        'accent': '#8a5700',
        'on_accent': '#ffffff',
        'link': '#7a4e00',
        'sel_bg': '#f6e8cf',
        'danger': '#8a2a1a',
        'danger_soft': '#f1d2ca',
        'broken_bg': '#f9e5df',
        'broken_chip': '#f1d2ca',
        'ok': '#1f6b3a',
        'chip_text': '#4a443b',
    },
}


def register_fonts() -> list[str]:
    """Registra las fuentes OFL bundleadas; sin ellas la app arranca con fallback."""
    families: set[str] = set()
    for path in sorted(FONTS_DIR.glob('*.ttf')):
        font_id = QFontDatabase.addApplicationFont(str(path))
        if font_id == -1:
            _log.warning('No se pudo cargar la fuente %s', path.name)
            continue
        families.update(QFontDatabase.applicationFontFamilies(font_id))
    if not families:
        _log.warning('Sin fuentes bundleadas en %s; se usa el fallback del sistema', FONTS_DIR)
    return sorted(families)


TITLE_TRACKING_EM = -0.02


def apply_title_tracking(label: QLabel, px: int) -> None:
    """QSS no soporta letter-spacing: el tracking de marca/títulos va por QFont."""
    font = label.font()
    font.setLetterSpacing(QFont.SpacingType.AbsoluteSpacing, TITLE_TRACKING_EM * px)
    label.setFont(font)


COLUMN_TRACKING_EM = 0.06


def apply_caps_tracking(label: QLabel, px: int) -> None:
    """Tracking de la cabecera de columnas (QSS no soporta letter-spacing)."""
    font = label.font()
    font.setLetterSpacing(QFont.SpacingType.AbsoluteSpacing, COLUMN_TRACKING_EM * px)
    label.setFont(font)


def token(theme: str, name: str) -> str:
    return THEMES.get(theme, THEMES['dark'])[name]


def card_styles(theme: str) -> dict[str, str]:
    """Estilos inline del estado «marcada» de PlaylistCard (evitan polish en cascada)."""
    t = THEMES.get(theme, THEMES['dark'])
    return {
        'card_on': (
            f"QWidget#playlist_card {{ background: {t['sel_bg']};"
            f" border: 1.5px solid {t['sel_bg']}; border-radius: 8px; }}"
        ),
        'check_on': (
            f"background: {t['accent']}; border: 1.5px solid {t['accent']};"
            f" color: {t['on_accent']}; border-radius: 6px;"
        ),
    }


def status_style(theme: str, variant: str) -> str:
    key = {'ok': 'ok', 'warn': 'accent', 'error': 'danger'}.get(variant)
    if key is None:
        return ''
    c = token(theme, key)
    return f"color: {c}; border-color: {c};"


def _tick_url(tokens: Dict[str, str]) -> str:
    """QSS solo acepta imágenes por ruta: el tilde se rasteriza una vez por color."""
    import icons

    color = tokens['on_accent']
    path = Path(tempfile.gettempdir()) / 'listbuddy-qss' / f"tick-{color.lstrip('#')}.png"
    if not path.exists():
        path.parent.mkdir(parents=True, exist_ok=True)
        icons.pixmap('check', color, 18).save(str(path), 'PNG')
    return path.as_posix()


def load_qss(name: str = 'dark') -> str:
    path = ROOT / 'qss' / 'app.qss'
    if not path.exists():
        return ''
    qss = path.read_text(encoding='utf-8')
    tokens = THEMES.get(name, THEMES['dark'])
    for k, v in tokens.items():
        qss = qss.replace(f'@{{{k}}}', v)
    # El tilde va como regla extra: la ruta de la imagen no es un token de diseño.
    tick = _tick_url(tokens)
    return qss + f"\nQCheckBox#settings_check::indicator:checked {{ image: url({tick}); }}\n"


def apply_theme(app: QApplication, name: str = 'dark') -> None:
    qss = load_qss(name)
    if qss:
        app.setStyleSheet(qss)
