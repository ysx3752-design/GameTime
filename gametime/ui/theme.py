"""视觉主题：深色/浅色/跟随系统，低饱和、强调游戏数据本身。"""

from __future__ import annotations

COLORS_DARK = {
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

COLORS_LIGHT = {
    "bg": "#F5F6FA",
    "sidebar": "#EBEDF3",
    "surface": "#FFFFFF",
    "surface_2": "#F0F1F5",
    "surface_3": "#E6E8EE",
    "border": "#D8DBE3",
    "border_soft": "#E2E4EB",
    "text": "#1A1D26",
    "text_soft": "#3D4356",
    "muted": "#6B7080",
    "faint": "#9CA1AE",
    "accent": "#7C5CFF",
    "accent_hover": "#6B4CE6",
    "accent_soft": "#EDEAFF",
    "green": "#1BA97E",
    "green_soft": "#E3F8F0",
    "amber": "#D49A2A",
    "amber_soft": "#FFF5E0",
    "red": "#D94444",
    "red_soft": "#FFE8E8",
    "blue": "#3B8ADB",
}

# 主调色板（全局可变引用，通过 set_theme 就地更新）
COLORS: dict[str, str] = dict(COLORS_DARK)

# 深色模式下 build_stylesheet 使用的非 COLORS 硬编码色值
_EXTRA_DARK = {
    "scrollbar_handle": "#2B3850",
    "scrollbar_hover": "#3B4B69",
    "hero_grad_0": "#211C40",
    "hero_grad_55": "#18182E",
    "hero_grad_1": "#121927",
    "hero_border": "#322A5C",
    "live_grad_0": "#132924",
    "live_grad_1": "#101B20",
    "live_border": "#1D463B",
    "gamecard_hover_bg": "#151E2E",
    "gamecard_hover_border": "#2C3A54",
    "gamecard_active_border": "#285E50",
    "gamecard_active_bg": "#111F20",
    "gamecard_missing_bg": "#121823",
    "gamecard_missing_border": "#2A3447",
    "btn_hover_border": "#32415C",
    "btn_pressed": "#0F1623",
    "btn_disabled_color": "#566176",
    "btn_disabled_bg": "#101621",
    "btn_disabled_border": "#1A2231",
    "btn_primary_pressed": "#6B4CE6",
    "btn_danger_border": "#5B2A35",
    "btn_danger_hover_bg": "#42212B",
    "btn_danger_hover_border": "#7A3543",
    "btn_dangersolid_text": "#210D10",
    "nav_hover_bg": "#131B2A",
    "nav_checked_border": "#302A55",
    "nav_checked_color": "#D9D0FF",
    "iconbtn_hover_border": "#394762",
    "quick_active_border": "#5B2A35",
    "quick_active_hover": "#42212B",
    "quick_disabled_bg": "#1A2130",
    "quick_disabled_border": "#232D3F",
    "input_bg": "#0E1520",
    "input_hover_border": "#31405A",
    "input_focus_bg": "#101827",
    "input_disabled_bg": "#0C111A",
    "checkbox_border": "#33415A",
    "checkbox_bg": "#0E1520",
    "tooltip_bg": "#1D2738",
    "tooltip_border": "#34435D",
    "pill_purple_color": "#B9A8FF",
}

# 浅色模式下的等价色值
_EXTRA_LIGHT = {
    "scrollbar_handle": "#C8CCD5",
    "scrollbar_hover": "#AEB4BF",
    "hero_grad_0": "#E8E5F8",
    "hero_grad_55": "#EFECF8",
    "hero_grad_1": "#FFFFFF",
    "hero_border": "#D0CAE8",
    "live_grad_0": "#E3F8F0",
    "live_grad_1": "#EFF7F4",
    "live_border": "#B8DFD0",
    "gamecard_hover_bg": "#F0F1F5",
    "gamecard_hover_border": "#CDD1DB",
    "gamecard_active_border": "#89D4B8",
    "gamecard_active_bg": "#EAF8F2",
    "gamecard_missing_bg": "#F5F5F8",
    "gamecard_missing_border": "#D0D3DB",
    "btn_hover_border": "#C0C5D0",
    "btn_pressed": "#DDDFE5",
    "btn_disabled_color": "#A6ABB7",
    "btn_disabled_bg": "#ECEDF1",
    "btn_disabled_border": "#DDDFE5",
    "btn_primary_pressed": "#6B4CE6",
    "btn_danger_border": "#F0BFBF",
    "btn_danger_hover_bg": "#FCDADA",
    "btn_danger_hover_border": "#E89999",
    "btn_dangersolid_text": "#FFFFFF",
    "nav_hover_bg": "#E2E4EB",
    "nav_checked_border": "#C9C0EE",
    "nav_checked_color": "#5B3FCC",
    "iconbtn_hover_border": "#BFC4D0",
    "quick_active_border": "#F0BFBF",
    "quick_active_hover": "#FCDADA",
    "quick_disabled_bg": "#ECEDF1",
    "quick_disabled_border": "#DDDFE5",
    "input_bg": "#FFFFFF",
    "input_hover_border": "#B8BDC9",
    "input_focus_bg": "#FFFFFF",
    "input_disabled_bg": "#F0F1F5",
    "checkbox_border": "#BFC4D0",
    "checkbox_bg": "#FFFFFF",
    "tooltip_bg": "#FFFFFF",
    "tooltip_border": "#D0D3DB",
    "pill_purple_color": "#6B4CE6",
}

# 当前生效的额外色值（与 COLORS 配合使用）
_EXTRA: dict[str, str] = dict(_EXTRA_DARK)

# 当前生效的主题模式
_current_mode: str = "dark"
_effective_theme: str = "dark"

FONT_FAMILY = '"Microsoft YaHei UI", "Segoe UI", "PingFang SC", sans-serif'
NUMBER_FONT = '"Segoe UI Variable Display", "Segoe UI", "Microsoft YaHei UI", sans-serif'

THEME_LABELS = {"dark": "深色", "light": "浅色", "system": "跟随系统"}


def _is_system_dark() -> bool:
    """检测 Windows 系统当前是否为深色模式。"""
    try:
        import winreg

        with winreg.OpenKey(
            winreg.HKEY_CURRENT_USER,
            r"SOFTWARE\Microsoft\Windows\CurrentVersion\Themes\Personalize",
        ) as key:
            value, _ = winreg.QueryValueEx(key, "AppsUseLightTheme")
            return value == 0
    except Exception:
        return True  # 读取失败默认深色


def normalize_theme_mode(mode: str | None) -> str:
    return mode if mode in THEME_LABELS else "dark"


def system_theme() -> str:
    """返回 Windows 应用主题：``"dark"`` 或 ``"light"``。"""
    return "dark" if _is_system_dark() else "light"


def _resolve_theme(mode: str) -> str:
    mode = normalize_theme_mode(mode)
    return system_theme() if mode == "system" else mode


def set_theme(mode: str) -> str:
    """切换主题。mode 可为 ``"dark"``、``"light"``、``"system"``，返回实际生效主题。"""
    global _current_mode, _effective_theme
    _current_mode = normalize_theme_mode(mode)
    _effective_theme = _resolve_theme(_current_mode)
    source = COLORS_DARK if _effective_theme == "dark" else COLORS_LIGHT
    for key in source:
        COLORS[key] = source[key]
    extra_source = _EXTRA_DARK if _effective_theme == "dark" else _EXTRA_LIGHT
    for key in extra_source:
        _EXTRA[key] = extra_source[key]
    return _effective_theme


def current_theme_mode() -> str:
    return _current_mode


def effective_theme() -> str:
    return _effective_theme


def is_dark_active() -> bool:
    """当前是否正在使用深色调色板。"""
    return _effective_theme == "dark"


def rgba(color: str, alpha: int) -> str:
    """把 #RRGGBB 转为 QSS 可用的 rgba()。"""
    value = color.lstrip("#")
    if len(value) == 8:
        value = value[2:]
    if len(value) != 6:
        return color
    red, green, blue = (int(value[index : index + 2], 16) for index in (0, 2, 4))
    return f"rgba({red}, {green}, {blue}, {max(0, min(255, int(alpha)))})"


def apply_theme(app, mode: str) -> str:
    """应用主题到 QApplication，并刷新全局调色板与样式表。"""
    from PySide6.QtGui import QColor, QPalette

    effective = set_theme(mode)
    palette = QPalette()
    palette.setColor(QPalette.ColorRole.Window, QColor(COLORS["bg"]))
    palette.setColor(QPalette.ColorRole.WindowText, QColor(COLORS["text"]))
    palette.setColor(QPalette.ColorRole.Base, QColor(COLORS["surface"]))
    palette.setColor(QPalette.ColorRole.AlternateBase, QColor(COLORS["surface_2"]))
    palette.setColor(QPalette.ColorRole.Text, QColor(COLORS["text"]))
    palette.setColor(QPalette.ColorRole.Button, QColor(COLORS["surface_2"]))
    palette.setColor(QPalette.ColorRole.ButtonText, QColor(COLORS["text_soft"]))
    palette.setColor(QPalette.ColorRole.Highlight, QColor(COLORS["accent"]))
    palette.setColor(QPalette.ColorRole.HighlightedText, QColor("#FFFFFF"))
    palette.setColor(QPalette.ColorRole.ToolTipBase, QColor(COLORS["surface_2"]))
    palette.setColor(QPalette.ColorRole.ToolTipText, QColor(COLORS["text"]))
    palette.setColor(QPalette.ColorRole.PlaceholderText, QColor(COLORS["muted"]))
    palette.setColor(QPalette.ColorRole.Link, QColor(COLORS["accent"]))
    app.setPalette(palette)
    app.setStyleSheet(build_stylesheet())
    return effective



def build_stylesheet() -> str:
    c = COLORS
    e = _EXTRA
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
    background: {e['scrollbar_handle']};
    min-height: 36px;
    border-radius: 4px;
}}
QScrollBar::handle:vertical:hover {{
    background: {e['scrollbar_hover']};
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
    background: {e['scrollbar_handle']};
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
    color: {e['pill_purple_color']};
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
        stop:0 {e['hero_grad_0']}, stop:0.55 {e['hero_grad_55']}, stop:1 {e['hero_grad_1']});
    border: 1px solid {e['hero_border']};
    border-radius: 18px;
}}
QFrame#LiveCard {{
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
        stop:0 {e['live_grad_0']}, stop:1 {e['live_grad_1']});
    border: 1px solid {e['live_border']};
    border-radius: 16px;
}}
QFrame#GameCard {{
    background: {c['surface']};
    border: 1px solid {c['border_soft']};
    border-radius: 16px;
}}
QFrame#GameCard:hover {{
    background: {e['gamecard_hover_bg']};
    border: 1px solid {e['gamecard_hover_border']};
}}
QFrame#GameCard[active="true"] {{
    border: 1px solid {e['gamecard_active_border']};
    background: {e['gamecard_active_bg']};
}}
QFrame#GameCard[missing="true"] {{
    background: {e['gamecard_missing_bg']};
    border: 1px dashed {e['gamecard_missing_border']};
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
    border-color: {e['btn_hover_border']};
    color: {c['text']};
}}
QPushButton:pressed {{
    background: {e['btn_pressed']};
}}
QPushButton:disabled {{
    color: {e['btn_disabled_color']};
    background: {e['btn_disabled_bg']};
    border-color: {e['btn_disabled_border']};
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
    background: {e['btn_primary_pressed']};
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
    border: 1px solid {e['btn_danger_border']};
    color: {c['red']};
}}
QPushButton[variant="danger"]:hover {{
    background: {e['btn_danger_hover_bg']};
    border-color: {e['btn_danger_hover_border']};
}}
QPushButton[variant="dangerSolid"] {{
    background: {c['red']};
    border: 1px solid {c['red']};
    color: {e['btn_dangersolid_text']};
    font-weight: 700;
}}
QPushButton[variant="soft"] {{
    background: {c['surface_2']};
    border: 1px solid {c['border']};
    color: {c['text_soft']};
}}
QPushButton[themeChoice="true"] {{
    background: {c['surface_2']};
    border: 1px solid {c['border']};
    border-radius: 12px;
    padding: 11px 14px;
    color: {c['text_soft']};
    font-size: 12px;
    font-weight: 600;
    text-align: left;
}}
QPushButton[themeChoice="true"]:hover {{
    background: {c['surface_3']};
    border-color: {e['btn_hover_border']};
    color: {c['text']};
}}
QPushButton[themeChoice="true"]:checked {{
    background: {c['accent_soft']};
    border: 2px solid {c['accent']};
    color: {c['accent']};
    padding: 10px 13px;
}}
QPushButton[scope="true"] {{
    background: {c['surface_2']};
    border: 1px solid {c['border']};
    border-radius: 9px;
    padding: 7px 12px;
    color: {c['text_soft']};
    font-size: 11px;
    font-weight: 600;
}}
QPushButton[scope="true"]:hover {{
    background: {c['surface_3']};
    border-color: {e['btn_hover_border']};
}}
QPushButton[scope="true"]:checked {{
    background: {c['accent_soft']};
    border: 1px solid {c['accent']};
    color: {c['accent']};
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
    background: {e['nav_hover_bg']};
    color: {c['text_soft']};
}}
QPushButton#NavButton:checked {{
    background: {c['accent_soft']};
    border-color: {e['nav_checked_border']};
    color: {e['nav_checked_color']};
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
    border-color: {e['iconbtn_hover_border']};
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
    border: 1px solid {e['quick_active_border']};
}}
QPushButton#QuickButton[active="true"]:hover {{
    background: {e['quick_active_hover']};
}}
QPushButton#QuickButton:disabled {{
    background: {e['quick_disabled_bg']};
    border: 1px solid {e['quick_disabled_border']};
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
    background: {e['input_bg']};
    border: 1px solid {c['border']};
    border-radius: 10px;
    padding: 9px 12px;
    color: {c['text']};
    selection-background-color: {c['accent']};
    font-size: 13px;
}}
QLineEdit:hover, QTextEdit:hover, QComboBox:hover {{
    border-color: {e['input_hover_border']};
}}
QLineEdit:focus, QTextEdit:focus, QComboBox:focus {{
    border-color: {c['accent']};
    background: {e['input_focus_bg']};
}}
QLineEdit:disabled, QTextEdit:disabled {{
    color: {c['faint']};
    background: {e['input_disabled_bg']};
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
    border: 1px solid {e['checkbox_border']};
    background: {e['checkbox_bg']};
}}
QCheckBox::indicator:hover {{
    border-color: {c['accent']};
}}
QCheckBox::indicator:checked {{
    background: {c['accent']};
    border-color: {c['accent']};
}}

QToolTip {{
    background: {e['tooltip_bg']};
    color: {c['text']};
    border: 1px solid {e['tooltip_border']};
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
