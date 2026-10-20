"""Visual language: colours, fonts and the global stylesheet."""
from __future__ import annotations

from string import Template

from PySide6.QtGui import QColor, QFont, QFontDatabase, QPalette

from ..paths import asset_path

PALETTE = {
    "BG": "#0e0c09",
    "BG_DEEP": "#0a0907",
    "CARD": "#17140f",
    "CARD_HI": "#1d1912",
    "BORDER": "#2b2419",
    "BORDER_HI": "#3a3020",
    "TEXT": "#e9e1ce",
    "MUTED": "#988d78",
    "DIM": "#6b6252",
    "GOLD": "#c9a45f",
    "GOLD_HI": "#e6c688",
    "GOLD_DIM": "#8a6f3e",
    "EMBER": "#c9603a",
    "RED": "#b3452f",
    "GREEN": "#7d9b6a",
    "SLATE": "#78909c",
}

CHECK_ICON = str(asset_path("check.svg")).replace("\\", "/")

_QSS = Template("""
* { outline: none; }
QWidget {
    color: $TEXT;
    font-family: "Noto Sans", "DejaVu Sans", sans-serif;
    font-size: 13px;
}
QWidget#Root { background: $BG; }
QMainWindow { background: $BG; }

QFrame#Card {
    background: $CARD;
    border: 1px solid $BORDER;
    border-radius: 12px;
}
QFrame#Card QLabel { background: transparent; }

QLabel#H1 {
    font-family: "Cinzel", "Noto Serif", serif;
    font-size: 27px;
    font-weight: 600;
    color: $TEXT;
}
QLabel#Tagline { color: $MUTED; font-size: 9px; }
QLabel#Eyebrow { color: $GOLD_DIM; font-size: 9px; font-weight: 700; }
QLabel#FileName {
    font-family: "Cinzel", "Noto Serif", serif;
    font-size: 17px;
    color: $TEXT;
}
QLabel#Muted { color: $MUTED; font-size: 12px; }
QLabel#Small { color: $DIM; font-size: 11px; }
QLabel#Value { color: $TEXT; font-size: 12px; }
QLabel#Mono {
    font-family: "JetBrains Mono", "DejaVu Sans Mono", monospace;
    color: $MUTED;
    font-size: 10px;
}
QLabel#Countdown {
    font-family: "Cinzel", "Noto Serif", serif;
    font-size: 20px;
    color: $GOLD_HI;
}
QLabel#EmptyTitle {
    font-family: "Cinzel", "Noto Serif", serif;
    font-size: 16px;
    color: #8d826d;
}
QLabel#DetailTitle {
    font-family: "Cinzel", "Noto Serif", serif;
    font-size: 14px;
    color: $TEXT;
}

QLabel#Chip {
    border: 1px solid $BORDER_HI;
    border-radius: 10px;
    padding: 3px 9px;
    font-size: 9px;
    font-weight: 700;
    color: $MUTED;
    background: rgba(23, 20, 15, 160);
}
QLabel#Chip[tone="ok"] {
    color: #dcc391;
    border-color: #584729;
    background: #211b11;
}
QLabel#Chip[tone="warn"] {
    color: #e3a07c;
    border-color: #5e3726;
    background: #241611;
}
QLabel#Chip[tone="muted"] { color: $DIM; border-color: $BORDER; }

QPushButton {
    background: $CARD_HI;
    border: 1px solid $BORDER_HI;
    border-radius: 7px;
    color: $TEXT;
    padding: 8px 14px;
}
QPushButton:hover { background: #262015; border-color: #4a3d28; }
QPushButton:pressed { background: #201a11; }
QPushButton:disabled { color: $DIM; background: #14110d; border-color: #241f16; }

QPushButton#Boss {
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #e7c78b, stop:0.55 #cba55f, stop:1 #b58c48);
    color: #1c1407;
    border: 1px solid #ecd39c;
    font-family: "Cinzel", "Noto Serif", serif;
    font-size: 14px;
    font-weight: 700;
    padding: 14px 16px;
    border-radius: 9px;
}
QPushButton#Boss:hover {
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #f2d9a7, stop:0.55 #d9b673, stop:1 #c39a55);
}
QPushButton#Boss:pressed { background: #b68e4c; }
QPushButton#Boss:disabled { background: #2a2418; color: #6b6252; border-color: #3a3226; }

QPushButton#Ghost {
    background: transparent;
    border: 1px solid $BORDER;
    color: $MUTED;
    padding: 7px 12px;
    font-size: 11px;
}
QPushButton#Ghost:hover { color: $GOLD_HI; border-color: $GOLD_DIM; background: #1c1710; }

QPushButton#Restore {
    background: #1c1811;
    border: 1px solid $GOLD_DIM;
    color: $GOLD_HI;
    font-weight: 600;
    padding: 10px 14px;
}
QPushButton#Restore:hover { background: #262013; border-color: $GOLD; }
QPushButton#Restore:disabled {
    background: #14110d;
    border-color: $BORDER;
    color: $DIM;
}
QPushButton#Ghost:disabled {
    background: transparent;
    border-color: #241f16;
    color: #4f483b;
}
QPushButton#Danger:disabled {
    background: transparent;
    border-color: #241f16;
    color: #5a4a42;
}
QPushButton#Danger { color: #c98a76; background: transparent; border-color: $BORDER; }
QPushButton#Danger:hover { background: #231512; border-color: #5e3726; color: #e0a58e; }
QPushButton#DangerSolid {
    background: #3a1a14;
    border: 1px solid #7a3a28;
    color: #ecc0ad;
    font-weight: 600;
    padding: 9px 16px;
}
QPushButton#DangerSolid:hover { background: #4a2119; border-color: #a04a34; }
QPushButton#Link {
    background: transparent;
    border: none;
    color: $MUTED;
    padding: 2px;
    text-align: left;
}
QPushButton#Link:hover { color: $GOLD_HI; }

QTreeWidget#VaultTable {
    background: transparent;
    border: none;
    show-decoration-selected: 1;
    alternate-background-color: transparent;
}
QTreeWidget#VaultTable::item {
    border-bottom: 1px solid #201b13;
    color: $TEXT;
}
QTreeWidget#VaultTable::item:hover { background: #1b1710; }
QTreeWidget#VaultTable::item:selected { background: #2a2317; color: $TEXT; }
QHeaderView::section {
    background: transparent;
    color: $DIM;
    border: none;
    border-bottom: 1px solid $BORDER;
    padding: 7px 8px;
    font-size: 9px;
    font-weight: 700;
}
QTableCornerButton::section { background: transparent; border: none; }

QScrollBar:vertical {
    background: transparent;
    width: 10px;
    margin: 2px;
}
QScrollBar::handle:vertical {
    background: #3a3226;
    border-radius: 4px;
    min-height: 28px;
}
QScrollBar::handle:vertical:hover { background: #4d4130; }
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical { background: transparent; }

QSpinBox {
    background: #12100c;
    border: 1px solid $BORDER_HI;
    border-radius: 6px;
    padding: 5px 7px;
    color: $TEXT;
    min-width: 46px;
}
QSpinBox:focus { border-color: $GOLD_DIM; }
QSpinBox::up-button, QSpinBox::down-button {
    width: 15px;
    background: transparent;
    border: none;
}
QSpinBox::up-button:hover, QSpinBox::down-button:hover { background: #2a2317; }

QCheckBox { color: $MUTED; font-size: 11px; spacing: 8px; }
QCheckBox::indicator {
    width: 15px;
    height: 15px;
    border: 1px solid $BORDER_HI;
    border-radius: 4px;
    background: #12100c;
}
QCheckBox::indicator:hover { border-color: $GOLD_DIM; }
QCheckBox::indicator:checked {
    background: $GOLD;
    border-color: $GOLD;
    image: url($CHECK_ICON);
}

QToolTip {
    background: #221c13;
    color: $TEXT;
    border: 1px solid #4a3d28;
    padding: 6px 8px;
    font-size: 11px;
}

QMenu {
    background: #1b1710;
    border: 1px solid $BORDER_HI;
    padding: 6px;
}
QMenu::item { padding: 7px 22px 7px 14px; border-radius: 4px; }
QMenu::item:selected { background: #2a2317; color: $GOLD_HI; }
QMenu::separator { height: 1px; background: $BORDER; margin: 5px 8px; }

QDialog, QMessageBox, QInputDialog { background: $CARD; }
QMessageBox QLabel, QInputDialog QLabel { color: $TEXT; }
QDialogButtonBox QPushButton { min-width: 86px; }

QFrame#WarningBox {
    background: #1f140f;
    border: 1px solid #5e3726;
    border-radius: 8px;
}
QFrame#SafetyBox {
    background: #161a13;
    border: 1px solid #3c4a32;
    border-radius: 8px;
}
QFrame#Toast {
    background: #221c13;
    border: 1px solid #4a3d28;
    border-radius: 9px;
}
QFrame#Toast[tone="ok"] { border-color: #4d6140; }
QFrame#Toast[tone="warn"] { border-color: #6b3a27; }
""").substitute(PALETTE, CHECK_ICON=CHECK_ICON)


def load_fonts() -> list[str]:
    families: list[str] = []
    font_dir = asset_path("fonts")
    if not font_dir.is_dir():
        return families
    for path in sorted(font_dir.glob("*.ttf")):
        font_id = QFontDatabase.addApplicationFont(str(path))
        if font_id >= 0:
            families.extend(QFontDatabase.applicationFontFamilies(font_id))
    return sorted(set(families))


def apply_theme(app) -> None:
    load_fonts()
    app.setStyle("Fusion")

    palette = QPalette()
    palette.setColor(QPalette.Window, QColor(PALETTE["BG"]))
    palette.setColor(QPalette.WindowText, QColor(PALETTE["TEXT"]))
    palette.setColor(QPalette.Base, QColor("#12100c"))
    palette.setColor(QPalette.AlternateBase, QColor(PALETTE["CARD"]))
    palette.setColor(QPalette.Text, QColor(PALETTE["TEXT"]))
    palette.setColor(QPalette.Button, QColor(PALETTE["CARD_HI"]))
    palette.setColor(QPalette.ButtonText, QColor(PALETTE["TEXT"]))
    palette.setColor(QPalette.Highlight, QColor("#2a2317"))
    palette.setColor(QPalette.HighlightedText, QColor(PALETTE["TEXT"]))
    palette.setColor(QPalette.ToolTipBase, QColor("#221c13"))
    palette.setColor(QPalette.ToolTipText, QColor(PALETTE["TEXT"]))
    palette.setColor(QPalette.PlaceholderText, QColor(PALETTE["DIM"]))
    palette.setColor(QPalette.Disabled, QPalette.Text, QColor(PALETTE["DIM"]))
    palette.setColor(QPalette.Disabled, QPalette.ButtonText, QColor(PALETTE["DIM"]))
    app.setPalette(palette)
    app.setStyleSheet(_QSS)


def display_font(size: int, weight: QFont.Weight = QFont.Weight.DemiBold) -> QFont:
    font = QFont("Cinzel")
    font.setPointSize(size)
    font.setWeight(weight)
    font.setLetterSpacing(QFont.SpacingType.AbsoluteSpacing, 0.6)
    return font


def tracking_font(size: int, spacing: float = 1.4, bold: bool = True) -> QFont:
    font = QFont("Noto Sans")
    font.setPointSize(size)
    font.setLetterSpacing(QFont.SpacingType.AbsoluteSpacing, spacing)
    if bold:
        font.setWeight(QFont.Weight.Bold)
    return font
