# -*- coding: utf-8 -*-
"""
Permanent navigation sidebar for the RAVI dialog.

The sidebar owns only presentation and navigation signals. Page switching stays
in ``farm_tools_dialog.py`` so the dialog can keep header and active state in sync.
"""

import os
import re

from qgis.PyQt.QtCore import (
    QCoreApplication,
    QEasingCurve,
    QRectF,
    Qt,
    QSize,
    QVariantAnimation,
    pyqtSignal,
)
from qgis.PyQt.QtCore import QPointF
from qgis.PyQt.QtGui import QColor, QFont, QIcon, QPainter, QPainterPath, QPen, QPixmap
from qgis.PyQt.QtWidgets import (
    QButtonGroup,
    QDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QTextBrowser,
    QVBoxLayout,
    QWidget,
)


def _tr(text):
    return QCoreApplication.translate("RAVI", text)


def _read_plugin_version() -> str:
    """Read ``version=`` from the plugin's metadata.txt; empty string if missing."""
    plugin_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    metadata_path = os.path.join(plugin_dir, "metadata.txt")
    try:
        with open(metadata_path, "r", encoding="utf-8") as handle:
            for line in handle:
                stripped = line.strip()
                if stripped.startswith("version="):
                    return stripped.split("=", 1)[1].strip()
    except OSError:
        pass
    return ""


def _read_plugin_changelog() -> str:
    """Read the ``changelog=`` block from the plugin's metadata.txt.

    Re-reads the file on every call so the dialog always reflects the current
    metadata.txt. Returns the de-indented changelog text, empty if missing.
    """
    plugin_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    metadata_path = os.path.join(plugin_dir, "metadata.txt")
    raw_lines = []
    try:
        with open(metadata_path, "r", encoding="utf-8") as handle:
            in_block = False
            for raw in handle:
                line = raw.rstrip("\n")
                if not in_block:
                    if line.strip().startswith("changelog="):
                        in_block = True
                        first = line.split("=", 1)[1].strip()
                        if first:
                            raw_lines.append(first)
                    continue
                # Continuation lines are indented; an unindented line ends the
                # block (next metadata key, comment, or section header).
                if line.strip() and not line[:1].isspace():
                    break
                raw_lines.append(line.strip())
    except OSError:
        return ""

    # Each version entry starts with "<n>.<n> - ..."; following indented lines
    # are soft-wrapped continuations of that same entry, so re-join them into
    # one paragraph per version.
    entries = []
    for line in raw_lines:
        if re.match(r"^\d+\.\d+\s*-", line):
            entries.append(line)
        elif line and entries:
            entries[-1] += " " + line
    return "\n".join(entries).strip()


SIDEBAR_COLLAPSED_WIDTH = 64
SIDEBAR_EXPANDED_WIDTH = 184
SIDEBAR_GREEN = "#1F6B3A"
SIDEBAR_GREEN_DARK = "#195A31"
SIDEBAR_INDICATOR = "#9FE0B4"
SIDEBAR_TEXT = "rgba(255, 255, 255, 218)"
SIDEBAR_MUTED = "rgba(255, 255, 255, 170)"


class SidebarNavButton(QPushButton):
    """Navigation button with a compact rounded active indicator."""

    def __init__(self, text="", parent=None):
        super().__init__(text, parent)
        self._indicator_color = QColor(SIDEBAR_INDICATOR)

    def paintEvent(self, event) -> None:
        super().paintEvent(event)
        if not self.isChecked():
            return

        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(self._indicator_color)
        height = 28 if self.width() > 80 else 22
        y = (self.height() - height) / 2
        painter.drawRoundedRect(QRectF(0, y, 3.5, height), 1.75, 1.75)
        painter.end()


class Sidebar(QFrame):
    """
    Permanent left navigation with two checkable page buttons.

    Signals:
        welcome_requested: emitted when the user clicks the FARM tools brand.
        auth_requested: emitted when the user clicks Auth.
        optical_requested: emitted when the user clicks Optical (Sentinel-2).
        sysi_requested: emitted when the user clicks SYSI.
        radar_requested: emitted when the user clicks Radar (SAR) data.
        dem_requested: emitted when the user clicks Download DEM.
        landsat_requested: emitted when the user clicks Landsat (Super-Res).
        fieldguide_requested: emitted when the user clicks Field Guide.
        climaplots_requested: emitted when the user clicks ClimaPlots.
        mapbiomas_requested: emitted when the user clicks MapBiomas.
    """

    welcome_requested = pyqtSignal()
    auth_requested = pyqtSignal()
    optical_requested = pyqtSignal()
    sysi_requested = pyqtSignal()
    radar_requested = pyqtSignal()
    dem_requested = pyqtSignal()
    landsat_requested = pyqtSignal()
    fieldguide_requested = pyqtSignal()
    climaplots_requested = pyqtSignal()
    mapbiomas_requested = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("Sidebar")
        self._active_page = "auth"
        self._expanded = False
        self.setFixedWidth(SIDEBAR_COLLAPSED_WIDTH)
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)

        self._width_animation = QVariantAnimation(self)
        self._width_animation.setDuration(160)
        easing = getattr(getattr(QEasingCurve, "Type", QEasingCurve), "OutCubic")
        self._width_animation.setEasingCurve(easing)
        self._width_animation.valueChanged.connect(self._set_animated_width)

        self._build()
        self._apply_expanded_state(False)
        self.set_active_page("auth")

    def _build(self) -> None:
        self._layout = QVBoxLayout(self)
        lay = self._layout
        lay.setContentsMargins(10, 18, 10, 18)
        lay.setSpacing(8)

        self.brand_block = QWidget()
        self.brand_block.setStyleSheet("background: transparent;")
        brand_block_lay = QVBoxLayout(self.brand_block)
        brand_block_lay.setContentsMargins(0, 0, 0, 0)
        brand_block_lay.setSpacing(0)

        # The brand is a real nav button (logo only): same group, selection
        # indicator and wiring as the other pages — it navigates to Welcome.
        self.btn_welcome = self._build_brand_panel()
        self.btn_welcome.clicked.connect(self.welcome_requested.emit)
        brand_block_lay.addWidget(self.btn_welcome, 0, Qt.AlignmentFlag.AlignHCenter)
        brand_block_lay.addSpacing(8)
        self.brand_divider = QFrame()
        self.brand_divider.setObjectName("sidebarBrandDivider")
        self.brand_divider.setFixedHeight(1)
        self.brand_divider.setStyleSheet("""
            QFrame#sidebarBrandDivider {
                background-color: rgba(255, 255, 255, 38);
                border: none;
            }
        """)
        brand_block_lay.addWidget(self.brand_divider, 0, Qt.AlignmentFlag.AlignHCenter)
        brand_block_lay.addSpacing(10)
        lay.addWidget(self.brand_block)

        # Nav buttons live in a scroll area so the rail never imposes a tall
        # minimum height on the dialog as more modules are added — it scrolls
        # instead. Brand stays pinned above, version below.
        self.nav_scroll = QScrollArea()
        self.nav_scroll.setObjectName("sidebarNavScroll")
        self.nav_scroll.setWidgetResizable(True)
        self.nav_scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.nav_scroll.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        )
        # Vertical scrollbar is shown only in expanded mode (see
        # _apply_expanded_state); collapsed rail stays clean and is still
        # wheel-scrollable.
        self.nav_scroll.setVerticalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        )
        self.nav_scroll.setSizePolicy(
            QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Expanding
        )
        self.nav_scroll.viewport().setStyleSheet("background: transparent;")

        nav_container = QWidget()
        nav_container.setObjectName("sidebarNavContainer")
        nav_lay = QVBoxLayout(nav_container)
        nav_lay.setContentsMargins(0, 0, 0, 0)
        nav_lay.setSpacing(8)

        self.btn_auth = self._make_button(_tr("Auth"), "auth")
        self.btn_auth.clicked.connect(self.auth_requested.emit)
        nav_lay.addWidget(self.btn_auth)

        self.btn_optical = self._make_button(_tr("Optical (Sentinel-2)"), "optical")
        self.btn_optical.clicked.connect(self.optical_requested.emit)
        nav_lay.addWidget(self.btn_optical)

        self.btn_sysi = self._make_button(_tr("SYSI"), "sysi")
        self.btn_sysi.clicked.connect(self.sysi_requested.emit)
        nav_lay.addWidget(self.btn_sysi)

        self.btn_radar = self._make_button(_tr("Radar (SAR) data"), "radar")
        self.btn_radar.clicked.connect(self.radar_requested.emit)
        nav_lay.addWidget(self.btn_radar)

        self.btn_download = self._make_button(_tr("EasyDEM"), "download")
        self.btn_download.clicked.connect(self.dem_requested.emit)
        nav_lay.addWidget(self.btn_download)

        self.btn_landsat = self._make_button(_tr("Landsat (Super-Res)"), "landsat")
        self.btn_landsat.clicked.connect(self.landsat_requested.emit)
        nav_lay.addWidget(self.btn_landsat)

        self.btn_fieldguide = self._make_button(_tr("Field Guide"), "fieldguide")
        self.btn_fieldguide.clicked.connect(self.fieldguide_requested.emit)
        nav_lay.addWidget(self.btn_fieldguide)

        self.btn_climaplots = self._make_button(_tr("ClimaPlots"), "climaplots")
        self.btn_climaplots.clicked.connect(self.climaplots_requested.emit)
        nav_lay.addWidget(self.btn_climaplots)

        self.btn_mapbiomas = self._make_button(_tr("MapBiomas"), "mapbiomas")
        self.btn_mapbiomas.clicked.connect(self.mapbiomas_requested.emit)
        nav_lay.addWidget(self.btn_mapbiomas)

        nav_lay.addStretch(1)
        self.nav_scroll.setWidget(nav_container)
        lay.addWidget(self.nav_scroll, 1)

        self._group = QButtonGroup(self)
        self._group.setExclusive(True)
        self._group.addButton(self.btn_welcome)
        self._group.addButton(self.btn_auth)
        self._group.addButton(self.btn_optical)
        self._group.addButton(self.btn_sysi)
        self._group.addButton(self.btn_radar)
        self._group.addButton(self.btn_download)
        self._group.addButton(self.btn_landsat)
        self._group.addButton(self.btn_fieldguide)
        self._group.addButton(self.btn_climaplots)
        self._group.addButton(self.btn_mapbiomas)

        self._version = _read_plugin_version()
        self.version_label = QLabel()
        self.version_label.setObjectName("sidebarVersion")
        self.version_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.version_label.setStyleSheet("""
            QLabel#sidebarVersion {
                background: transparent;
                color: rgba(255, 255, 255, 120);
                font-size: 10px;
                letter-spacing: 0.3px;
            }
        """)
        if self._version:
            self.version_label.setText("v{0}".format(self._version))
        lay.addWidget(self.version_label)

        # Discreet "What's new" link below the version: opens a dialog that
        # re-reads the changelog from metadata.txt on every click.
        self.whats_new_label = QLabel()
        self.whats_new_label.setObjectName("sidebarWhatsNew")
        self.whats_new_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.whats_new_label.setCursor(Qt.CursorShape.PointingHandCursor)
        self.whats_new_label.setText(
            '<a href="#whatsnew" style="color: rgba(255,255,255,150); '
            'text-decoration: none;">{0}</a>'.format(_tr("What's new"))
        )
        self.whats_new_label.setStyleSheet("""
            QLabel#sidebarWhatsNew {
                background: transparent;
                font-size: 10px;
                letter-spacing: 0.3px;
            }
        """)
        self.whats_new_label.linkActivated.connect(self._show_changelog)
        self.whats_new_label.setVisible(False)
        lay.addWidget(self.whats_new_label)

    def _build_brand_panel(self) -> QPushButton:
        """Brand as a logo-only nav button (no wordmark).

        Shares ``sidebarNavButton`` styling and ``SidebarNavButton``'s checked
        indicator, so it looks and behaves exactly like the other nav buttons.
        """
        btn = SidebarNavButton("")
        btn.setObjectName("sidebarNavButton")
        btn.setProperty("navText", "")
        btn.setCheckable(True)
        btn.setCursor(Qt.CursorShape.PointingHandCursor)
        btn.setFixedHeight(42)
        btn.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        btn.setToolTip(_tr("Welcome"))

        pix = self._load_brand_pixmap()
        if pix is not None:
            icon = QIcon()
            icon.addPixmap(pix, QIcon.Mode.Normal, QIcon.State.Off)
            icon.addPixmap(pix, QIcon.Mode.Normal, QIcon.State.On)
            icon.addPixmap(pix, QIcon.Mode.Active, QIcon.State.Off)
            btn.setIcon(icon)
            btn.setIconSize(QSize(30, 30))
        else:
            btn.setText("FARM")
        return btn

    def _make_button(self, text: str, icon_kind: str) -> QPushButton:
        btn = SidebarNavButton(text)
        btn.setObjectName("sidebarNavButton")
        btn.setProperty("navText", text)
        btn.setCheckable(True)
        btn.setCursor(Qt.CursorShape.PointingHandCursor)
        btn.setFixedHeight(42)
        btn.setIcon(self._make_icon(icon_kind))
        btn.setIconSize(QSize(20, 20))
        btn.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        btn.setToolTip(text)
        return btn

    def set_active_page(self, page: str) -> None:
        """Highlight the button matching ``page`` (``'auth'``, ``'optical'``, ``'sysi'``, ``'radar'``, ``'download'``, ``'landsat'`` or ``'fieldguide'``)."""
        self._active_page = page
        # An exclusive QButtonGroup ignores setChecked(False) on the currently
        # checked button, so it could never reach a no-selection state (needed
        # when the brand/Welcome page is active). Drop exclusivity while syncing,
        # then restore it.
        self._group.setExclusive(False)
        self.btn_welcome.setChecked(page == "welcome")
        self.btn_auth.setChecked(page == "auth")
        self.btn_optical.setChecked(page == "optical")
        self.btn_sysi.setChecked(page == "sysi")
        self.btn_radar.setChecked(page == "radar")
        self.btn_download.setChecked(page == "download")
        self.btn_landsat.setChecked(page == "landsat")
        self.btn_fieldguide.setChecked(page == "fieldguide")
        self.btn_climaplots.setChecked(page == "climaplots")
        self.btn_mapbiomas.setChecked(page == "mapbiomas")
        self._group.setExclusive(True)
        self._sync_brand_visibility()

    def _show_changelog(self) -> None:
        """Open a modal dialog with the changelog, re-read from metadata.txt."""
        changelog = _read_plugin_changelog()
        dlg = QDialog(self)
        dlg.setWindowTitle(_tr("What's new"))
        dlg.setMinimumSize(560, 420)
        dlg_lay = QVBoxLayout(dlg)
        dlg_lay.setContentsMargins(0, 0, 0, 0)
        dlg_lay.setSpacing(0)

        browser = QTextBrowser(dlg)
        browser.setOpenExternalLinks(True)
        if changelog:
            entries = []
            for entry in changelog.split("\n"):
                match = re.match(r"^(\d+\.\d+)\s*-\s*(.*)$", entry)
                if match:
                    entries.append(
                        "<p style='margin:0 0 14px 0;'>"
                        "<b style='color:#1F6B3A;'>v{0}</b> &mdash; {1}</p>".format(
                            match.group(1), match.group(2)
                        )
                    )
                else:
                    entries.append(
                        "<p style='margin:0 0 14px 0;'>{0}</p>".format(entry)
                    )
            browser.setHtml(
                "<div style='font-size:13px; line-height:1.45;'>{0}</div>".format(
                    "".join(entries)
                )
            )
        else:
            browser.setPlainText(_tr("No changelog available."))
        dlg_lay.addWidget(browser)

        dlg.exec()

    def enterEvent(self, event) -> None:
        """Expand the navigation rail while the pointer is over it."""
        self._apply_expanded_state(True)
        super().enterEvent(event)

    def leaveEvent(self, event) -> None:
        """Collapse back to an icon rail after the pointer leaves it."""
        self._apply_expanded_state(False)
        super().leaveEvent(event)

    def _apply_expanded_state(self, expanded: bool) -> None:
        self._expanded = expanded
        side_margin = 14 if expanded else 11
        self._layout.setContentsMargins(side_margin, 18, side_margin, 18)

        for btn in (self.btn_auth, self.btn_optical, self.btn_sysi, self.btn_radar, self.btn_download, self.btn_landsat, self.btn_fieldguide, self.btn_climaplots, self.btn_mapbiomas):
            btn.setText(btn.property("navText") if expanded else "")
            btn.setToolTip("" if expanded else btn.property("navText"))
            btn.setFixedWidth(156 if expanded else 42)

        self.btn_welcome.setFixedWidth(156 if expanded else 42)
        self.brand_block.setFixedWidth(156 if expanded else 42)
        self.brand_divider.setFixedWidth(156 if expanded else 28)

        # Scrollbar only while expanded; collapsed rail stays clean (wheel still
        # scrolls). Snap back to the top when collapsing so the icon rail always
        # starts at Auth.
        self.nav_scroll.setVerticalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAsNeeded if expanded
            else Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        )
        if not expanded:
            self.nav_scroll.verticalScrollBar().setValue(0)

        if self._version:
            self.version_label.setText(
                _tr("Version {0}").format(self._version) if expanded
                else "v{0}".format(self._version)
            )
        # The link only fits the expanded rail; collapsed shows version alone.
        self.whats_new_label.setVisible(expanded)
        self._sync_brand_visibility()

        self.setStyleSheet(self._stylesheet(expanded))
        self._animate_width(
            SIDEBAR_EXPANDED_WIDTH if expanded else SIDEBAR_COLLAPSED_WIDTH
        )

    def _sync_brand_visibility(self) -> None:
        self.brand_block.setVisible(True)

    def _animate_width(self, target_width: int) -> None:
        if self.width() == target_width:
            return
        self._width_animation.stop()
        self._width_animation.setStartValue(self.width())
        self._width_animation.setEndValue(target_width)
        self._width_animation.start()

    def _set_animated_width(self, width) -> None:
        self.setFixedWidth(int(width))

    def _stylesheet(self, expanded: bool) -> str:
        button_padding = "0 12px 0 10px" if expanded else "0"
        button_radius = "8px"
        button_text_align = "left" if expanded else "center"
        button_width = "156px" if expanded else "42px"
        return f"""
        QFrame#Sidebar {{
            background-color: qlineargradient(
                x1:0, y1:0, x2:0, y2:1,
                stop:0 {SIDEBAR_GREEN},
                stop:1 {SIDEBAR_GREEN_DARK}
            );
            border: none;
            border-right: 1px solid rgba(20, 76, 41, 180);
        }}
        QPushButton#sidebarNavButton {{
            background-color: transparent;
            color: {SIDEBAR_TEXT};
            border: none;
            border-radius: {button_radius};
            font-size: 12px;
            font-weight: bold;
            text-align: {button_text_align};
            padding: {button_padding};
            min-width: {button_width};
            max-width: {button_width};
            min-height: 42px;
            max-height: 42px;
        }}
        QPushButton#sidebarNavButton:hover {{
            background-color: rgba(255, 255, 255, 22);
            color: #ffffff;
        }}
        QPushButton#sidebarNavButton:checked {{
            background-color: transparent;
            color: #ffffff;
        }}
        QPushButton#sidebarNavButton:disabled {{
            color: {SIDEBAR_MUTED};
        }}
        QScrollArea#sidebarNavScroll, QWidget#sidebarNavContainer {{
            background: transparent;
            border: none;
        }}
        QScrollArea#sidebarNavScroll QScrollBar:vertical {{
            background: transparent;
            width: 5px;
            margin: 0;
        }}
        QScrollArea#sidebarNavScroll QScrollBar::handle:vertical {{
            background: rgba(255, 255, 255, 60);
            border-radius: 2px;
            min-height: 24px;
        }}
        QScrollArea#sidebarNavScroll QScrollBar::handle:vertical:hover {{
            background: rgba(255, 255, 255, 110);
        }}
        QScrollArea#sidebarNavScroll QScrollBar::add-line:vertical,
        QScrollArea#sidebarNavScroll QScrollBar::sub-line:vertical {{
            height: 0;
        }}
        QScrollArea#sidebarNavScroll QScrollBar::add-page:vertical,
        QScrollArea#sidebarNavScroll QScrollBar::sub-page:vertical {{
            background: transparent;
        }}
        """

    def _make_icon(self, kind: str) -> QIcon:
        """Create simple line icons so the sidebar avoids platform emoji styles."""
        icon = QIcon()
        if kind == "auth":
            key_pix = self._draw_key_emoji_icon()
            icon.addPixmap(key_pix, QIcon.Mode.Normal, QIcon.State.Off)
            icon.addPixmap(key_pix, QIcon.Mode.Normal, QIcon.State.On)
            icon.addPixmap(key_pix, QIcon.Mode.Active, QIcon.State.Off)
            return icon

        icon.addPixmap(
            self._draw_icon(kind, "#E9F4ED"), QIcon.Mode.Normal, QIcon.State.Off
        )
        icon.addPixmap(
            self._draw_icon(kind, "#FFFFFF"), QIcon.Mode.Normal, QIcon.State.On
        )
        icon.addPixmap(
            self._draw_icon(kind, "#FFFFFF"), QIcon.Mode.Active, QIcon.State.Off
        )
        return icon

    def _draw_key_emoji_icon(self) -> QPixmap:
        pix = QPixmap(20, 20)
        pix.fill(Qt.GlobalColor.transparent)

        painter = QPainter(pix)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        font = QFont("Segoe UI Emoji")
        font.setPixelSize(15)
        painter.setFont(font)
        painter.drawText(pix.rect(), Qt.AlignmentFlag.AlignCenter, "\U0001f511")
        painter.end()
        return pix

    def _load_brand_pixmap(self):
        plugin_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        icon_path = os.path.join(plugin_dir, "icon.png")
        if not os.path.exists(icon_path):
            return None

        raw = QPixmap(icon_path)
        if raw.isNull():
            return None

        # Show the full logo undistorted, scaled to fill the 40 px brand label.
        return raw.scaled(
            40,
            40,
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )

    def _draw_icon(self, kind: str, color: str) -> QPixmap:
        pix = QPixmap(20, 20)
        pix.fill(Qt.GlobalColor.transparent)

        painter = QPainter(pix)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        pen = QPen(QColor(color), 1.8)
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)

        if kind == "auth":
            painter.setPen(Qt.PenStyle.NoPen)
        elif kind == "optical":
            # Leaf with a midrib — evokes optical vegetation analysis.
            painter.setPen(pen)
            path = QPainterPath()
            path.moveTo(4, 16)
            path.cubicTo(5, 7, 11, 4, 16, 4)
            path.cubicTo(16, 11, 13, 16, 4, 16)
            painter.drawPath(path)
            painter.drawLine(6, 14, 15, 5)
        elif kind == "sysi":
            # Stacked soil strata with a sprout — evokes a bare-soil image.
            painter.setPen(pen)
            painter.drawLine(3, 11, 17, 11)
            painter.drawLine(3, 14, 17, 14)
            painter.drawLine(3, 17, 17, 17)
            painter.drawLine(10, 8, 10, 3)
            painter.drawLine(10, 6, 7, 4)
            painter.drawLine(10, 6, 13, 4)
        elif kind == "radar":
            painter.setPen(pen)
            painter.drawArc(QRectF(2, 2, 14, 14), 0 * 16, 90 * 16)
            painter.drawArc(QRectF(4, 4, 10, 10), 0 * 16, 90 * 16)
            painter.drawArc(QRectF(6, 6, 6, 6), 0 * 16, 90 * 16)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QColor(color))
            painter.drawEllipse(QPointF(9, 9), 1.4, 1.4)
        elif kind == "landsat":
            # Pixel grid sharpened by a magnifier — evokes super-resolution.
            painter.setPen(pen)
            painter.drawRect(QRectF(3, 3, 8, 8))
            painter.drawLine(7, 3, 7, 11)
            painter.drawLine(3, 7, 11, 7)
            painter.drawArc(QRectF(10, 10, 6, 6), 0, 360 * 16)
            painter.drawLine(15, 15, 18, 18)
        elif kind == "fieldguide":
            # Map pin with a center dot — evokes field point capture.
            painter.setPen(pen)
            painter.drawEllipse(QPointF(10, 8), 4.5, 4.5)
            painter.drawLine(QPointF(6.4, 11.0), QPointF(10, 17))
            painter.drawLine(QPointF(13.6, 11.0), QPointF(10, 17))
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QColor(color))
            painter.drawEllipse(QPointF(10, 8), 1.4, 1.4)
        elif kind == "climaplots":
            # Sun with rays + raindrop — evokes climate analysis.
            painter.setPen(pen)
            painter.drawEllipse(QPointF(7, 7), 3.0, 3.0)
            painter.drawLine(QPointF(7, 1.5), QPointF(7, 3.0))
            painter.drawLine(QPointF(1.5, 7), QPointF(3.0, 7))
            painter.drawLine(QPointF(3.1, 3.1), QPointF(4.2, 4.2))
            painter.drawLine(QPointF(10.9, 3.1), QPointF(9.8, 4.2))
            painter.drawLine(QPointF(3.1, 10.9), QPointF(4.2, 9.8))
            # Raindrop: rounded body with a peak at the top.
            drop = QPainterPath()
            drop.moveTo(13.5, 9.5)
            drop.cubicTo(11.0, 13.0, 11.0, 15.0, 13.5, 17.0)
            drop.cubicTo(16.0, 15.0, 16.0, 13.0, 13.5, 9.5)
            painter.drawPath(drop)
        elif kind == "mapbiomas":
            # Land-cover mosaic — a map tile split into patches, one filled.
            painter.setPen(pen)
            painter.drawRect(QRectF(3, 4, 14, 12))
            painter.drawLine(QPointF(9, 4), QPointF(9, 16))
            painter.drawLine(QPointF(3, 10), QPointF(17, 10))
            # A meandering boundary (river/field edge) across a patch.
            edge = QPainterPath()
            edge.moveTo(9, 7)
            edge.cubicTo(12, 7.5, 11, 9.5, 14, 10)
            painter.drawPath(edge)
            painter.fillRect(QRectF(3.6, 10.6, 4.8, 4.8), QColor(color))
        else:
            painter.setPen(pen)
            painter.drawLine(10, 3, 10, 12)
            painter.drawLine(6, 9, 10, 13)
            painter.drawLine(14, 9, 10, 13)
            painter.drawLine(5, 16, 15, 16)

        painter.end()
        return pix
