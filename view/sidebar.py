# -*- coding: utf-8 -*-
"""
Permanent navigation sidebar for the RAVI dialog.

The sidebar owns only presentation and navigation signals. Page switching stays
in ``farm_tools_dialog.py`` so the dialog can keep header and active state in sync.
"""

import os

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
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSizePolicy,
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
        auth_requested: emitted when the user clicks Auth.
        optical_requested: emitted when the user clicks Optical (Sentinel-2).
        sysi_requested: emitted when the user clicks SYSI.
        radar_requested: emitted when the user clicks Radar (SAR) data.
        dem_requested: emitted when the user clicks Download DEM.
        landsat_requested: emitted when the user clicks Landsat (Super-Res).
        fieldguide_requested: emitted when the user clicks Field Guide.
        climaplots_requested: emitted when the user clicks ClimaPlots.
    """

    auth_requested = pyqtSignal()
    optical_requested = pyqtSignal()
    sysi_requested = pyqtSignal()
    radar_requested = pyqtSignal()
    dem_requested = pyqtSignal()
    landsat_requested = pyqtSignal()
    fieldguide_requested = pyqtSignal()
    climaplots_requested = pyqtSignal()

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

        self.brand_panel = self._build_brand_panel()
        brand_block_lay.addWidget(self.brand_panel, 0, Qt.AlignmentFlag.AlignHCenter)
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

        self.btn_auth = self._make_button(_tr("Auth"), "auth")
        self.btn_auth.clicked.connect(self.auth_requested.emit)
        lay.addWidget(self.btn_auth)

        self.btn_optical = self._make_button(_tr("Optical (Sentinel-2)"), "optical")
        self.btn_optical.clicked.connect(self.optical_requested.emit)
        lay.addWidget(self.btn_optical)

        self.btn_sysi = self._make_button(_tr("SYSI"), "sysi")
        self.btn_sysi.clicked.connect(self.sysi_requested.emit)
        lay.addWidget(self.btn_sysi)

        self.btn_radar = self._make_button(_tr("Radar (SAR) data"), "radar")
        self.btn_radar.clicked.connect(self.radar_requested.emit)
        lay.addWidget(self.btn_radar)

        self.btn_download = self._make_button(_tr("Download DEM"), "download")
        self.btn_download.clicked.connect(self.dem_requested.emit)
        lay.addWidget(self.btn_download)

        self.btn_landsat = self._make_button(_tr("Landsat (Super-Res)"), "landsat")
        self.btn_landsat.clicked.connect(self.landsat_requested.emit)
        lay.addWidget(self.btn_landsat)

        self.btn_fieldguide = self._make_button(_tr("Field Guide"), "fieldguide")
        self.btn_fieldguide.clicked.connect(self.fieldguide_requested.emit)
        lay.addWidget(self.btn_fieldguide)

        self.btn_climaplots = self._make_button(_tr("ClimaPlots"), "climaplots")
        self.btn_climaplots.clicked.connect(self.climaplots_requested.emit)
        lay.addWidget(self.btn_climaplots)

        self._group = QButtonGroup(self)
        self._group.setExclusive(True)
        self._group.addButton(self.btn_auth)
        self._group.addButton(self.btn_optical)
        self._group.addButton(self.btn_sysi)
        self._group.addButton(self.btn_radar)
        self._group.addButton(self.btn_download)
        self._group.addButton(self.btn_landsat)
        self._group.addButton(self.btn_fieldguide)
        self._group.addButton(self.btn_climaplots)

        lay.addStretch()

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
        lay.addWidget(self.version_label)

    def _build_brand_panel(self) -> QWidget:
        panel = QWidget()
        panel.setObjectName("sidebarBrand")
        panel.setFixedHeight(42)
        panel.setStyleSheet("background: transparent;")

        brand_lay = QHBoxLayout(panel)
        brand_lay.setContentsMargins(0, 0, 0, 0)
        brand_lay.setSpacing(8)

        self.brand_icon = QLabel()
        self.brand_icon.setObjectName("sidebarBrandIcon")
        self.brand_icon.setFixedSize(32, 32)
        self.brand_icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.brand_icon.setStyleSheet("""
            QLabel#sidebarBrandIcon {
                background-color: rgba(255, 255, 255, 24);
                border: 1px solid rgba(255, 255, 255, 42);
                border-radius: 16px;
            }
        """)
        pix = self._load_brand_pixmap()
        if pix is not None:
            self.brand_icon.setPixmap(pix)
        else:
            self.brand_icon.setText("E")
            self.brand_icon.setStyleSheet("""
                QLabel#sidebarBrandIcon {
                    background-color: rgba(255, 255, 255, 24);
                    border: 1px solid rgba(255, 255, 255, 42);
                    border-radius: 16px;
                    color: #ffffff;
                    font-size: 14px;
                    font-weight: bold;
                }
            """)
        brand_lay.addWidget(self.brand_icon)

        self.brand_text = QLabel("FARM tools")
        self.brand_text.setObjectName("sidebarBrandText")
        self.brand_text.setStyleSheet("""
            QLabel#sidebarBrandText {
                background: transparent;
                color: #ffffff;
                font-size: 13px;
                font-weight: bold;
                letter-spacing: 0.4px;
            }
        """)
        brand_lay.addWidget(self.brand_text)
        brand_lay.addStretch()
        return panel

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
        self.btn_auth.setChecked(page == "auth")
        self.btn_optical.setChecked(page == "optical")
        self.btn_sysi.setChecked(page == "sysi")
        self.btn_radar.setChecked(page == "radar")
        self.btn_download.setChecked(page == "download")
        self.btn_landsat.setChecked(page == "landsat")
        self.btn_fieldguide.setChecked(page == "fieldguide")
        self.btn_climaplots.setChecked(page == "climaplots")
        self._sync_brand_visibility()

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

        for btn in (self.btn_auth, self.btn_optical, self.btn_sysi, self.btn_radar, self.btn_download, self.btn_landsat, self.btn_fieldguide, self.btn_climaplots):
            btn.setText(btn.property("navText") if expanded else "")
            btn.setToolTip("" if expanded else btn.property("navText"))
            btn.setFixedWidth(156 if expanded else 42)

        self.brand_panel.setFixedWidth(156 if expanded else 32)
        self.brand_block.setFixedWidth(156 if expanded else 42)
        self.brand_text.setVisible(expanded)
        self.brand_divider.setFixedWidth(156 if expanded else 28)

        if self._version:
            self.version_label.setText(
                _tr("Version {0}").format(self._version) if expanded
                else "v{0}".format(self._version)
            )
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
        crop_top = int(raw.height() * 0.11)
        cropped = raw.copy(0, crop_top, raw.width(), raw.height() - crop_top)
        square = cropped.scaled(
            26,
            26,
            Qt.AspectRatioMode.IgnoreAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
        rounded = QPixmap(26, 26)
        rounded.fill(Qt.GlobalColor.transparent)

        painter = QPainter(rounded)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        path = QPainterPath()
        path.addEllipse(0, 0, 26, 26)
        painter.setClipPath(path)
        painter.drawPixmap(0, 0, square)
        painter.end()
        return rounded

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
        else:
            painter.setPen(pen)
            painter.drawLine(10, 3, 10, 12)
            painter.drawLine(6, 9, 10, 13)
            painter.drawLine(14, 9, 10, 13)
            painter.drawLine(5, 16, 15, 16)

        painter.end()
        return pix
