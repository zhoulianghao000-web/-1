"""深色主题与 QSS（PRD §6 全局窗口约束）。

只使用 PySide6 内置控件，不引入任何第三方 UI 库。
"""
from __future__ import annotations

BG = '#0f1115'
PANEL = '#161a21'
LINE = '#242a34'
TEXT = '#e6e9ef'
SUB = '#8b93a3'
BRAND = '#07c160'
BRAND_DARK = '#06ad56'
WARN = '#e8a33d'
ERROR = '#e5484d'

QSS = f"""
QWidget {{
    background: {BG};
    color: {TEXT};
    font-family: "Microsoft YaHei", "Segoe UI", sans-serif;
    font-size: 13px;
}}
QLabel {{ background: transparent; }}
QPushButton {{
    background: {BG};
    border: 1px solid {LINE};
    border-radius: 8px;
    padding: 6px 12px;
    color: {TEXT};
}}
QPushButton:hover {{ border-color: {BRAND_DARK}; }}
QPushButton:disabled {{ color: #5b6270; border-color: {LINE}; }}
QPushButton[primary="true"] {{
    background: {BRAND_DARK};
    border: 1px solid {BRAND_DARK};
    color: #ffffff;
}}
QPushButton[primary="true"]:disabled {{
    background: #1d232c;
    border-color: {LINE};
    color: #5b6270;
}}
QToolButton {{
    background: transparent;
    border: none;
    padding: 4px 8px;
    color: {SUB};
}}
QToolButton:hover {{ color: {TEXT}; }}
"""
