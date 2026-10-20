"""视觉主题：深色、低饱和、强调游戏数据本身。"""

from __future__ import annotations

COLORS = {
    "bg": "#0A0E16",
    "sidebar": "#0D1220",
    "surface": "#121927",
    "surface_2": "#161F30",
    "surface_3": "#1B2537",
    "border": "#202B3E",
    "border_soft": "#1A2434",
    "text": "#EDF1F8",
    "text_soft": "#C4CCDA",
    "muted": "#8995AA",
    "faint": "#5F6B80",
    "accent": "#7C5CFF",
    "accent_hover": "#8D72FF",
    "accent_soft": "#221F44",
    "green": "#35D6A5",
    "green_soft": "#132F2A",
    "amber": "#F3B24A",
    "amber_soft": "#322817",
    "red": "#F07171",
    "red_soft": "#331B23",
    "blue": "#55A7FF",
}

FONT_FAMILY = '"Microsoft YaHei UI", "Segoe UI", "PingFang SC", sans-serif'
NUMBER_FONT = '"Segoe UI Variable Display", "Segoe UI", "Microsoft YaHei UI", sans-serif'


def build_stylesheet() -> str:
    c = COLORS
    return f"""
* {{
    font-family: {FONT_FAMILY};
    color: {c['text']};
    outline: none;
}}
QMainWindow, QDialog, QMessageBox {{
    background: {c['bg']};
}}
QWidget#AppRoot, QWidget#Page, QWidget#ScrollContent {{
    background: transparent;
}}
QScrollArea {{
    background: transparent;
    border: none;
}}
QScrollArea > QWidget > QWidget {{
    background: transparent;
}}
QScrollBar:vertical {{
    background: transparent;
    width: 9px;
    margin: 2px;
}}
QScrollBar::handle:vertical {{
    background: #2B3850;
    min-height: 36px;
    border-radius: 4px;
}}
QScrollBar::handle:vertical:hover {{
    background: #3B4B69;
}}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical,
QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{
    background: none;
    height: 0;
}}
QScrollBar:horizontal {{
    background: transparent;
    height: 9px;
    margin: 2px;
}}
QScrollBar::handle:horizontal {{
    background: #2B3850;
    min-width: 36px;
    border-radius: 4px;
}}
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{
    width: 0;
}}

QFrame#Sidebar {{
    background: {c['sidebar']};
    border-right: 1px solid {c['border_soft']};
}}
QLabel#LogoTitle {{
    font-size: 21px;
    font-weight: 700;
    letter-spacing: 1px;
}}
QLabel#LogoSub {{
    color: {c['faint']};
    font-size: 9px;
    letter-spacing: 2px;
}}
QLabel[role="display"] {{
    font-family: {NUMBER_FONT};
    font-size: 31px;
    font-weight: 700;
    color: {c['text']};
}}
QLabel[role="h1"] {{
    font-size: 26px;
    font-weight: 700;
}}
QLabel[role="h2"] {{
    font-size: 18px;
    font-weight: 600;
}}
QLabel[role="h3"] {{
    font-size: 15px;
    font-weight: 600;
}}
QLabel[role="body"] {{
    font-size: 13px;
    color: {c['text_soft']};
}}
QLabel[role="muted"] {{
    font-size: 12px;
    color: {c['muted']};
}}
QLabel[role="faint"] {{
    font-size: 11px;
    color: {c['faint']};
}}
QLabel[role="accent"] {{
    color: {c['accent']};
    font-size: 12px;
    font-weight: 600;
}}
QLabel[role="danger"] {{
    color: {c['red']};
    font-size: 12px;
}}
QLabel[role="section"] {{
    font-size: 11px;
    font-weight: 600;
    color: {c['faint']};
    letter-spacing: 1px;
}}
QLabel[role="number"] {{
    font-family: {NUMBER_FONT};
    font-size: 25px;
    font-weight: 700;
}}
QLabel[role="number-sm"] {{
    font-family: {NUMBER_FONT};
    font-size: 19px;
    font-weight: 700;
}}
QLabel[role="pill"] {{
    border-radius: 10px;
    padding: 3px 9px;
    font-size: 11px;
    font-weight: 600;
}}
QLabel[pill="green"] {{
    color: {c['green']};
    background: {c['green_soft']};
}}
QLabel[pill="amber"] {{
    color: {c['amber']};
    background: {c['amber_soft']};
}}
QLabel[pill="purple"] {{
    color: #B9A8FF;
    background: {c['accent_soft']};
}}
QLabel[pill="neutral"] {{
    color: {c['muted']};
    background: {c['surface_3']};
}}

QFrame[card="true"] {{
    background: {c['surface']};
    border: 1px solid {c['border_soft']};
    border-radius: 16px;
}}
QFrame[card="soft"] {{
    background: {c['surface_2']};
    border: 1px solid {c['border_soft']};
    border-radius: 14px;
}}
QFrame#HeroCard {{
    background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
        stop:0 #211C40, stop:0.55 #18182E, stop:1 #121927);
    border: 1px solid #322A5C;
    border-radius: 18px;
}}
QFrame#LiveCard {{
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
        stop:0 #132924, stop:1 #101B20);
    border: 1px solid #1D463B;
    border-radius: 16px;
}}
QFrame#GameCard {{
    background: {c['surface']};
    border: 1px solid {c['border_soft']};
    border-radius: 16px;
}}
QFrame#GameCard:hover {{
    background: #151E2E;
    border: 1px solid #2C3A54;
}}
QFrame#GameCard[active="true"] {{
    border: 1px solid #285E50;
    background: #111F20;
}}
QFrame#GameCard[missing="true"] {{
    background: #121823;
    border: 1px dashed #2A3447;
}}

QPushButton {{
    background: {c['surface_2']};
    border: 1px solid {c['border']};
    border-radius: 10px;
    padding: 8px 14px;
    color: {c['text_soft']};
    font-size: 12px;
    font-weight: 500;
}}
QPushButton:hover {{
    background: {c['surface_3']};
    border-color: #32415C;
    color: {c['text']};
}}
QPushButton:pressed {{
    background: #0F1623;
}}
QPushButton:disabled {{
    color: #566176;
    background: #101621;
    border-color: #1A2231;
}}
QPushButton[variant="primary"] {{
    background: {c['accent']};
    border: 1px solid {c['accent']};
    color: white;
    font-weight: 600;
    padding: 9px 16px;
}}
QPushButton[variant="primary"]:hover {{
    background: {c['accent_hover']};
    border-color: {c['accent_hover']};
}}
QPushButton[variant="primary"]:pressed {{
    background: #6B4CE6;
}}
QPushButton[variant="ghost"] {{
    background: transparent;
    border: 1px solid transparent;
    color: {c['muted']};
    padding: 7px 10px;
}}
QPushButton[variant="ghost"]:hover {{
    background: {c['surface_2']};
    color: {c['text']};
}}
QPushButton[variant="danger"] {{
    background: {c['red_soft']};
    border: 1px solid #5B2A35;
    color: {c['red']};
}}
QPushButton[variant="danger"]:hover {{
    background: #42212B;
    border-color: #7A3543;
}}
QPushButton[variant="dangerSolid"] {{
    background: {c['red']};
    border: 1px solid {c['red']};
    color: #210D10;
    font-weight: 700;
}}
QPushButton[variant="soft"] {{
    background: {c['surface_2']};
    border: 1px solid {c['border']};
    color: {c['text_soft']};
}}
QPushButton#NavButton {{
    background: transparent;
    border: 1px solid transparent;
    border-radius: 11px;
    padding: 10px 12px;
    text-align: left;
    color: {c['muted']};
    font-size: 13px;
    font-weight: 500;
}}
QPushButton#NavButton:hover {{
    background: #131B2A;
    color: {c['text_soft']};
}}
QPushButton#NavButton:checked {{
    background: {c['accent_soft']};
    border-color: #302A55;
    color: #D9D0FF;
    font-weight: 600;
}}
QPushButton#IconButton {{
    background: {c['surface_2']};
    border: 1px solid {c['border']};
    border-radius: 18px;
    padding: 0;
}}
QPushButton#IconButton:hover {{
    background: {c['surface_3']};
    border-color: #394762;
}}
QPushButton#QuickButton {{
    background: {c['accent']};
    border: none;
    border-radius: 18px;
    padding: 0;
}}
QPushButton#QuickButton:hover {{
    background: {c['accent_hover']};
}}
QPushButton#QuickButton[active="true"] {{
    background: {c['red_soft']};
    border: 1px solid #5B2A35;
}}
QPushButton#QuickButton[active="true"]:hover {{
    background: #42212B;
}}
QPushButton#QuickButton:disabled {{
    background: #1A2130;
    border: 1px solid #232D3F;
}}
QPushButton#WindowButton {{
    background: transparent;
    border: none;
    border-radius: 7px;
    padding: 4px;
}}
QPushButton#WindowButton:hover {{
    background: {c['surface_3']};
}}
QPushButton#CloseWindowButton {{
    background: transparent;
    border: none;
    border-radius: 7px;
    padding: 4px;
}}
QPushButton#CloseWindowButton:hover {{
    background: {c['red_soft']};
}}

QLineEdit, QTextEdit, QComboBox, QSpinBox {{
    background: #0E1520;
    border: 1px solid {c['border']};
    border-radius: 10px;
    padding: 9px 12px;
    color: {c['text']};
    selection-background-color: {c['accent']};
    font-size: 13px;
}}
QLineEdit:hover, QTextEdit:hover, QComboBox:hover {{
    border-color: #31405A;
}}
QLineEdit:focus, QTextEdit:focus, QComboBox:focus {{
    border-color: {c['accent']};
    background: #101827;
}}
QLineEdit:disabled, QTextEdit:disabled {{
    color: {c['faint']};
    background: #0C111A;
}}
QLineEdit[error="true"] {{
    border-color: {c['red']};
}}
QComboBox {{
    padding-right: 28px;
}}
QComboBox::drop-down {{
    border: none;
    width: 26px;
}}
QComboBox QAbstractItemView {{
    background: {c['surface_2']};
    border: 1px solid {c['border']};
    border-radius: 8px;
    padding: 4px;
    selection-background-color: {c['accent_soft']};
    color: {c['text']};
    outline: none;
}}
QComboBox::item {{
    min-height: 26px;
    padding-left: 8px;
}}

QCheckBox {{
    spacing: 10px;
    color: {c['text_soft']};
    font-size: 13px;
}}
QCheckBox::indicator {{
    width: 18px;
    height: 18px;
    border-radius: 5px;
    border: 1px solid #33415A;
    background: #0E1520;
}}
QCheckBox::indicator:hover {{
    border-color: {c['accent']};
}}
QCheckBox::indicator:checked {{
    background: {c['accent']};
    border-color: {c['accent']};
}}

QToolTip {{
    background: #1D2738;
    color: {c['text']};
    border: 1px solid #34435D;
    border-radius: 6px;
    padding: 5px 8px;
    font-size: 11px;
}}

QMenu {{
    background: {c['surface_2']};
    border: 1px solid {c['border']};
    border-radius: 10px;
    padding: 6px;
}}
QMenu::item {{
    padding: 7px 26px 7px 12px;
    border-radius: 6px;
    color: {c['text_soft']};
    font-size: 12px;
}}
QMenu::item:selected {{
    background: {c['accent_soft']};
    color: {c['text']};
}}
QMenu::separator {{
    height: 1px;
    background: {c['border']};
    margin: 5px 8px;
}}

QDialog#ContentDialog {{
    background: {c['bg']};
}}
QFrame#DialogHeader {{
    background: transparent;
    border-bottom: 1px solid {c['border_soft']};
}}
QFrame#DialogFooter {{
    background: transparent;
    border-top: 1px solid {c['border_soft']};
}}
QFrame#Divider {{
    background: {c['border_soft']};
    border: none;
    max-height: 1px;
    min-height: 1px;
}}
"""
