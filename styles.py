"""styles.py — listBuddy design tokens + QSS loader."""
from __future__ import annotations

import sys
from pathlib import Path
from typing import Dict

from PyQt6.QtWidgets import QApplication


# En modo frozen (PyInstaller) los recursos quedan en sys._MEIPASS
if getattr(sys, 'frozen', False) and hasattr(sys, '_MEIPASS'):
    ROOT = Path(sys._MEIPASS)
else:
    ROOT = Path(__file__).parent

# Design tokens translated from listBuddy CSS (oklch → hex approximations)
THEMES: Dict[str, Dict[str, str]] = {
    'dark': {
        'bg':          '#1b1927',
        'surface':     '#221f30',
        'surface2':    '#2a2738',
        'inset':       '#151321',
        'line':        '#38354a',
        'line2':       '#2c2a3d',
        'text':        '#f3f2f8',
        'muted':       '#9893a8',
        'faint':       '#6b677a',
        'accent':      '#ce7de6',
        'accent2':     '#b053d4',
        'accent_soft': 'rgba(206, 125, 230, 36)',
        'on_accent':   '#1e0d29',
        'title_bar':   '#231f31',
    },
    'light': {
        'bg':          '#f4f3f9',
        'surface':     '#fdfcff',
        'surface2':    '#f8f7fc',
        'inset':       '#f3f2f9',
        'line':        '#dddbe8',
        'line2':       '#eceaf3',
        'text':        '#2c2838',
        'muted':       '#736d85',
        'faint':       '#9e99b1',
        'accent':      '#8c38bf',
        'accent2':     '#7828ab',
        'accent_soft': 'rgba(140, 56, 191, 26)',
        'on_accent':   '#fefefe',
        'title_bar':   '#f9f8fc',
    },
}


def load_qss(name: str = 'dark') -> str:
    path = ROOT / 'qss' / f'{name}.qss'
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
