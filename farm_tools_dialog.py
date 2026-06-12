# -*- coding: utf-8 -*-
"""
UI layer for the FARM tools QGIS plugin.

Defines ``FarmToolsDialog``, a three-page modal dialog that guides the user
through the full plugin workflow:

1. **Authentication page** — user supplies a Google Cloud
   project ID and validates GEE access, chooses a download
   folder or browses datasets without
   authenticating.
2. **SAR page** - user selects (or draw) a polygon layer as the Area
   of Interest, picks the start and end date, the polarization, the output format,
   the spectral index and other processing options. Generate or preview a SAR time series
   and a synthetic image
3. **DEM page** — user selects a polygon layer as the Area
   of Interest, picks a DEM dataset, sets an AOI buffer and triggers the download.

This module owns the dialog shell only. Keep this module free of business logic
and the ``ee`` SDK.
"""

import os

from qgis.PyQt.QtCore import Qt, QUrl, QCoreApplication, QEvent
from qgis.PyQt.QtGui import QDesktopServices, QPixmap
from qgis.PyQt.QtWidgets import (
    QApplication,
    QDialog,
    QDialogButtonBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QSizePolicy,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from .managers.settings_manager import SettingsManager

from .view.auth import setup_auth_page
from .view.climaplots import setup_climaplots_page
from .view.download_dem import setup_download_dem_page
from .view.fieldguide import setup_fieldguide_page
from .view.landsat import setup_landsat_page
from .view.optical import setup_optical_page
from .view.radar import setup_radar_page
from .view.sysi import setup_sysi_page
from .view.sidebar import Sidebar
from .view.styles import STYLE_DIALOG, STYLE_BTN_HELP


def _tr(text):
    return QCoreApplication.translate("RAVI", text)


class FarmToolsDialog(QDialog):
    """
    Main dialog window for the FARM tools plugin.

    Auth page:
        project_id_input: GCP project ID field.
        btn_authenticate: Triggers GEE authentication.
        btn_reset_auth: Clears existing GEE credentials.
        btn_go_to_aoi: Navigates to the AOI page without authenticating.

    AOI page:
        layer_combo: Polygon layer selector.
        dem_combo: Lists DEM datasets available for the AOI.
        dem_info: Displays metadata for the selected dataset.
        buffer_slider: AOI buffer control (−300 m … +300 m).
        buffer_value_lbl: Live label showing the current buffer value.
        folder_input: Download destination path field.
        btn_browse_folder: Opens the folder picker dialog.
        btn_hybrid_layer: Adds a Google Hybrid basemap layer.
        btn_download_dem: Downloads and loads the DEM into QGIS.

    Signal connections are wired externally by ``farm_tools.py``.
    """

    _DEFAULT_SIZE = (800, 534)

    def __init__(self, parent=None):
        self._qgis_parent = parent
        # Do not pass ``parent`` to QDialog: a Qt-child top-level window has no
        # taskbar button on Windows, so minimizing collapses it to a tiny stub in
        # the screen corner instead of going to the taskbar. Stacking above QGIS is
        # restored via a transient parent in ``showEvent``, and the missing taskbar
        # button (a side effect of the owner relationship) is forced back with the
        # WS_EX_APPWINDOW extended style. Result: floats above QGIS *and* minimizes
        # to the taskbar like a normal window.
        super().__init__(None)
        self._win_configured = False
        self._setup_ui()

    def showEvent(self, event):
        super().showEvent(event)
        if self._win_configured:
            return
        self._win_configured = True
        self._configure_native_window()

    def changeEvent(self, event):
        super().changeEvent(event)
        # Restore from maximized should snap back to the default size, not the
        # window's pre-maximize geometry that Qt would otherwise reapply.
        if event.type() == QEvent.Type.WindowStateChange:
            was_maximized = bool(event.oldState() & Qt.WindowState.WindowMaximized)
            if was_maximized and not self.isMaximized() and not self.isMinimized():
                self.resize(*self._DEFAULT_SIZE)

    def _configure_native_window(self):
        """Float above QGIS (transient parent) while keeping a taskbar button."""
        handle = self.windowHandle()
        if handle is not None and self._qgis_parent is not None:
            parent_handle = self._qgis_parent.windowHandle()
            if parent_handle is not None:
                handle.setTransientParent(parent_handle)

        if os.name != "nt":
            return
        try:
            import ctypes

            GWL_EXSTYLE = -20
            WS_EX_APPWINDOW = 0x00040000
            WS_EX_TOOLWINDOW = 0x00000080
            user32 = ctypes.windll.user32
            hwnd = int(self.winId())
            style = user32.GetWindowLongW(hwnd, GWL_EXSTYLE)
            new_style = (style | WS_EX_APPWINDOW) & ~WS_EX_TOOLWINDOW
            if new_style != style:
                user32.SetWindowLongW(hwnd, GWL_EXSTYLE, new_style)
                # Re-show so the taskbar registers the button. Guarded by
                # ``_win_configured`` above, so this does not recurse.
                self.hide()
                self.show()
        except Exception:
            pass

    def _setup_ui(self):
        """Build the main_layout layout: fixed header, central stack, fixed footer."""
        self.setWindowTitle("FARM tools")
        self.setWindowFlags(
            Qt.WindowType.Window
            | Qt.WindowType.WindowSystemMenuHint
            | Qt.WindowType.WindowTitleHint
            | Qt.WindowType.WindowMinimizeButtonHint
            | Qt.WindowType.WindowMaximizeButtonHint
            | Qt.WindowType.WindowCloseButtonHint
        )
        self.setWindowModality(Qt.WindowModality.NonModal)

        self.resize(*self._DEFAULT_SIZE)
        self.setSizeGripEnabled(True)
        self.setStyleSheet(STYLE_DIALOG)

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        main_layout.addWidget(self._build_header())

        body_container = QWidget()
        body_container.setStyleSheet("background-color: #f5f5f5;")
        body_layout = QHBoxLayout(body_container)
        body_layout.setContentsMargins(0, 0, 0, 0)
        body_layout.setSpacing(2)

        self.sidebar = Sidebar()
        self.sidebar.auth_requested.connect(self._nav_to_auth)
        self.sidebar.optical_requested.connect(self._nav_to_optical)
        self.sidebar.sysi_requested.connect(self._nav_to_sysi)
        self.sidebar.radar_requested.connect(self._nav_to_radar)
        self.sidebar.dem_requested.connect(self._nav_to_dem)
        self.sidebar.landsat_requested.connect(self._nav_to_landsat)
        self.sidebar.fieldguide_requested.connect(self._nav_to_fieldguide)
        self.sidebar.climaplots_requested.connect(self._nav_to_climaplots)
        body_layout.addWidget(self.sidebar)

        content_container = QWidget()
        content_container.setStyleSheet("background-color: #f5f5f5;")
        content_layout = QVBoxLayout(content_container)
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(0)

        self.stack = QStackedWidget()
        self.stack.setFrameShape(QFrame.Shape.NoFrame)
        self.stack.setLineWidth(0)
        self.stack.setStyleSheet("background-color: #f5f5f5;")
        content_layout.addWidget(self.stack, 1)

        self.footer = self._build_footer()
        content_layout.addWidget(self.footer)

        body_layout.addWidget(content_container, 1)

        self.loading_page = self._build_loading_page()
        self.auth_page = QWidget()
        self.optical_page = QWidget()
        self.sysi_page = QWidget()
        self.radar_page = QWidget()
        self.dem_page = QWidget()
        self.landsat_page = QWidget()
        self.fieldguide_page = QWidget()
        self.climaplots_page = QWidget()

        setup_auth_page(self, self.auth_page)
        setup_optical_page(self, self.optical_page)
        setup_sysi_page(self, self.sysi_page)
        setup_radar_page(self, self.radar_page)
        setup_download_dem_page(self, self.dem_page)
        setup_landsat_page(self, self.landsat_page)
        setup_fieldguide_page(self, self.fieldguide_page)
        setup_climaplots_page(self, self.climaplots_page)

        self.stack.addWidget(self.loading_page)
        self.stack.addWidget(self.auth_page)
        self.stack.addWidget(self.optical_page)
        self.stack.addWidget(self.sysi_page)
        self.stack.addWidget(self.radar_page)
        self.stack.addWidget(self.dem_page)
        self.stack.addWidget(self.landsat_page)
        self.stack.addWidget(self.fieldguide_page)
        self.stack.addWidget(self.climaplots_page)
        self.stack.currentChanged.connect(self._sync_page_state)

        self.stack.setCurrentWidget(self.auth_page)
        self._sync_page_state(self.stack.currentIndex())

        main_layout.addWidget(body_container, 1)


    def _build_loading_page(self):
        loading_page = QWidget()
        loading_layout = QVBoxLayout(loading_page)
        loading_layout.setContentsMargins(48, 0, 48, 24)
        loading_layout.setSpacing(12)
        loading_layout.addStretch()

        title = QLabel(_tr("Setting up FARM tools…"))
        title.setStyleSheet("color: #1b6b39; font-size: 14px; font-weight: bold;")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        loading_layout.addWidget(title)

        subtitle = QLabel(
            _tr("Downloading dependencies. This only happens on first use.")
        )
        subtitle.setStyleSheet("color: #616161; font-size: 10px;")
        subtitle.setAlignment(Qt.AlignmentFlag.AlignCenter)
        loading_layout.addWidget(subtitle)

        progress_bar = QProgressBar()
        progress_bar.setRange(0, 0)
        progress_bar.setFixedHeight(6)
        progress_bar.setTextVisible(False)
        progress_bar.setStyleSheet(
            "QProgressBar { border: none; border-radius: 3px; background: #e0e0e0; }"
            "QProgressBar::chunk { background: #1b6b39; border-radius: 3px; }"
        )
        loading_layout.addWidget(progress_bar)
        self._loading_bar = progress_bar

        loading_layout.addStretch()
        return loading_page


    def _build_header(self):
        """
        Build and return the dialog header widget.

        The header is a fixed-height white bar containing:
        - The "FARM tools" brand label (green).
        - A vertical separator.
        - A dynamic page-title label updated by the
          controller when the active page changes.
        - A "?" help button that opens the documentation URL in the browser.
        """
        header = QWidget()
        header.setFixedHeight(38)
        header.setStyleSheet("background-color: #ffffff;")

        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(28, 0, 20, 0)
        header_layout.setSpacing(0)

        brand = QLabel("FARM tools")
        brand.setStyleSheet(
            "color: #1b6b39; font-size: 13px; font-weight: bold; letter-spacing: 0.5px;"
        )
        header_layout.addWidget(brand)

        separator = QLabel("  |")
        separator.setStyleSheet("color: #d0d0d0; font-size: 16px;")
        header_layout.addWidget(separator)

        self._header_title = QLabel(_tr("GEE Configuration"))
        self._header_title.setStyleSheet(
            "color: #616161; font-size: 13px; margin-left: 4px;"
        )
        header_layout.addWidget(self._header_title)

        header_layout.addStretch()

        # Proxy settings, tucked into the top-right corner as a subtle link
        # (mirrors the ClimaPlots placement). Only needed on restricted networks.
        self.proxy_btn = QPushButton(_tr("Proxy settings"))
        self.proxy_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.proxy_btn.setToolTip(
            _tr("Proxy setting (only if required by your network provider)")
        )
        self.proxy_btn.setStyleSheet("""
            QPushButton {
                background-color: transparent;
                color: #9e9e9e;
                border: none;
                font-size: 11px;
                padding: 0 10px;
            }
            QPushButton:hover { color: #1b6b39; }
        """)
        self.proxy_btn.clicked.connect(self._open_proxy_dialog)
        header_layout.addWidget(self.proxy_btn)

        self.browser = QPushButton("?")
        self.browser.setFixedSize(28, 28)
        self.browser.setToolTip(_tr("Learn more"))
        self.browser.setStyleSheet(STYLE_BTN_HELP)
        self.browser.clicked.connect(
            lambda: QDesktopServices.openUrl(
                QUrl("https://www.raviqgis.org")
            )
        )
        header_layout.addWidget(self.browser)

        return header

    def _open_proxy_dialog(self):
        """Small modal to view/edit the optional outbound HTTP(S) proxy."""
        dialog = QDialog(self)
        dialog.setWindowTitle(_tr("Proxy Settings"))
        layout = QVBoxLayout(dialog)
        layout.addWidget(
            QLabel(_tr("Enter proxy (e.g. http://[username]:[password]@host:port):"))
        )
        proxy_edit = QLineEdit()
        proxy_edit.setText(SettingsManager.get_proxy())
        proxy_edit.setMinimumWidth(320)
        layout.addWidget(proxy_edit)
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        layout.addWidget(buttons)

        def _accept():
            SettingsManager.set_proxy(proxy_edit.text().strip())
            dialog.accept()

        buttons.accepted.connect(_accept)
        buttons.rejected.connect(dialog.reject)
        dialog.exec()


    def _build_footer(self):
        """
        Build and return the dialog footer widget.

        The footer is a fixed-height white bar containing the FARM
        Analytica logo and a short attribution text with a clickable
        link to the FARM Analytica website
        """
        footer = QWidget()
        # Fixed (not minimum) height: a word-wrapped label below has
        # heightForWidth, and as persistent chrome in the top-level layout it
        # would otherwise grow the whole dialog taller when the window narrows
        # (or its DPI changes while being dragged between monitors).
        footer.setFixedHeight(36)
        footer.setStyleSheet(
            "background-color: transparent;"
            "QLabel { border: none; background: transparent; }"
        )

        footer_layout = QHBoxLayout(footer)
        footer_layout.setContentsMargins(28, 4, 28, 4)
        footer_layout.setSpacing(8)

        farm_icon = QLabel()
        farm_icon.setFixedHeight(16)
        farm_icon.setStyleSheet("background: transparent;")
        logo_path = os.path.join(
            os.path.dirname(os.path.abspath(__file__)),
            "assets",
            "farm_analytica_logo.svg",
        )
        if os.path.exists(logo_path):
            pix = QPixmap(logo_path).scaledToHeight(
                16, Qt.TransformationMode.SmoothTransformation
            )
            farm_icon.setPixmap(pix)
            farm_icon.setFixedWidth(pix.width())
        else:
            farm_icon.setText("FARM ANALYTICA")
            farm_icon.setStyleSheet(
                "color: #1b6b39; font-size: 9px; font-weight: bold;"
            )
        farm_icon.setAlignment(
            Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft
        )
        footer_layout.addWidget(farm_icon)

        farm_text = QLabel()
        farm_text.setTextFormat(Qt.TextFormat.RichText)
        farm_text.setOpenExternalLinks(True)
        # No word wrap: wrapping reintroduces a width-dependent height that
        # destabilises the fixed-height footer (see setFixedHeight above).
        farm_text.setWordWrap(False)
        farm_text.setText(
            _tr("This is a free and open project, supported by ")
            + '<a href="https://farmanalytica.com.br" style="color:#1b6b39;'
            'text-decoration:none;font-weight:bold;">FARM Analytica</a>. '
            + _tr("Get in touch for exclusive and personalized commercial solutions.")
        )
        farm_text.setStyleSheet("color: #9e9e9e; font-size: 9px;")
        farm_text.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred
        )
        footer_layout.addWidget(farm_text)

        return footer


    def show_loading_page(self):
        """Switch the stacked widget to the loading/download page."""
        self.stack.setCurrentWidget(self.loading_page)

    def show_dem_page(self):
        """Switch the stacked widget to the AOI selection page."""
        self.stack.setCurrentWidget(self.dem_page)

    def show_auth_page(self):
        """Switch the stacked widget to the authentication page."""
        self.stack.setCurrentWidget(self.auth_page)

    def show_optical_page(self):
        """Switch the stacked widget to the Optical (Sentinel-2) page."""
        self.stack.setCurrentWidget(self.optical_page)

    def show_sysi_page(self):
        """Switch the stacked widget to the SYSI page."""
        self.stack.setCurrentWidget(self.sysi_page)

    def show_radar_page(self):
        """Switch the stacked widget to the Radar (SAR) page."""
        self.stack.setCurrentWidget(self.radar_page)

    def show_landsat_page(self):
        """Switch the stacked widget to the Landsat Super-Resolution page."""
        self.stack.setCurrentWidget(self.landsat_page)

    def show_fieldguide_page(self):
        """Switch the stacked widget to the Field Guide page."""
        self.stack.setCurrentWidget(self.fieldguide_page)

    def show_climaplots_page(self):
        """Switch the stacked widget to the ClimaPlots page."""
        self.stack.setCurrentWidget(self.climaplots_page)

    def _nav_to_auth(self):
        """Sidebar auth button — always navigates to the auth page."""
        self.show_auth_page()

    def _nav_to_optical(self):
        """Sidebar optical button — always navigates to the Optical page."""
        self.show_optical_page()

    def _nav_to_sysi(self):
        """Sidebar SYSI button — always navigates to the SYSI page."""
        self.show_sysi_page()

    def _nav_to_radar(self):
        """Sidebar radar button — always navigates to the radar page."""
        self.show_radar_page()

    def _nav_to_dem(self):
        """Sidebar download button follows the existing dataset-loading path."""
        if hasattr(self, "btn_go_to_aoi"):
            self.btn_go_to_aoi.click()
            return
        self.show_dem_page()

    def _nav_to_landsat(self):
        """Sidebar Landsat button — always navigates to the Landsat page."""
        self.show_landsat_page()

    def _nav_to_fieldguide(self):
        """Sidebar Field Guide button — always navigates to the Field Guide page."""
        self.show_fieldguide_page()

    def _nav_to_climaplots(self):
        """Sidebar ClimaPlots button — always navigates to the ClimaPlots page."""
        self.show_climaplots_page()

    def _sync_page_state(self, index):
        """Keep header and sidebar state aligned with the current stack page."""
        current = self.stack.widget(index)

        # Proxy settings matter on the auth page (network setup) and on the
        # ClimaPlots page (its data fetchers honor the same proxy).
        self.proxy_btn.setVisible(current in (self.auth_page, self.climaplots_page))

        if current is self.loading_page:
            self._header_title.setText(_tr("Setting up…"))
            self.sidebar.set_active_page(None)
            self.footer.setVisible(True)
            return

        if current is self.auth_page:
            self._header_title.setText(_tr("GEE Configuration"))
            self.sidebar.set_active_page("auth")
            self.footer.setVisible(True)
            return

        if current is self.optical_page:
            self._header_title.setText(_tr("Optical Imagery (Sentinel-2)"))
            self.sidebar.set_active_page("optical")
            self.footer.setVisible(False)
            return

        if current is self.sysi_page:
            self._header_title.setText(_tr("Synthetic Soil Image (SYSI)"))
            self.sidebar.set_active_page("sysi")
            self.footer.setVisible(False)
            return

        if current is self.radar_page:
            self._header_title.setText(_tr("Radar (SAR) Data"))
            self.sidebar.set_active_page("radar")
            self.footer.setVisible(False)
            return

        if current is self.dem_page:
            self._header_title.setText(_tr("Inputs & Parameters"))
            self.sidebar.set_active_page("download")
            self.footer.setVisible(False)
            return

        if current is self.landsat_page:
            self._header_title.setText(_tr("Landsat Super-Resolution"))
            self.sidebar.set_active_page("landsat")
            self.footer.setVisible(False)
            return

        if current is self.fieldguide_page:
            self._header_title.setText(_tr("Field Guide"))
            self.sidebar.set_active_page("fieldguide")
            self.footer.setVisible(False)
            return

        if current is self.climaplots_page:
            self._header_title.setText(_tr("ClimaPlots"))
            self.sidebar.set_active_page("climaplots")
            self.footer.setVisible(False)


    def set_auth_busy(self, busy):
        """
        Toggle the auth page between idle and in-progress states.

        While busy the project-ID field and the reset/browse buttons are
        disabled, and the primary button becomes a Cancel control.
        """
        self._auth_busy = busy
        self.project_id_input.setEnabled(not busy)
        self.btn_reset_auth.setEnabled(not busy)
        self.btn_browse_folder.setEnabled(not busy)
        self.auth_status_badge.setEnabled(not busy)
        self.btn_mode_personal.setEnabled(not busy)
        self.btn_mode_service.setEnabled(not busy)
        self.btn_browse_key.setEnabled(not busy)

        if busy:
            self.btn_authenticate.setText(_tr("Cancel"))
            self.set_auth_status(_tr("Starting authentication…"))
        else:
            if getattr(self, "_auth_state", "").startswith("authenticated"):
                self.btn_authenticate.setText(_tr("Continue"))
            else:
                self.btn_authenticate.setText(_tr("🔑   Validate ID"))
            self.auth_status_lbl.hide()
            self.auth_status_lbl.clear()

    _AUTH_STATE_STYLES = {
        "checking": ("Checking sign-in status…", "#757575", "#f0f0f0", "#e0e0e0"),
        "none": ("Not signed in", "#b71c1c", "#fdecea", "#f5c6c2"),
        "stored": (
            "Credentials found — validate to finish",
            "#8a5300",
            "#fff4e0",
            "#f0d9a8",
        ),
        "authenticated": ("Signed in & ready", "#1b5e20", "#e8f5e9", "#a5d6a7"),
        "authenticated_sa": (
            "Signed in via service account",
            "#1b5e20",
            "#e8f5e9",
            "#a5d6a7",
        ),
    }

    def set_auth_mode(self, mode):
        """Switch the sign-in card between personal OAuth and service-account.

        Shows/hides the key-file picker and keeps the segmented toggle in sync.
        The Project ID field is shared by both modes.
        """
        is_service = mode == "service"
        self._auth_mode = "service" if is_service else "personal"
        self.sa_key_row.setVisible(is_service)
        target = self.btn_mode_service if is_service else self.btn_mode_personal
        if not target.isChecked():
            target.setChecked(True)

    def set_auth_state(self, state):
        """
        Update the auth-page status pill.

        ``state`` is one of ``"checking"``, ``"none"``, ``"stored"``,
        ``"authenticated"``, or ``"authenticated_sa"``; unknown values fall
        back to ``"stored"``.
        """
        text, fg, bg, border = self._AUTH_STATE_STYLES.get(
            state, self._AUTH_STATE_STYLES["stored"]
        )
        self._auth_state = state

        if not getattr(self, "_auth_busy", False):
            if state.startswith("authenticated"):
                self.btn_authenticate.setText(_tr("Continue"))
            elif state != "checking":
                self.btn_authenticate.setText(_tr("🔑   Validate ID"))

        self.auth_status_badge.setText(_tr(text).replace("&", "&&"))
        self.auth_status_badge.setStyleSheet(
            """
            QPushButton {
                background-color: transparent;
                color: %s;
                border: none;
                font-size: 11px;
                font-weight: bold;
                padding: 0 10px;
                text-align: center;
            }
            """
            % (fg,)
        )

    def set_auth_status(self, text, url=""):
        """Show a non-blocking status line; if ``url`` is given, append a
        link that reopens the browser sign-in page."""
        if url:
            text += '<br><a href="%s" style="color:#1b6b39;">%s</a>' % (
                url,
                _tr("Reopen the sign-in page"),
            )
        self.auth_status_lbl.setText(text)
        self.auth_status_lbl.show()

    def pop_message(self, message, kind):
        """
        Display a modal message box to the user.
        """
        QApplication.restoreOverrideCursor()

        config = {
            "info": (_tr("Information"), QMessageBox.Icon.Information),
            "warning": (_tr("Warning"), QMessageBox.Icon.Warning),
        }
        title, icon = config.get(kind, config["info"])

        msg = QMessageBox(self)
        msg.setWindowTitle(title)
        msg.setIcon(icon)
        msg.setText(message)
        msg.setStandardButtons(QMessageBox.StandardButton.Ok)
        msg.button(QMessageBox.StandardButton.Ok).setText("OK")
        msg.setStyleSheet("font-size: 10pt;")
        msg.exec()
