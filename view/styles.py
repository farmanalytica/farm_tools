# -*- coding: utf-8 -*-
"""
Shared UI styles for RAVI dialog views.

Stylesheet constants are defined here so individual page modules can reuse
the same visual language without duplicating long Qt stylesheet strings.
"""

STYLE_DIALOG = """
QDialog {
    background-color: #f5f5f5;
    color: #212121;
}
QWidget {
    color: #212121;
}
QToolTip {
    background-color: #ffffff;
    color: #212121;
    border: 1px solid #c8d8ce;
    padding: 4px 6px;
}
QLineEdit {
    background-color: #ffffff;
    color: #212121;
    border: 1px solid #e0e0e0;
    border-radius: 6px;
    padding: 6px 10px;
    font-size: 12px;
}
QLineEdit:focus {
    border-color: #1b6b39;
}
QScrollBar:vertical {
    background: #f5f5f5;
    width: 12px;
    margin: 0;
}
QScrollBar::handle:vertical {
    background: #bdbdbd;
    border-radius: 6px;
    min-height: 20px;
}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
    height: 0;
}
QScrollBar:horizontal {
    background: #f5f5f5;
    height: 12px;
    margin: 0;
}
QScrollBar::handle:horizontal {
    background: #bdbdbd;
    border-radius: 6px;
    min-width: 20px;
}
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {
    width: 0;
}
"""

STYLE_BTN_PRIMARY = """
QPushButton {
    background-color: #1b6b39;
    color: #ffffff;
    border: none;
    border-radius: 8px;
    font-size: 13px;
    font-weight: bold;
    padding: 0 16px;
}
QPushButton:hover  { background-color: #1e7d42; }
QPushButton:pressed { background-color: #155a2f; }
QPushButton:disabled {
    background-color: #bdbdbd;
    color: #f5f5f5;
}
"""

STYLE_BTN_SECONDARY = """
QPushButton {
    background-color: #ffffff;
    color: #1b6b39;
    border: 1px solid #c8d8ce;
    border-radius: 7px;
    font-size: 12px;
    font-weight: bold;
    padding: 0 12px;
}
QPushButton:hover {
    background-color: #e8f5e9;
    border-color: #8db99c;
}
QPushButton:pressed {
    background-color: #d7eadb;
    border-color: #1b6b39;
}
QPushButton:disabled {
    background-color: #eeeeee;
    color: #9e9e9e;
    border-color: #e0e0e0;
}
QToolTip {
    background-color: #ffffff;
    color: #212121;
    border: 1px solid #c8d8ce;
    padding: 4px 6px;
}
"""

STYLE_BTN_DRAW_ACTIVE = """
QPushButton {
    background-color: #e8833a;
    color: #ffffff;
    border: 1px solid #c96a26;
    border-radius: 7px;
    font-size: 11px;
    font-weight: bold;
    padding: 0 12px;
}
QPushButton:hover  { background-color: #f0954f; }
QPushButton:pressed { background-color: #d3742e; }
QToolTip {
    background-color: #ffffff;
    color: #212121;
    border: 1px solid #c8d8ce;
    padding: 4px 6px;
}
"""

STYLE_AOI_PAGE = """
QWidget#aoiPage {
    background-color: #f5f5f5;
}
QFrame#aoiPanel {
    background-color: #ffffff;
    border: 1px solid #e0e0e0;
    border-radius: 12px;
}
QLabel {
    background: transparent;
    border: none;
}
QLabel#aoiTitle {
    color: #1a1a1a;
    font-size: 17px;
    font-weight: bold;
}
QLabel#aoiSubtitle {
    color: #616161;
    font-size: 12px;
}
QLabel#aoiFieldLabel {
    color: #9e9e9e;
    font-size: 11px;
    font-weight: bold;
    letter-spacing: 1px;
}
QComboBox, QgsMapLayerComboBox {
    combobox-popup: 0;
    background-color: #ffffff;
    color: #212121;
    border: 1px solid #d0d0d0;
    border-radius: 6px;
    padding: 4px 8px;
    font-size: 13px;
}
QComboBox:focus, QgsMapLayerComboBox:focus {
    border: 1.5px solid #1b6b39;
}
QComboBox QAbstractItemView {
    background-color: #ffffff;
    color: #212121;
    border: 1px solid #bdbdbd;
    selection-background-color: #e8f5e9;
    selection-color: #1a1a1a;
    outline: 0;
}
QTextBrowser#demInfo {
    background-color: #fbfcfb;
    color: #212121;
    border: 1px solid #e0e0e0;
    border-radius: 8px;
    padding: 8px;
    font-size: 12px;
}
QTextBrowser#demInfo:focus {
    border-color: #1b6b39;
}
"""

STYLE_COMBO_YEAR = """
QComboBox {
    combobox-popup: 1;
    background-color: #ffffff;
    color: #212121;
    border: 1px solid #d0d0d0;
    border-radius: 6px;
    padding: 5px 10px;
    font-size: 13px;
    font-weight: bold;
}
QComboBox:hover { border-color: #8db99c; }
QComboBox:focus { border: 1.5px solid #1b6b39; }
QComboBox::drop-down {
    subcontrol-origin: padding;
    subcontrol-position: center right;
    width: 22px;
    border: none;
}
QComboBox QAbstractItemView {
    background-color: #ffffff;
    color: #212121;
    border: 1px solid #bdbdbd;
    border-radius: 6px;
    padding: 4px;
    selection-background-color: #e8f5e9;
    selection-color: #1a1a1a;
    outline: 0;
}
QComboBox QAbstractItemView::item {
    min-height: 26px;
    padding: 2px 8px;
}
"""

STYLE_CHECKBOX = """
QCheckBox {
    color: #212121;
    font-size: 12px;
    background: transparent;
    spacing: 8px;
}
QCheckBox::indicator {
    width: 15px;
    height: 15px;
}
QCheckBox::indicator:unchecked {
    background-color: #ffffff;
    border: 1.5px solid #9e9e9e;
    border-radius: 3px;
}
QCheckBox::indicator:unchecked:hover {
    border-color: #1b6b39;
}
"""

STYLE_BTN_HELP = """
QPushButton {
    background-color: transparent;
    color: #9e9e9e;
    border: 1.5px solid #d0d0d0;
    border-radius: 14px;
    font-size: 13px;
    font-weight: bold;
}
QPushButton:hover {
    background-color: #f5f5f5;
    color: #424242;
    border-color: #bdbdbd;
}
"""