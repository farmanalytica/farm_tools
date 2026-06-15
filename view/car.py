# -*- coding: utf-8 -*-
"""
CAR analysis page for the FARM tools dialog.

Lets the user type a Brazilian CAR code (e.g.
``GO-5219258-CAE9B45810F4458584BAB4E860CF288E``) and fetch the property
geometry from the public CAR registry, saving it as KML to the configured
download folder and loading it as a layer.

Interactive widgets are exposed on ``dialog`` so ``farm_tools.py`` and
``car_ctrl.py`` can wire signals without importing this module.
"""

from qgis.PyQt.QtCore import Qt, QCoreApplication
from qgis.PyQt.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from .styles import STYLE_AOI_PAGE, STYLE_BTN_PRIMARY


def _tr(text):
    return QCoreApplication.translate("RAVI", text)


def setup_car_page(dialog, page):
    """Populate the CAR analysis page."""
    page.setObjectName("aoiPage")
    page.setStyleSheet(STYLE_AOI_PAGE)

    outer = QVBoxLayout(page)
    outer.setContentsMargins(6, 8, 6, 8)
    outer.setSpacing(0)

    panel = QFrame()
    panel.setObjectName("aoiPanel")
    panel_lay = QVBoxLayout(panel)
    panel_lay.setContentsMargins(16, 12, 16, 10)
    panel_lay.setSpacing(0)

    scroll_area = QScrollArea()
    scroll_area.setWidgetResizable(True)
    scroll_area.setFrameShape(QFrame.Shape.NoFrame)
    scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
    scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
    scroll_area.setStyleSheet("QScrollArea { background: #ffffff; border: none; }")

    scroll_content = QWidget()
    scroll_content.setObjectName("scrollContent")
    scroll_content.setStyleSheet("QWidget#scrollContent { background: #ffffff; }")
    scroll_lay = QVBoxLayout(scroll_content)
    scroll_lay.setContentsMargins(0, 0, 6, 0)
    scroll_lay.setSpacing(6)

    intro = QLabel(
        _tr(
            "<b>Análise CAR</b> fetches the registered property boundary for a "
            "Brazilian CAR code straight from the public rural-environmental "
            "registry. Paste the code, fetch it, and the boundary is saved as a "
            "KML in your download folder and loaded onto the map."
        )
    )
    intro.setObjectName("aoiIntro")
    intro.setWordWrap(True)
    intro.setTextFormat(Qt.TextFormat.RichText)
    intro.setStyleSheet(
        "QLabel#aoiIntro {"
        " color: #1b5e20; font-size: 11px; line-height: 1.4;"
        " background: #e8f5e9; border-left: 4px solid #1b6b39;"
        " border-radius: 4px; padding: 8px 10px; }"
    )
    scroll_lay.addWidget(intro)

    scroll_lay.addSpacing(8)

    title_lbl = QLabel(_tr("CAR code"))
    title_lbl.setObjectName("aoiTitle")
    scroll_lay.addWidget(title_lbl)

    subtitle_lbl = QLabel(
        _tr("Type or paste the property's CAR registration code.")
    )
    subtitle_lbl.setObjectName("aoiSubtitle")
    subtitle_lbl.setWordWrap(True)
    scroll_lay.addWidget(subtitle_lbl)

    scroll_lay.addSpacing(4)

    code_lbl = QLabel(_tr("CAR CODE"))
    code_lbl.setObjectName("aoiFieldLabel")
    scroll_lay.addWidget(code_lbl)

    code_row = QHBoxLayout()
    code_row.setContentsMargins(0, 0, 0, 0)
    code_row.setSpacing(6)

    dialog.car_input = QLineEdit()
    dialog.car_input.setObjectName("carInput")
    dialog.car_input.setPlaceholderText(
        "GO-5219258-CAE9B45810F4458584BAB4E860CF288E"
    )
    dialog.car_input.setClearButtonEnabled(True)
    dialog.car_input.setFixedHeight(28)
    code_row.addWidget(dialog.car_input, 1)

    dialog.btn_fetch_car = QPushButton(_tr("Fetch CAR"))
    dialog.btn_fetch_car.setFixedSize(120, 28)
    dialog.btn_fetch_car.setSizePolicy(
        QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed
    )
    dialog.btn_fetch_car.setStyleSheet(STYLE_BTN_PRIMARY)
    code_row.addWidget(dialog.btn_fetch_car)

    scroll_lay.addLayout(code_row)

    hint_lbl = QLabel(
        _tr(
            "The KML is saved to the download folder set on the Auth page; "
            "if none is set, it goes to a temporary folder."
        )
    )
    hint_lbl.setWordWrap(True)
    hint_lbl.setStyleSheet("color: #757575; font-size: 9px;")
    scroll_lay.addWidget(hint_lbl)

    scroll_lay.addStretch()

    scroll_area.setWidget(scroll_content)
    panel_lay.addWidget(scroll_area, 1)

    outer.addWidget(panel)
