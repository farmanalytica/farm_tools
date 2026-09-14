# -*- coding: utf-8 -*-
"""
The widget vocabulary every module page is built from.

Section panels, field labels, captions, dividers, the tab-button styles and the
calendar/slider/popup stylesheets are shared by the RAVI, SAR, Landsat, SYSI,
MapBiomas and Management Zones pages, so a control looks and behaves the same
whichever page it appears on.

These lived in ``radar.py`` and were imported from there by every other page;
they are neither private nor about radar.
"""

from qgis.core import QgsStyle
from qgis.PyQt.QtCore import QCoreApplication, QPoint, QRect, QSize, Qt
from qgis.PyQt.QtGui import QIcon, QLinearGradient, QPainter, QPixmap
from qgis.PyQt.QtWidgets import (
    QComboBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLayout,
    QSizePolicy,
    QWidget,
)


def _tr(text):
    return QCoreApplication.translate("RAVI", text)


def _ramp_icon(name: str, w: int = 48, h: int = 13) -> QIcon:
    ramp = QgsStyle.defaultStyle().colorRamp(name)
    pix = QPixmap(w, h)
    if ramp is None:
        pix.fill(Qt.GlobalColor.transparent)
        return QIcon(pix)
    gradient = QLinearGradient(0, 0, w, 0)
    for i in range(33):
        t = i / 32
        gradient.setColorAt(t, ramp.color(t))
    painter = QPainter(pix)
    painter.fillRect(0, 0, w, h, gradient)
    painter.end()
    return QIcon(pix)


class FlowLayout(QLayout):
    """Left-to-right layout that wraps items onto new lines when the available
    width runs out. Widening the window packs more controls per line, so fewer
    lines are needed and more options stay visible without scrolling."""

    def __init__(self, parent=None, margin=0, spacing=8):
        super().__init__(parent)
        if parent is not None:
            self.setContentsMargins(margin, margin, margin, margin)
        self.setSpacing(spacing)
        self._items = []

    def __del__(self):
        while self.count():
            self.takeAt(0)

    def addItem(self, item):
        self._items.append(item)

    def count(self):
        return len(self._items)

    def itemAt(self, index):
        if 0 <= index < len(self._items):
            return self._items[index]
        return None

    def takeAt(self, index):
        if 0 <= index < len(self._items):
            return self._items.pop(index)
        return None

    def expandingDirections(self):
        return Qt.Orientation(0)

    def hasHeightForWidth(self):
        return True

    def heightForWidth(self, width):
        return self._do_layout(QRect(0, 0, width, 0), True)

    def setGeometry(self, rect):
        super().setGeometry(rect)
        self._do_layout(rect, False)

    def sizeHint(self):
        return self.minimumSize()

    def minimumSize(self):
        size = QSize()
        for item in self._items:
            size = size.expandedTo(item.minimumSize())
        margins = self.contentsMargins()
        size += QSize(
            margins.left() + margins.right(), margins.top() + margins.bottom()
        )
        return size

    def _do_layout(self, rect, test_only):
        margins = self.contentsMargins()
        effective = rect.adjusted(
            margins.left(), margins.top(), -margins.right(), -margins.bottom()
        )
        x = effective.x()
        y = effective.y()
        line_height = 0
        spacing = self.spacing()
        for item in self._items:
            hint = item.sizeHint()
            next_x = x + hint.width() + spacing
            if next_x - spacing > effective.right() and line_height > 0:
                x = effective.x()
                y = y + line_height + spacing
                next_x = x + hint.width() + spacing
                line_height = 0
            if not test_only:
                item.setGeometry(QRect(QPoint(x, y), hint))
            x = next_x
            line_height = max(line_height, hint.height())
        return y + line_height - rect.y() + margins.bottom()


STYLE_TAB_ACTIVE = """
QPushButton {
    background-color: transparent;
    color: #1b6b39;
    border: none;
    border-bottom: 2px solid #1b6b39;
    font-size: 13px;
    font-weight: bold;
    padding: 0 4px 2px 4px;
    border-radius: 0;
}
"""


STYLE_TAB_INACTIVE = """
QPushButton {
    background-color: transparent;
    color: #9e9e9e;
    border: none;
    border-bottom: 2px solid transparent;
    font-size: 13px;
    font-weight: normal;
    padding: 0 4px 2px 4px;
    border-radius: 0;
}
QPushButton:hover {
    color: #616161;
    border-bottom-color: #d0d0d0;
}
"""


STYLE_POPUP_VIEW = (
    "background-color: #ffffff; color: #212121;"
    " selection-background-color: #e8f5e9; selection-color: #1a1a1a;"
)


STYLE_SLIDER = """
QSlider::groove:horizontal { height: 4px; background: #d6d6d6; border-radius: 2px; }
QSlider::sub-page:horizontal { background: #d6d6d6; border-radius: 2px; }
QSlider::add-page:horizontal { background: #d6d6d6; border-radius: 2px; }
QSlider::handle:horizontal {
    background: #1b6b39; width: 14px; height: 14px;
    margin: -6px 0; border-radius: 7px;
}
QSlider::handle:horizontal:hover { background: #15532d; }
"""


# The same slider, but with the travelled part of the track filled green —
# used where the value itself is the message (a threshold), not a position.
STYLE_SLIDER_FILLED = STYLE_SLIDER.replace(
    "QSlider::sub-page:horizontal { background: #d6d6d6;",
    "QSlider::sub-page:horizontal { background: #1b6b39;",
)

STYLE_CALENDAR = """
QCalendarWidget QWidget {
    background-color: #ffffff;
    color: #212121;
    alternate-background-color: #f5f5f5;
}
QCalendarWidget QAbstractItemView:enabled {
    background-color: #ffffff;
    color: #212121;
    selection-background-color: #1b6b39;
    selection-color: #ffffff;
}
QCalendarWidget QAbstractItemView:disabled {
    color: #bdbdbd;
}
QCalendarWidget QWidget#qt_calendar_navigationbar {
    background-color: #f8f9fa;
    border-bottom: 1px solid #e0e0e0;
    padding: 2px;
}
QCalendarWidget QToolButton {
    background-color: transparent;
    color: #212121;
    border: none;
    padding: 2px 6px;
    font-size: 12px;
    font-weight: bold;
}
QCalendarWidget QToolButton:hover {
    background-color: #e8f5e9;
    border-radius: 4px;
}
QCalendarWidget QSpinBox {
    background-color: #ffffff;
    color: #212121;
    border: 1px solid #d0d0d0;
    border-radius: 4px;
    padding: 2px 4px;
    font-size: 11px;
}
QCalendarWidget QMenu {
    background-color: #ffffff;
    color: #212121;
    border: 1px solid #e0e0e0;
}
"""


def add_ramp_items(combo: QComboBox, names) -> None:
    combo.setIconSize(QSize(48, 13))
    for name in names:
        combo.addItem(_ramp_icon(name), name)


def field_label(text):
    lbl = QLabel(text)
    lbl.setStyleSheet(
        "color: #8f9691; font-size: 10px; font-weight: bold; letter-spacing: 1px;"
        " background: transparent; border: none;"
    )
    return lbl


def prepare_field(widget, height=30):
    widget.setFixedHeight(height)
    widget.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
    return widget


def flow(widgets, spacing=8):
    """Wrap ``widgets`` in a container driven by a FlowLayout."""
    container = QWidget()
    container.setStyleSheet("background: transparent;")
    flow = FlowLayout(container, margin=0, spacing=spacing)
    for w in widgets:
        flow.addWidget(w)
    policy = container.sizePolicy()
    policy.setHeightForWidth(True)
    container.setSizePolicy(policy)
    return container


def labeled(text, widget, lbl_width=None):
    """Group a caption label with its control as a single flow item, so they
    never wrap apart from each other."""
    group = QWidget()
    group.setStyleSheet("background: transparent;")
    row = QHBoxLayout(group)
    row.setContentsMargins(0, 0, 0, 0)
    row.setSpacing(8)
    lbl = QLabel(text)
    lbl.setStyleSheet(
        "color: #616161; font-size: 12px; background: transparent; border: none;"
    )
    if lbl_width:
        lbl.setMinimumWidth(lbl_width)
    row.addWidget(lbl)
    row.addWidget(widget)
    return group


def caption(text):
    """Small uppercase group caption — a cheap, scannable visual anchor that
    keeps related controls readable as one cluster after the row wraps."""
    lbl = QLabel(text)
    lbl.setStyleSheet(
        "color: #9e9e9e; font-size: 11px; font-weight: bold; letter-spacing: 1px;"
        " background: transparent; border: none;"
    )
    return lbl


def make_divider():
    divider = QFrame()
    divider.setFrameShape(QFrame.Shape.HLine)
    divider.setStyleSheet("color: #edf0ee; background: transparent;")
    return divider


def section_panel():
    panel = QFrame()
    panel.setObjectName("sarSectionPanel")
    panel.setStyleSheet("""
        QFrame#sarSectionPanel {
            background-color: #fbfcfb;
            border: 1px solid #e4ebe6;
            border-radius: 8px;
        }
    """)
    return panel
