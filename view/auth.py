# -*- coding: utf-8 -*-
"""
Authentication page for the RAVI dialog.

Builds the Google Earth Engine project configuration and authentication
controls. The project story and feature overview live on the separate
Welcome page (``view/welcome.py``). Signal connections are wired externally
by ``farm_tools.py``.
"""

from qgis.PyQt.QtCore import Qt, QCoreApplication
from qgis.PyQt.QtWidgets import (
    QButtonGroup,
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
from qgis.gui import QgsPasswordLineEdit

from .styles import STYLE_BTN_PRIMARY, STYLE_BTN_SECONDARY


def _tr(text):
    return QCoreApplication.translate("RAVI", text)


def setup_auth_page(dialog, page):
    """
    Populate the authentication page.

    A single centred column holds the sign-in card (``project_id_input``,
    ``btn_authenticate``, ``btn_reset_auth``, the personal/service-account
    mode toggle and key picker), a status line, the GEE prerequisites info
    box, and the download-folder picker. All interactive widgets are exposed
    on ``dialog`` so ``farm_tools.py`` can wire signal connections without
    importing this module's internals.
    """
    page.setStyleSheet("background-color: #f5f5f5;")

    # Single column, scrolling independently and centred horizontally.
    page_lay = QHBoxLayout(page)
    page_lay.setContentsMargins(16, 16, 16, 16)
    page_lay.setSpacing(0)

    right_scroll = QScrollArea()
    right_scroll.setWidgetResizable(True)
    right_scroll.setFrameShape(QFrame.Shape.NoFrame)
    right_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
    # Fill the available height and scroll internally so word-wrapped content
    # never drives the whole dialog taller when the window is narrowed.
    right_scroll.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
    right_scroll.setMinimumHeight(0)
    right_scroll.setStyleSheet("QScrollArea { background: transparent; border: none; }")
    page_lay.addWidget(right_scroll, 1)

    right = QWidget()
    right.setStyleSheet("background: transparent;")
    # Keep the card a comfortable reading width; the page centres it.
    right.setMaximumWidth(460)
    right_scroll.setWidget(right)
    right_scroll.setAlignment(Qt.AlignmentFlag.AlignHCenter)
    right_lay = QVBoxLayout(right)
    right_lay.setContentsMargins(0, 0, 0, 0)
    right_lay.setSpacing(12)

    auth_heading = QLabel(_tr("GEE Authentication"))
    auth_heading.setStyleSheet(
        "color: #1a1a1a; font-size: 16px; font-weight: bold;"
    )
    right_lay.addWidget(auth_heading)

    card = QFrame()
    # Height tracks content: the service-account key row appears/disappears as
    # the user switches sign-in mode, so a fixed height would clip or pad it.
    card.setMinimumHeight(250)
    # Accent border keeps the sign-in card the visual focus of the page.
    card.setStyleSheet("""
        QFrame {
            background-color: #ffffff;
            border: 2px solid #1b6b39;
            border-radius: 12px;
        }
        QLabel { background: transparent; border: none; }
    """)
    card_lay = QVBoxLayout(card)
    card_lay.setContentsMargins(20, 18, 20, 14)
    card_lay.setSpacing(7)

    # Sign-in mode toggle: personal OAuth vs. a service-account key file.
    mode_row = QFrame()
    mode_row.setStyleSheet(
        """
        QFrame { background: #f0f0f0; border: none; border-radius: 6px; }
        QPushButton {
            background: transparent;
            color: #616161;
            border: none;
            border-radius: 5px;
            font-size: 11px;
            font-weight: bold;
            padding: 5px 0;
        }
        QPushButton:checked {
            background: #1b6b39;
            color: #ffffff;
        }
        """
    )
    mode_lay = QHBoxLayout(mode_row)
    mode_lay.setContentsMargins(3, 3, 3, 3)
    mode_lay.setSpacing(3)

    dialog.btn_mode_personal = QPushButton(_tr("Personal"))
    dialog.btn_mode_service = QPushButton(_tr("Service account"))
    dialog.auth_mode_group = QButtonGroup(dialog)
    dialog.auth_mode_group.setExclusive(True)
    for btn in (dialog.btn_mode_personal, dialog.btn_mode_service):
        btn.setCheckable(True)
        btn.setCursor(Qt.CursorShape.PointingHandCursor)
        btn.setFixedHeight(26)
        dialog.auth_mode_group.addButton(btn)
        mode_lay.addWidget(btn, 1)
    dialog.btn_mode_personal.setChecked(True)
    card_lay.addWidget(mode_row)
    card_lay.addSpacing(2)

    dialog.auth_status_badge = QPushButton(_tr("Checking sign-in status…"))
    dialog.auth_status_badge.setCursor(Qt.CursorShape.PointingHandCursor)
    dialog.auth_status_badge.setToolTip(
        _tr("Click to re-check your Earth Engine sign-in status")
    )
    dialog.auth_status_badge.setFixedHeight(22)
    dialog.auth_status_badge.setStyleSheet(
        """
        QPushButton {
            background-color: transparent;
            color: #757575;
            border: none;
            font-size: 11px;
            font-weight: bold;
            padding: 0 10px;
            text-align: center;
        }
        """
    )
    card_lay.addWidget(dialog.auth_status_badge)
    card_lay.addSpacing(4)

    # Service-account key picker. Hidden in personal mode; shown via
    # dialog.set_auth_mode("service").
    dialog.sa_key_row = QWidget()
    dialog.sa_key_row.setStyleSheet("background: transparent;")
    sa_lay = QVBoxLayout(dialog.sa_key_row)
    sa_lay.setContentsMargins(0, 0, 0, 0)
    sa_lay.setSpacing(4)

    sa_lbl = QLabel(_tr("SERVICE-ACCOUNT KEY (.json)"))
    sa_lbl.setStyleSheet(
        "color: #9e9e9e; font-size: 11px; letter-spacing: 1px; font-weight: bold;"
    )
    sa_lay.addWidget(sa_lbl)

    sa_input_row = QHBoxLayout()
    sa_input_row.setContentsMargins(0, 0, 0, 0)
    sa_input_row.setSpacing(8)

    dialog.sa_key_input = QLineEdit()
    dialog.sa_key_input.setReadOnly(True)
    dialog.sa_key_input.setPlaceholderText(_tr("No key file selected"))
    dialog.sa_key_input.setFixedHeight(28)
    dialog.sa_key_input.setStyleSheet("""
        QLineEdit {
            background-color: #f5f5f5;
            color: #424242;
            border: 1px solid #e0e0e0;
            border-radius: 4px;
            padding: 2px 8px;
            font-size: 12px;
        }
    """)
    sa_input_row.addWidget(dialog.sa_key_input, 1)

    dialog.btn_browse_key = QPushButton(_tr("Browse"))
    dialog.btn_browse_key.setFixedHeight(28)
    dialog.btn_browse_key.setStyleSheet(STYLE_BTN_SECONDARY)
    sa_input_row.addWidget(dialog.btn_browse_key)

    sa_lay.addLayout(sa_input_row)
    card_lay.addWidget(dialog.sa_key_row)
    card_lay.addSpacing(10)
    dialog.sa_key_row.hide()

    pid_lbl = QLabel(_tr("PROJECT ID (GOOGLE CLOUD)"))
    pid_lbl.setStyleSheet(
        "color: #9e9e9e; font-size: 11px; letter-spacing: 1px; font-weight: bold;"
    )
    card_lay.addWidget(pid_lbl)
    card_lay.addSpacing(18)

    dialog.project_id_input = QgsPasswordLineEdit()
    dialog.project_id_input.setEchoMode(QLineEdit.EchoMode.Normal)
    dialog.project_id_input.setPlaceholderText(_tr("e.g. my-geospatial-project-42"))
    dialog.project_id_input.setFixedHeight(28)
    dialog.project_id_input.setStyleSheet("""
        QLineEdit {
            background-color: transparent;
            color: #212121;
            border: none;
            border-bottom: 1.5px solid #d0d0d0;
            border-radius: 0;
            padding: 2px 0 6px 0;
            font-size: 14px;
        }
        QLineEdit:focus {
            border-bottom: 2px solid #1b6b39;
        }
    """)
    card_lay.addWidget(dialog.project_id_input)

    card_lay.addSpacing(3)

    dialog.btn_authenticate = QPushButton(_tr("🔑   Validate ID"))
    dialog.btn_authenticate.setFixedHeight(34)
    dialog.btn_authenticate.setStyleSheet(STYLE_BTN_PRIMARY)
    card_lay.addWidget(dialog.btn_authenticate)

    card_lay.addSpacing(2)

    dialog.btn_reset_auth = QPushButton(_tr("Reset authentication"))
    dialog.btn_reset_auth.setFixedHeight(20)
    dialog.btn_reset_auth.setStyleSheet("""
        QPushButton {
            background-color: transparent;
            color: #bdbdbd;
            border: none;
            font-size: 10px;
        }
        QPushButton:hover { color: #c62828; }
    """)
    card_lay.addWidget(dialog.btn_reset_auth, 0, Qt.AlignmentFlag.AlignHCenter)

    right_lay.addWidget(card)

    dialog.auth_status_lbl = QLabel("")
    dialog.auth_status_lbl.setWordWrap(True)
    dialog.auth_status_lbl.setTextFormat(Qt.TextFormat.RichText)
    dialog.auth_status_lbl.setOpenExternalLinks(True)
    dialog.auth_status_lbl.setAlignment(Qt.AlignmentFlag.AlignHCenter)
    dialog.auth_status_lbl.setStyleSheet("color: #616161; font-size: 11px;")
    dialog.auth_status_lbl.hide()
    right_lay.addWidget(dialog.auth_status_lbl)

    info_frame = QFrame()
    info_frame.setStyleSheet("""
        QFrame {
            background-color: #e8f5e9;
            border-left: 3px solid #43a047;
            border-radius: 4px;
        }
        QLabel { background: transparent; border: none; }
    """)
    info_lay = QHBoxLayout(info_frame)
    info_lay.setContentsMargins(12, 10, 12, 10)
    info_lay.setSpacing(8)

    info_icon = QLabel("ⓘ")
    info_icon.setFixedWidth(18)
    info_icon.setAlignment(Qt.AlignmentFlag.AlignTop)
    info_icon.setStyleSheet("color: #2e7d32; font-size: 14px; font-weight: bold;")
    info_lay.addWidget(info_icon)

    info_text = QLabel(
        _tr(
            "Requires an active GEE account and a Google Cloud Console project "
            "with the API enabled."
        )
    )
    info_text.setWordWrap(True)
    info_text.setStyleSheet("color: #1b5e20; font-size: 12px;")
    info_lay.addWidget(info_text, 1)

    right_lay.addWidget(info_frame)

    dialog.btn_go_to_aoi = QPushButton(page)
    dialog.btn_go_to_aoi.hide()
    dialog.btn_go_to_aoi.clicked.connect(dialog.show_dem_page)

    folder_frame = QFrame()
    folder_frame.setStyleSheet("""
        QFrame {
            background-color: #ffffff;
            border: 1px solid #e0e0e0;
            border-radius: 8px;
        }
        QLabel { background: transparent; border: none; }
    """)
    folder_lay = QVBoxLayout(folder_frame)
    folder_lay.setContentsMargins(14, 10, 14, 10)
    folder_lay.setSpacing(8)

    folder_lbl = QLabel(_tr("Download folder"))
    folder_lbl.setStyleSheet("color: #616161; font-size: 11px; font-weight: bold;")
    folder_lay.addWidget(folder_lbl)

    folder_input_row = QHBoxLayout()
    folder_input_row.setContentsMargins(0, 0, 0, 0)
    folder_input_row.setSpacing(8)

    dialog.folder_input = QLineEdit()
    dialog.folder_input.setReadOnly(True)
    dialog.folder_input.setPlaceholderText(_tr("System temp (default)"))
    dialog.folder_input.setFixedHeight(28)
    dialog.folder_input.setStyleSheet("""
        QLineEdit {
            background-color: #f5f5f5;
            color: #424242;
            border: 1px solid #e0e0e0;
            border-radius: 4px;
            padding: 2px 8px;
            font-size: 12px;
        }
    """)
    folder_input_row.addWidget(dialog.folder_input, 1)

    dialog.btn_clear_folder = QPushButton("✕")
    dialog.btn_clear_folder.setFixedSize(28, 28)
    dialog.btn_clear_folder.setToolTip(_tr("Clear download folder"))
    dialog.btn_clear_folder.setStyleSheet("""
        QPushButton {
            background-color: transparent;
            color: #bdbdbd;
            border: none;
            border-radius: 4px;
            font-size: 13px;
        }
        QPushButton:hover:enabled {
            color: #c62828;
            background-color: #fdecea;
        }
        QPushButton:disabled { color: #eeeeee; }
    """)
    folder_input_row.addWidget(dialog.btn_clear_folder)

    dialog.btn_browse_folder = QPushButton(_tr("Browse"))
    dialog.btn_browse_folder.setFixedHeight(28)
    dialog.btn_browse_folder.setStyleSheet(STYLE_BTN_SECONDARY)
    folder_input_row.addWidget(dialog.btn_browse_folder)

    folder_lay.addLayout(folder_input_row)

    def _sync_clear_enabled(text):
        dialog.btn_clear_folder.setEnabled(bool(text))

    dialog.folder_input.textChanged.connect(_sync_clear_enabled)
    _sync_clear_enabled(dialog.folder_input.text())

    right_lay.addWidget(folder_frame)
    right_lay.addStretch(1)
