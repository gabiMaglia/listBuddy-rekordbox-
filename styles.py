"""styles.py — listBuddy design tokens + QSS loader."""
from __future__ import annotations

import sys
from pathlib import Path
from typing import Dict

from PySide6.QtWidgets import QApplication


# En modo frozen (PyInstaller) los recursos quedan en sys._MEIPASS
if getattr(sys, 'frozen', False) and hasattr(sys, '_MEIPASS'):
    ROOT = Path(sys._MEIPASS)
else:
    ROOT = Path(__file__).parent

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


def token(theme: str, name: str) -> str:
    return THEMES.get(theme, THEMES['dark'])[name]


def card_styles(theme: str) -> dict[str, str]:
    """Estilos inline del estado «marcada» de PlaylistCard (evitan polish en cascada)."""
    t = THEMES.get(theme, THEMES['dark'])
    return {
        'card_on': (
            f"QWidget#playlist_card {{ background: {t['sel_bg']};"
            f" border: 1.5px solid {t['accent']}; border-radius: 12px; }}"
        ),
        'order_on': f"color: {t['link']};",
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


def load_qss(name: str = 'dark') -> str:
    path = ROOT / 'qss' / 'app.qss'
    if not path.exists():
        return ''
    qss = path.read_text(encoding='utf-8')
    tokens = THEMES.get(name, THEMES['dark'])
    for k, v in tokens.items():
        qss = qss.replace(f'@{{{k}}}', v)
    return qss


def apply_theme(app: QApplication, name: str = 'dark') -> None:
    qss = load_qss(name)
    if qss:
        app.setStyleSheet(qss)
