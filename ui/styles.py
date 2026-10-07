import os
import sys


def _assets() -> str:
    if getattr(sys, "frozen", False):
        base = getattr(sys, "_MEIPASS", os.path.dirname(sys.executable))
    else:
        base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base, "assets").replace("\\", "/")


_A = _assets()

BG = "#121315"
BG_DEEP = "#0d0e10"
SURFACE = "#17191c"
SURFACE_2 = "#1b1d21"
SURFACE_3 = "#24272c"
FIELD = "#0f1012"
BORDER = "#232629"
BORDER_2 = "#2a2d31"
BORDER_3 = "#3a3d42"
TEXT = "#e6e6e6"
TEXT_2 = "#b7bac0"
TEXT_DIM = "#8b8e94"
TEXT_MUTED = "#6f7378"
ACCENT = "#e8743b"
ACCENT_HOVER = "#f0884f"
ACCENT_INK = "#1a0f08"
GREEN = "#2ec16a"
RED = "#e2574c"
AMBER = "#e8a03b"

QSS = f"""
* {{
    font-family: 'Segoe UI', 'Inter', sans-serif;
    color: {TEXT};
    font-size: 13px;
}}

QWidget#Root {{ background: {BG}; }}
QWidget#PageBody {{ background: transparent; }}
QScrollArea#PageScroll, QScrollArea#PageScroll > QWidget#qt_scrollarea_viewport {{
    background: {BG}; border: none;
}}
QDialog, QMessageBox, QInputDialog, QFileDialog {{ background: {SURFACE}; }}

QWidget#TitleBar {{ background: {BG_DEEP}; }}
QLabel#TitleText {{ color: #d7d7d7; font-weight: 600; letter-spacing: 1px; }}
QLabel#TitleLogo {{ color: {ACCENT}; }}
QPushButton#WinBtn, QPushButton#WinBtnClose {{
    background: transparent; border: none; color: {TEXT_DIM};
    border-radius: 6px; padding: 0;
}}
QPushButton#WinBtn:hover {{ background: #26282c; color: #fff; }}
QPushButton#WinBtn:checked {{ background: #2b2e33; color: {ACCENT}; }}
QPushButton#WinBtnClose:hover {{ background: {RED}; color: #fff; }}

QWidget#Sidebar {{ background: {BG_DEEP}; border-right: 1px solid #1d1f23; }}
QLabel#SideSection {{
    color: #4f5358; font-size: 10px; font-weight: 700; letter-spacing: 1px;
    padding: 10px 12px 2px 12px;
}}

QFrame#Card {{
    background: {SURFACE}; border: 1px solid {BORDER}; border-radius: 12px;
}}
QFrame#Row {{
    background: {FIELD}; border: 1px solid {BORDER}; border-radius: 10px;
}}
QFrame#Tile {{
    background: {SURFACE}; border: 1px solid {BORDER}; border-radius: 12px;
}}
QFrame#Tile:hover {{ border: 1px solid {BORDER_3}; }}
QLabel#TileValue {{ font-size: 20px; font-weight: 800; color: #ffffff; }}
QLabel#TileLabel {{ color: {TEXT_DIM}; font-size: 12px; font-weight: 600; }}
QLabel#CardTitle {{ font-size: 14px; font-weight: 700; color: #f0f0f0; }}
QLabel#Muted {{ color: {TEXT_MUTED}; }}
QLabel#Hint {{ color: {TEXT_MUTED}; font-size: 12px; }}
QLabel#Warn {{ color: {AMBER}; font-size: 12px; }}
QLabel#Error {{ color: {RED}; font-size: 12px; }}
QLabel#PageTitle {{ font-size: 22px; font-weight: 800; color: #ffffff; }}
QLabel#PageSubtitle {{ color: {TEXT_MUTED}; font-size: 12px; }}
QLabel#Accent {{ color: {ACCENT}; font-weight: 700; }}
QLabel#Mono, QPlainTextEdit#Mono {{
    font-family: 'Cascadia Mono', 'Consolas', monospace;
}}
QLabel#Kbd {{
    background: {SURFACE_2}; border: 1px solid {BORDER_2}; border-radius: 5px;
    padding: 1px 6px; color: {TEXT_2}; font-size: 11px; font-weight: 600;
}}

QLineEdit, QSpinBox, QDoubleSpinBox, QPlainTextEdit, QTextEdit, QTimeEdit {{
    background: {FIELD}; border: 1px solid {BORDER_2}; border-radius: 8px;
    padding: 6px 10px; selection-background-color: {ACCENT};
    selection-color: {ACCENT_INK};
}}
QLineEdit:hover, QSpinBox:hover, QDoubleSpinBox:hover, QTimeEdit:hover {{
    border: 1px solid {BORDER_3};
}}
QLineEdit:focus, QSpinBox:focus, QDoubleSpinBox:focus, QPlainTextEdit:focus,
QTextEdit:focus, QTimeEdit:focus {{
    border: 1px solid {ACCENT};
}}
QLineEdit:disabled, QSpinBox:disabled, QDoubleSpinBox:disabled,
QPlainTextEdit:disabled {{ color: #5c5f64; }}
QPlainTextEdit, QTextEdit {{ padding: 8px 10px; }}

QSpinBox, QDoubleSpinBox, QTimeEdit {{ padding-right: 24px; }}
QSpinBox::up-button, QDoubleSpinBox::up-button, QTimeEdit::up-button,
QSpinBox::down-button, QDoubleSpinBox::down-button, QTimeEdit::down-button {{
    subcontrol-origin: border;
    width: 19px;
    background: {SURFACE_2};
    border-left: 1px solid {BORDER_2};
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
    background: #26282c;
}}
QSpinBox::up-arrow, QDoubleSpinBox::up-arrow, QTimeEdit::up-arrow {{
    image: url("{_A}/spin_up.png"); width: 8px; height: 5px;
}}
QSpinBox::down-arrow, QDoubleSpinBox::down-arrow, QTimeEdit::down-arrow {{
    image: url("{_A}/spin_down.png"); width: 8px; height: 5px;
}}
QSpinBox::up-arrow:hover, QDoubleSpinBox::up-arrow:hover, QTimeEdit::up-arrow:hover {{
    image: url("{_A}/spin_up_h.png");
}}
QSpinBox::down-arrow:hover, QDoubleSpinBox::down-arrow:hover,
QTimeEdit::down-arrow:hover {{
    image: url("{_A}/spin_down_h.png");
}}
QComboBox {{
    background: {FIELD}; border: 1px solid {BORDER_2}; border-radius: 8px;
    padding: 6px 10px;
}}
QComboBox:hover {{ border: 1px solid {BORDER_3}; }}
QComboBox::drop-down {{ border: none; width: 22px; }}
QComboBox::down-arrow {{ image: url("{_A}/spin_down.png"); width: 8px; height: 5px; }}
QComboBox QAbstractItemView {{
    background: {SURFACE}; border: 1px solid {BORDER_2};
    selection-background-color: {SURFACE_3}; outline: none; padding: 4px;
}}

QListWidget, QListView {{
    background: {FIELD}; border: 1px solid {BORDER_2}; border-radius: 8px;
    outline: none; padding: 4px;
}}
QListWidget::item {{
    padding: 8px 10px; border-radius: 7px; color: #cfcfcf;
}}
QListWidget::item:hover {{ background: {SURFACE}; }}
QListWidget::item:selected {{ background: {SURFACE_3}; color: #ffffff; }}
QTableWidget {{
    background: {FIELD}; border: 1px solid {BORDER_2}; border-radius: 8px;
    gridline-color: #1d1f23; outline: none;
    selection-background-color: {SURFACE_3}; selection-color: #ffffff;
}}
QTableWidget::item {{ padding: 2px 6px; }}
QTableWidget::item:selected {{ background: {SURFACE_3}; color: #ffffff; }}
QTableWidget QLineEdit {{ border-radius: 0; padding: 2px 6px; }}
QHeaderView {{ background: transparent; }}
QHeaderView::section {{
    background: #131417; color: {TEXT_DIM}; border: none;
    border-bottom: 1px solid {BORDER}; padding: 6px 8px; font-weight: 700;
}}
QTableCornerButton::section {{ background: #131417; border: none; }}
QCheckBox {{ color: {TEXT_2}; spacing: 7px; }}
QCheckBox::indicator {{
    width: 15px; height: 15px; border-radius: 4px;
    border: 1px solid {BORDER_3}; background: {FIELD};
}}
QCheckBox::indicator:hover {{ border-color: #50545a; }}
QCheckBox::indicator:checked {{
    background: {ACCENT}; border-color: {ACCENT};
    image: url("{_A}/check.png");
}}
QCheckBox::indicator:disabled {{ background: #16171a; border-color: #2a2c30; }}

QToolTip {{
    background: #1e2024; color: {TEXT}; border: 1px solid {BORDER_2};
    padding: 5px 8px; border-radius: 6px;
}}

QMenu {{
    background: {SURFACE}; border: 1px solid {BORDER_2}; border-radius: 8px;
    padding: 5px;
}}
QMenu::item {{ padding: 7px 26px 7px 12px; border-radius: 6px; color: #d4d6da; }}
QMenu::item:selected {{ background: {SURFACE_3}; color: #ffffff; }}
QMenu::item:disabled {{ color: #5c5f64; }}
QMenu::separator {{ height: 1px; background: {BORDER}; margin: 5px 8px; }}
QMenu::indicator {{ width: 14px; height: 14px; left: 6px; }}
QMenu::indicator:checked {{ image: url("{_A}/check_menu.png"); }}

QProgressBar {{
    background: {SURFACE_2}; border: none; border-radius: 3px; height: 6px;
    max-height: 6px; text-align: center; color: transparent;
}}
QProgressBar::chunk {{ background: {ACCENT}; border-radius: 3px; }}

QSplitter::handle {{ background: transparent; }}
QSplitter::handle:horizontal {{ width: 10px; }}
QSplitter::handle:vertical {{ height: 10px; }}

QPushButton#Seg {{
    background: transparent; border: none; padding: 7px 16px;
    color: {TEXT_DIM}; font-weight: 600; border-radius: 7px;
}}
QPushButton#Seg:hover {{ color: #d0d0d0; }}
QPushButton#Seg:checked {{ background: #2b2e33; color: #ffffff; }}
QFrame#SegWrap {{ background: {FIELD}; border: 1px solid {BORDER_2}; border-radius: 9px; }}

QPushButton {{
    background: {SURFACE_2}; color: #d0d0d0; border: 1px solid {BORDER_2};
    border-radius: 9px; padding: 8px 16px; font-weight: 700;
}}
QPushButton:hover {{ background: #232629; border-color: {BORDER_3}; }}
QPushButton:pressed {{ background: #2b2e33; }}
QPushButton:disabled {{ color: #5c5f64; background: #17181b; border-color: #222428; }}
QPushButton:focus {{ outline: none; }}
QPushButton#Primary {{
    background: {ACCENT}; color: {ACCENT_INK}; border: none;
    border-radius: 9px; padding: 9px 18px; font-weight: 800;
}}
QPushButton#Primary:hover {{ background: {ACCENT_HOVER}; }}
QPushButton#Primary:pressed {{ background: #d9682f; }}
QPushButton#Primary:disabled {{ background: #4a3426; color: #8a7466; }}
QPushButton#Danger {{
    background: transparent; color: {RED}; border: 1px solid #4a2a28;
    border-radius: 9px; padding: 8px 16px; font-weight: 700;
}}
QPushButton#Danger:hover {{ background: #2a1918; }}
QPushButton#Running {{
    background: {GREEN}; color: #06140b; border: none;
    border-radius: 9px; padding: 9px 18px; font-weight: 800;
}}
QPushButton#Running:hover {{ background: #3ad178; }}
QPushButton#Ghost {{
    background: {SURFACE_2}; color: #d0d0d0; border: 1px solid {BORDER_2};
    border-radius: 9px; padding: 8px 16px; font-weight: 700;
}}
QPushButton#Ghost:hover {{ background: #232629; border-color: {BORDER_3}; }}
QPushButton#GhostSmall {{
    background: {SURFACE_2}; color: #d0d0d0; border: 1px solid {BORDER_2};
    border-radius: 7px; padding: 4px 10px; font-weight: 700; font-size: 12px;
}}
QPushButton#GhostSmall:hover {{ background: #232629; border-color: {BORDER_3}; }}
QPushButton#GhostSmall:checked {{ background: #2b2e33; color: {ACCENT}; }}
QPushButton::menu-indicator {{
    image: url("{_A}/spin_down.png"); width: 8px; height: 5px;
    subcontrol-origin: padding; subcontrol-position: right center; right: 8px;
}}
QPushButton#GhostSmall[hasMenu="true"] {{ padding-right: 24px; }}
QPushButton#Hotkey {{
    background: {FIELD}; color: #e0e0e0; border: 1px solid {BORDER_2};
    border-radius: 8px; padding: 7px 14px; font-weight: 700;
}}
QPushButton#Hotkey:hover {{ border-color: {BORDER_3}; }}
QPushButton#Hotkey[capturing="true"] {{
    border: 1px solid {ACCENT}; color: {ACCENT};
}}
QPushButton#Hotkey[empty="true"] {{ color: {TEXT_MUTED}; font-weight: 600; }}
QPushButton#IconBtn {{
    background: transparent; border: none; border-radius: 6px; padding: 4px;
    color: {TEXT_DIM};
}}
QPushButton#IconBtn:hover {{ background: {SURFACE_3}; color: #ffffff; }}
QPushButton#Swatch {{ border-radius: 8px; padding: 0; }}

QLabel#StatRunning {{ color: {GREEN}; font-weight: 800; }}
QLabel#StatIdle {{ color: {TEXT_MUTED}; font-weight: 800; }}

QLabel#Toast {{
    background: #26292e; color: #f2f2f2; border: 1px solid #383b41;
    border-radius: 9px; padding: 9px 16px; font-weight: 600;
}}

QFrame#Palette {{
    background: {SURFACE}; border: 1px solid #2f3237; border-radius: 12px;
}}
QLineEdit#PaletteInput {{
    background: transparent; border: none; border-bottom: 1px solid {BORDER};
    border-radius: 0; font-size: 16px; padding: 8px 6px 10px 6px;
}}
QListWidget#PaletteList {{
    background: transparent; border: none; padding: 0;
}}

QScrollArea {{ border: none; background: transparent; }}
QScrollBar:vertical {{ background: transparent; width: 10px; margin: 2px; }}
QScrollBar:horizontal {{ background: transparent; height: 10px; margin: 2px; }}
QScrollBar::handle:vertical {{ background: #2c2f34; border-radius: 3px; min-height: 30px; }}
QScrollBar::handle:horizontal {{ background: #2c2f34; border-radius: 3px; min-width: 30px; }}
QScrollBar::handle:hover {{ background: {BORDER_3}; }}
QScrollBar::add-line, QScrollBar::sub-line {{ height: 0; width: 0; }}
QScrollBar::add-page, QScrollBar::sub-page {{ background: transparent; }}
"""
