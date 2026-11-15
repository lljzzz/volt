import os
import sys
from types import SimpleNamespace


def _assets() -> str:
    if getattr(sys, "frozen", False):
        base = getattr(sys, "_MEIPASS", os.path.dirname(sys.executable))
    else:
        base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base, "assets").replace("\\", "/")


_A = _assets()

DARK = {
    "bg": "#121315", "bg_deep": "#0d0e10", "surface": "#17191c",
    "surface_2": "#1b1d21", "surface_3": "#24272c", "field": "#0f1012",
    "border": "#232629", "border_2": "#2a2d31", "border_3": "#3a3d42",
    "text": "#e6e6e6", "text_2": "#b7bac0", "text_dim": "#8b8e94",
    "text_muted": "#6f7378", "strong": "#ffffff", "soft": "#d4d6da",
    "button_fg": "#d0d0d0", "hover": "#232629", "hover_2": "#26282c",
    "pressed": "#2b2e33", "disabled_fg": "#5c5f64", "disabled_bg": "#17181b",
    "disabled_border": "#222428", "section": "#4f5358", "title": "#d7d7d7",
    "side_line": "#1d1f23", "header_bg": "#131417", "grid": "#1d1f23",
    "list_fg": "#cfcfcf", "scroll": "#2c2f34", "tooltip": "#1e2024",
    "check_hover": "#50545a", "check_off_bg": "#16171a",
    "check_off_border": "#2a2c30", "nav_hover": "#17191c",
    "nav_checked": "#1e2024", "palette_border": "#2f3237",
    "switch_off": "#3a3d42", "icon": "#c9ccd1", "icon_off": "#55585e",
    "item": "#d8dade", "item_dim": "#7b7f85",
    "green": "#2ec16a", "green_hover": "#3ad178", "running_ink": "#06140b",
    "red": "#e2574c", "amber": "#e8a03b",
    "danger_border": "#4a2a28", "danger_hover": "#2a1918",
    "toast_bg": "#26292e", "toast_fg": "#f2f2f2", "toast_border": "#383b41",
    "arrow": "spin", "track": "#1b1d21", "seg_track": "#0f1012",
}

LIGHT = {
    "bg": "#f3f4f6", "bg_deep": "#e8eaed", "surface": "#ffffff",
    "surface_2": "#f4f5f7", "surface_3": "#e2e5e9", "field": "#f7f8fa",
    "border": "#e2e4e8", "border_2": "#d4d7dc", "border_3": "#b7bbc2",
    "text": "#1c1e22", "text_2": "#3b3f46", "text_dim": "#5f646d",
    "text_muted": "#7a7f88", "strong": "#0d0e10", "soft": "#2b2e34",
    "button_fg": "#2b2e34", "hover": "#eceef1", "hover_2": "#e3e6ea",
    "pressed": "#dcdfe4", "disabled_fg": "#a5a9b0", "disabled_bg": "#f1f2f4",
    "disabled_border": "#e2e4e7", "section": "#8b9098", "title": "#2a2d33",
    "side_line": "#dcdfe3", "header_bg": "#f4f5f7", "grid": "#eceef1",
    "list_fg": "#2b2e34", "scroll": "#c6cad0", "tooltip": "#ffffff",
    "check_hover": "#8b9098", "check_off_bg": "#eef0f2",
    "check_off_border": "#d8dbe0", "nav_hover": "#e0e3e7",
    "nav_checked": "#d8dce1", "palette_border": "#d4d7dc",
    "switch_off": "#c2c6cc", "icon": "#4a4f57", "icon_off": "#b2b6bc",
    "item": "#23262b", "item_dim": "#979ca4",
    "green": "#1c9450", "green_hover": "#21a65a", "running_ink": "#04120a",
    "red": "#d4402f", "amber": "#b0721a",
    "danger_border": "#efc2bc", "danger_hover": "#fcecea",
    "toast_bg": "#2a2d33", "toast_fg": "#f5f5f5", "toast_border": "#2a2d33",
    "arrow": "spin_light", "track": "#e2e5e9", "seg_track": "#eceef1",
}

ACCENTS = {
    "orange": "#e8743b",
    "blue": "#4d8df6",
    "teal": "#1fb5a3",
    "pink": "#e85d8f",
    "violet": "#9776f0",
}
ACCENT_NAMES = [("orange", "Orange"), ("blue", "Blue"), ("teal", "Teal"),
                ("pink", "Pink"), ("violet", "Violet")]
THEMES = [("dark", "Dark"), ("light", "Light"), ("system", "Match Windows")]

T = SimpleNamespace()


def _rgb(hx: str) -> tuple[int, int, int]:
    hx = hx.lstrip("#")
    return int(hx[0:2], 16), int(hx[2:4], 16), int(hx[4:6], 16)


def mix(a: str, b: str, t: float) -> str:
    ra, rb = _rgb(a), _rgb(b)
    return "#{:02x}{:02x}{:02x}".format(
        *(round(x + (y - x) * t) for x, y in zip(ra, rb)))


def system_theme() -> str:
    try:
        from PySide6.QtCore import Qt
        from PySide6.QtGui import QGuiApplication
        scheme = QGuiApplication.styleHints().colorScheme()
        if scheme == Qt.ColorScheme.Light:
            return "light"
        if scheme == Qt.ColorScheme.Dark:
            return "dark"
    except Exception:
        pass
    if sys.platform.startswith("win"):
        try:
            import winreg
            key = winreg.OpenKey(
                winreg.HKEY_CURRENT_USER,
                r"Software\Microsoft\Windows\CurrentVersion\Themes\Personalize")
            try:
                value, _kind = winreg.QueryValueEx(key, "AppsUseLightTheme")
            finally:
                winreg.CloseKey(key)
            return "light" if value else "dark"
        except OSError:
            pass
    return "dark"


def set_theme(theme: str = "dark", accent: str = "orange"):
    name = "light" if theme == "light" else "dark"
    base = LIGHT if name == "light" else DARK
    T.__dict__.clear()
    T.__dict__.update(base)
    acc = ACCENTS.get(accent, ACCENTS["orange"])
    T.name = name
    T.accent_name = accent if accent in ACCENTS else "orange"
    T.accent = acc
    T.accent_hover = mix(acc, "#ffffff", 0.14)
    T.accent_pressed = mix(acc, "#000000", 0.08)
    T.accent_ink = mix(acc, "#000000", 0.88)
    T.accent_text = acc if name == "dark" else mix(acc, "#000000", 0.22)
    T.accent_off_bg = mix(acc, T.bg, 0.72)
    T.accent_off_fg = mix(acc, T.bg, 0.42)
    T.accent_soft = mix(acc, T.surface, 0.86)


def color(key) -> str:
    if not key:
        return ""
    return getattr(T, key, key)


def qss() -> str:
    c = T
    up, down = f"{_A}/{c.arrow}_up.png", f"{_A}/{c.arrow}_down.png"
    up_h, down_h = f"{_A}/{c.arrow}_up_h.png", f"{_A}/{c.arrow}_down_h.png"
    check = f"{_A}/check.png"
    return f"""
* {{
    font-family: 'Segoe UI', 'Inter', sans-serif;
    color: {c.text};
    font-size: 13px;
}}

QWidget#Root {{ background: {c.bg}; }}
QWidget#PageBody {{ background: transparent; }}
QScrollArea#PageScroll, QScrollArea#PageScroll > QWidget#qt_scrollarea_viewport {{
    background: {c.bg}; border: none;
}}
QDialog, QMessageBox, QInputDialog, QFileDialog {{ background: {c.surface}; }}

QWidget#TitleBar {{ background: {c.bg_deep}; }}
QLabel#TitleText {{ color: {c.title}; font-weight: 600; letter-spacing: 1px; }}
QLabel#TitleLogo {{ color: {c.accent}; }}
QPushButton#WinBtn, QPushButton#WinBtnClose {{
    background: transparent; border: none; color: {c.text_dim};
    border-radius: 6px; padding: 0;
}}
QPushButton#WinBtn:hover {{ background: {c.hover_2}; color: {c.strong}; }}
QPushButton#WinBtn:checked {{ background: {c.pressed}; color: {c.accent_text}; }}
QPushButton#WinBtnClose:hover {{ background: {c.red}; color: #ffffff; }}

QWidget#Sidebar {{ background: {c.bg_deep}; border-right: 1px solid {c.side_line}; }}
QLabel#SideSection {{
    color: {c.section}; font-size: 10px; font-weight: 700; letter-spacing: 1px;
    padding: 10px 12px 2px 12px;
}}
QLabel#SideVersion {{ color: {c.text_muted}; font-size: 11px; padding: 6px 12px 0 12px; }}

QFrame#Card {{
    background: {c.surface}; border: 1px solid {c.border}; border-radius: 12px;
}}
QFrame#Welcome {{
    background: {c.accent_soft}; border: 1px solid {c.accent_off_bg};
    border-radius: 12px;
}}
QFrame#Row {{
    background: {c.field}; border: 1px solid {c.border}; border-radius: 10px;
}}
QFrame#Tile {{
    background: {c.surface}; border: 1px solid {c.border}; border-radius: 12px;
}}
QFrame#Tile:hover {{ border: 1px solid {c.border_3}; }}
QLabel#TileValue {{ font-size: 20px; font-weight: 800; color: {c.strong}; }}
QLabel#TileValue[running="true"] {{ color: {c.green}; }}
QLabel#TileLabel {{ color: {c.text_dim}; font-size: 12px; font-weight: 600; }}
QLabel#TileGlyph {{ color: {c.text_dim}; }}
QLabel#TileGlyph[tone="accent"] {{ color: {c.accent}; }}
QLabel#TileGlyph[tone="green"] {{ color: {c.green}; }}
QLabel#CardTitle {{ font-size: 14px; font-weight: 700; color: {c.strong}; }}
QLabel#Muted {{ color: {c.text_muted}; }}
QLabel#Hint {{ color: {c.text_muted}; font-size: 12px; }}
QLabel#Warn {{ color: {c.amber}; font-size: 12px; }}
QLabel#Error {{ color: {c.red}; font-size: 12px; }}
QLabel#PageTitle {{ font-size: 22px; font-weight: 800; color: {c.strong}; }}
QLabel#PageSubtitle {{ color: {c.text_muted}; font-size: 12px; }}
QLabel#Accent {{ color: {c.accent_text}; font-weight: 700; }}
QLabel#Mono, QPlainTextEdit#Mono {{
    font-family: 'Cascadia Mono', 'Consolas', monospace;
}}
QLabel#Kbd {{
    background: {c.surface_2}; border: 1px solid {c.border_2}; border-radius: 5px;
    padding: 1px 6px; color: {c.text_2}; font-size: 11px; font-weight: 600;
}}
QLabel#BigTime {{ font-size: 18px; font-weight: 800; }}
QLabel#BigTime[paused="true"] {{ color: {c.text_muted}; }}
QLabel#Stopwatch {{
    font-size: 28px; font-weight: 800;
    font-family: 'Cascadia Mono', 'Consolas', monospace;
}}
QFrame#LiveSwatch {{ border: 1px solid {c.border_2}; border-radius: 10px; }}

QLineEdit, QSpinBox, QDoubleSpinBox, QPlainTextEdit, QTextEdit, QTimeEdit {{
    background: {c.field}; border: 1px solid {c.border_2}; border-radius: 8px;
    padding: 6px 10px; selection-background-color: {c.accent};
    selection-color: {c.accent_ink};
}}
QLineEdit:hover, QSpinBox:hover, QDoubleSpinBox:hover, QTimeEdit:hover {{
    border: 1px solid {c.border_3};
}}
QLineEdit:focus, QSpinBox:focus, QDoubleSpinBox:focus, QPlainTextEdit:focus,
QTextEdit:focus, QTimeEdit:focus {{
    border: 1px solid {c.accent};
}}
QLineEdit:disabled, QSpinBox:disabled, QDoubleSpinBox:disabled,
QPlainTextEdit:disabled {{ color: {c.disabled_fg}; }}
QPlainTextEdit, QTextEdit {{ padding: 8px 10px; }}

QSpinBox, QDoubleSpinBox, QTimeEdit {{ padding-right: 24px; }}
QSpinBox::up-button, QDoubleSpinBox::up-button, QTimeEdit::up-button,
QSpinBox::down-button, QDoubleSpinBox::down-button, QTimeEdit::down-button {{
    subcontrol-origin: border;
    width: 19px;
    background: {c.surface_2};
    border-left: 1px solid {c.border_2};
}}
QSpinBox::up-button, QDoubleSpinBox::up-button, QTimeEdit::up-button {{
    subcontrol-position: top right;
    border-top-right-radius: 7px;
}}
QSpinBox::down-button, QDoubleSpinBox::down-button, QTimeEdit::down-button {{
    subcontrol-position: bottom right;
    border-bottom-right-radius: 7px;
}}
QSpinBox::up-button:hover, QDoubleSpinBox::up-button:hover, QTimeEdit::up-button:hover,
QSpinBox::down-button:hover, QDoubleSpinBox::down-button:hover,
QTimeEdit::down-button:hover {{
    background: {c.hover_2};
}}
QSpinBox::up-arrow, QDoubleSpinBox::up-arrow, QTimeEdit::up-arrow {{
    image: url("{up}"); width: 8px; height: 5px;
}}
QSpinBox::down-arrow, QDoubleSpinBox::down-arrow, QTimeEdit::down-arrow {{
    image: url("{down}"); width: 8px; height: 5px;
}}
QSpinBox::up-arrow:hover, QDoubleSpinBox::up-arrow:hover, QTimeEdit::up-arrow:hover {{
    image: url("{up_h}");
}}
QSpinBox::down-arrow:hover, QDoubleSpinBox::down-arrow:hover,
QTimeEdit::down-arrow:hover {{
    image: url("{down_h}");
}}
QComboBox {{
    background: {c.field}; border: 1px solid {c.border_2}; border-radius: 8px;
    padding: 6px 10px;
}}
QComboBox:hover {{ border: 1px solid {c.border_3}; }}
QComboBox::drop-down {{ border: none; width: 22px; }}
QComboBox::down-arrow {{ image: url("{down}"); width: 8px; height: 5px; }}
QComboBox QAbstractItemView {{
    background: {c.surface}; border: 1px solid {c.border_2};
    selection-background-color: {c.surface_3}; selection-color: {c.strong};
    outline: none; padding: 4px;
}}

QListWidget, QListView {{
    background: {c.field}; border: 1px solid {c.border_2}; border-radius: 8px;
    outline: none; padding: 4px;
}}
QListWidget::item {{
    padding: 8px 10px; border-radius: 7px; color: {c.list_fg};
}}
QListWidget::item:hover {{ background: {c.surface}; }}
QListWidget::item:selected {{ background: {c.surface_3}; color: {c.strong}; }}
QTableWidget {{
    background: {c.field}; border: 1px solid {c.border_2}; border-radius: 8px;
    gridline-color: {c.grid}; outline: none;
    selection-background-color: {c.surface_3}; selection-color: {c.strong};
}}
QTableWidget::item {{ padding: 2px 6px; }}
QTableWidget::item:selected {{ background: {c.surface_3}; color: {c.strong}; }}
QTableWidget QLineEdit {{ border-radius: 0; padding: 2px 6px; }}
QHeaderView {{ background: transparent; }}
QHeaderView::section {{
    background: {c.header_bg}; color: {c.text_dim}; border: none;
    border-bottom: 1px solid {c.border}; padding: 6px 8px; font-weight: 700;
}}
QTableCornerButton::section {{ background: {c.header_bg}; border: none; }}
QCheckBox {{ color: {c.text_2}; spacing: 7px; }}
QCheckBox::indicator {{
    width: 15px; height: 15px; border-radius: 4px;
    border: 1px solid {c.border_3}; background: {c.field};
}}
QCheckBox::indicator:hover {{ border-color: {c.check_hover}; }}
QCheckBox::indicator:checked {{
    background: {c.accent}; border-color: {c.accent};
    image: url("{check}");
}}
QCheckBox::indicator:disabled {{
    background: {c.check_off_bg}; border-color: {c.check_off_border};
}}

QToolTip {{
    background: {c.tooltip}; color: {c.text}; border: 1px solid {c.border_2};
    padding: 5px 8px; border-radius: 6px;
}}

QMenu {{
    background: {c.surface}; border: 1px solid {c.border_2}; border-radius: 8px;
    padding: 5px;
}}
QMenu::item {{ padding: 7px 26px 7px 12px; border-radius: 6px; color: {c.soft}; }}
QMenu::item:selected {{ background: {c.surface_3}; color: {c.strong}; }}
QMenu::item:disabled {{ color: {c.disabled_fg}; }}
QMenu::separator {{ height: 1px; background: {c.border}; margin: 5px 8px; }}
QMenu::indicator {{ width: 14px; height: 14px; left: 6px; border-radius: 4px; }}
QMenu::indicator:checked {{ background: {c.accent}; image: url("{check}"); }}

QProgressBar {{
    background: {c.track}; border: none; border-radius: 3px; height: 6px;
    max-height: 6px; text-align: center; color: transparent;
}}
QProgressBar::chunk {{ background: {c.accent}; border-radius: 3px; }}

QSplitter::handle {{ background: transparent; }}
QSplitter::handle:horizontal {{ width: 10px; }}
QSplitter::handle:vertical {{ height: 10px; }}

QPushButton#Seg {{
    background: transparent; border: none; padding: 7px 16px;
    color: {c.text_dim}; font-weight: 600; border-radius: 7px;
}}
QPushButton#Seg:hover {{ color: {c.soft}; }}
QPushButton#Seg:checked {{ background: {c.pressed if c.name == "dark" else c.surface};
    color: {c.strong}; }}
QFrame#SegWrap {{
    background: {c.seg_track}; border: 1px solid {c.border_2}; border-radius: 9px;
}}

QPushButton {{
    background: {c.surface_2}; color: {c.button_fg}; border: 1px solid {c.border_2};
    border-radius: 9px; padding: 8px 16px; font-weight: 700;
}}
QPushButton:hover {{ background: {c.hover}; border-color: {c.border_3}; }}
QPushButton:pressed {{ background: {c.pressed}; }}
QPushButton:disabled {{
    color: {c.disabled_fg}; background: {c.disabled_bg};
    border-color: {c.disabled_border};
}}
QPushButton:focus {{ outline: none; }}
QPushButton#Primary {{
    background: {c.accent}; color: {c.accent_ink}; border: none;
    border-radius: 9px; padding: 9px 18px; font-weight: 800;
}}
QPushButton#Primary:hover {{ background: {c.accent_hover}; }}
QPushButton#Primary:pressed {{ background: {c.accent_pressed}; }}
QPushButton#Primary:disabled {{ background: {c.accent_off_bg}; color: {c.accent_off_fg}; }}
QPushButton#Danger {{
    background: transparent; color: {c.red}; border: 1px solid {c.danger_border};
    border-radius: 9px; padding: 8px 16px; font-weight: 700;
}}
QPushButton#Danger:hover {{ background: {c.danger_hover}; }}
QPushButton#Running {{
    background: {c.green}; color: {c.running_ink}; border: none;
    border-radius: 9px; padding: 9px 18px; font-weight: 800;
}}
QPushButton#Running:hover {{ background: {c.green_hover}; }}
QPushButton#Ghost {{
    background: {c.surface_2}; color: {c.button_fg}; border: 1px solid {c.border_2};
    border-radius: 9px; padding: 8px 16px; font-weight: 700;
}}
QPushButton#Ghost:hover {{ background: {c.hover}; border-color: {c.border_3}; }}
QPushButton#GhostSmall {{
    background: {c.surface_2}; color: {c.button_fg}; border: 1px solid {c.border_2};
    border-radius: 7px; padding: 4px 10px; font-weight: 700; font-size: 12px;
}}
QPushButton#GhostSmall:hover {{ background: {c.hover}; border-color: {c.border_3}; }}
QPushButton#GhostSmall:checked {{ background: {c.pressed}; color: {c.accent_text}; }}
QPushButton::menu-indicator {{
    image: url("{down}"); width: 8px; height: 5px;
    subcontrol-origin: padding; subcontrol-position: right center; right: 8px;
}}
QPushButton#GhostSmall[hasMenu="true"] {{ padding-right: 24px; }}
QPushButton#Hotkey {{
    background: {c.field}; color: {c.text}; border: 1px solid {c.border_2};
    border-radius: 8px; padding: 7px 14px; font-weight: 700;
}}
QPushButton#Hotkey:hover {{ border-color: {c.border_3}; }}
QPushButton#Hotkey[capturing="true"] {{
    border: 1px solid {c.accent}; color: {c.accent_text};
}}
QPushButton#Hotkey[empty="true"] {{ color: {c.text_muted}; font-weight: 600; }}
QPushButton#IconBtn {{
    background: transparent; border: none; border-radius: 6px; padding: 4px;
    color: {c.text_dim};
}}
QPushButton#IconBtn:hover {{ background: {c.surface_3}; color: {c.strong}; }}
QPushButton#Swatch {{ border-radius: 8px; padding: 0; border: 1px solid {c.border_2}; }}

QLabel#StatRunning {{ color: {c.green}; font-weight: 800; }}
QLabel#StatIdle {{ color: {c.text_muted}; font-weight: 800; }}

QLabel#Toast {{
    background: {c.toast_bg}; color: {c.toast_fg}; border: 1px solid {c.toast_border};
    border-radius: 9px; padding: 9px 16px; font-weight: 600;
}}

QFrame#Palette {{
    background: {c.surface}; border: 1px solid {c.palette_border}; border-radius: 12px;
}}
QLineEdit#PaletteInput {{
    background: transparent; border: none; border-bottom: 1px solid {c.border};
    border-radius: 0; font-size: 16px; padding: 8px 6px 10px 6px;
}}
QListWidget#PaletteList {{
    background: transparent; border: none; padding: 0;
}}

QScrollArea {{ border: none; background: transparent; }}
QScrollBar:vertical {{ background: transparent; width: 10px; margin: 2px; }}
QScrollBar:horizontal {{ background: transparent; height: 10px; margin: 2px; }}
QScrollBar::handle:vertical {{ background: {c.scroll}; border-radius: 3px; min-height: 30px; }}
QScrollBar::handle:horizontal {{ background: {c.scroll}; border-radius: 3px; min-width: 30px; }}
QScrollBar::handle:hover {{ background: {c.border_3}; }}
QScrollBar::add-line, QScrollBar::sub-line {{ height: 0; width: 0; }}
QScrollBar::add-page, QScrollBar::sub-page {{ background: transparent; }}
"""


set_theme()
