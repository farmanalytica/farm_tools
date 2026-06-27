# -*- coding: utf-8 -*-
"""
AOI and DEM download page for the RAVI dialog.

Builds the second workflow page: polygon AOI selection, DEM dataset selection,
dataset metadata display, AOI buffer control, download folder picker, and
action buttons.  Signal connections are wired externally by ``farm_tools.py`` and
``dem_ctrl.py``.
"""

from qgis.PyQt.QtCore import Qt, QTimer, QCoreApplication
from qgis.PyQt.QtWidgets import (
    QComboBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QListView,
    QPushButton,
    QScrollArea,
    QSlider,
    QSizePolicy,
    QTextBrowser,
    QVBoxLayout,
    QWidget,
)
from qgis.core import QgsMapLayerProxyModel
from qgis.gui import QgsMapLayerComboBox

from .styles import (
    STYLE_AOI_PAGE,
    STYLE_BTN_PRIMARY,
    STYLE_BTN_SECONDARY,
    make_logo_label,
)


def _tr(text):
    return QCoreApplication.translate("RAVI", text)


_SLIDER_STYLE = """
QSlider::groove:horizontal { height: 4px; background: #d6d6d6; border-radius: 2px; }
QSlider::sub-page:horizontal { background: #d6d6d6; border-radius: 2px; }
QSlider::add-page:horizontal { background: #d6d6d6; border-radius: 2px; }
QSlider::handle:horizontal {
    background: #1b6b39; width: 14px; height: 14px;
    margin: -6px 0; border-radius: 7px;
}
QSlider::handle:horizontal:hover { background: #15532d; }
"""


class LimitedPopupComboBox(QComboBox):
    """ComboBox with a bounded popup height for long catalogs."""

    def __init__(self, parent=None, popup_height=170):
        super().__init__(parent)
        self._popup_height = popup_height

    def showPopup(self):
        """Show the popup and schedule its size adjustment after Qt creates it."""
        view = self.view()
        view.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        super().showPopup()
        QTimer.singleShot(0, self._resize_popup)

    def _resize_popup(self):
        """Resize the popup to fit inside the dialog without overflowing."""
        view = self.view()
        popup = view.window()

        row_height = max(view.sizeHintForRow(0), self.fontMetrics().height() + 4)
        visible_rows = min(self.maxVisibleItems(), self.count())
        popup_height = min(
            self._popup_height,
            max(row_height * visible_rows + 2, row_height + 2),
        )
        popup_width = self.width()

        top_left = self.mapToGlobal(self.rect().bottomLeft())
        parent_window = self.window()
        if parent_window:
            bottom_limit = (
                parent_window.mapToGlobal(parent_window.rect().bottomLeft()).y() - 8
            )
            available_below = bottom_limit - top_left.y()
            if row_height * 4 <= available_below < popup_height:
                popup_height = available_below

        popup.setFixedSize(popup_width, popup_height)
        popup.move(top_left)
        view.setGeometry(0, 0, popup_width, popup_height)


def setup_download_dem_page(dialog, page):
    """
    Populate the AOI and DEM download page.

    The white panel is split into two areas:

    - **Scrollable area** (top, expands): title, AOI layer selector, DEM
      dataset selector, metadata browser, and AOI buffer control.
    - **Fixed footer** (always visible): download folder picker and action
      buttons.

    All interactive widgets are exposed on ``dialog`` so ``farm_tools.py`` and
    ``dem_ctrl.py`` can wire signal connections without importing this
    module directly.
    """
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

    scroll_lay.addWidget(make_logo_label("easydem.svg", height=48))
    scroll_lay.addSpacing(4)

    intro = QLabel(
        _tr(
            "<b>EasyDEM</b> downloads ready-to-use terrain elevation models for "
            "your area of interest. Pick a polygon layer (or draw one), choose a "
            "DEM dataset such as SRTM or Copernicus, fine-tune the area with the "
            "buffer, and save a clipped GeoTIFF straight to your map."
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

    title_lbl = QLabel(_tr("AOI and DEM inputs"))
    title_lbl.setObjectName("aoiTitle")
    scroll_lay.addWidget(title_lbl)

    subtitle_lbl = QLabel(_tr("Select the polygon layer and elevation dataset."))
    subtitle_lbl.setObjectName("aoiSubtitle")
    subtitle_lbl.setWordWrap(True)
    scroll_lay.addWidget(subtitle_lbl)

    scroll_lay.addSpacing(4)

    layer_lbl = QLabel(_tr("AOI LAYER"))
    layer_lbl.setObjectName("aoiFieldLabel")
    scroll_lay.addWidget(layer_lbl)

    aoi_row = QWidget()
    aoi_row_lay = QHBoxLayout(aoi_row)
    aoi_row_lay.setContentsMargins(0, 0, 0, 0)
    aoi_row_lay.setSpacing(6)

    dialog.layer_combo = QgsMapLayerComboBox()
    dialog.layer_combo.setObjectName("layerCombo")
    dialog.layer_combo.setFilters(QgsMapLayerProxyModel.PolygonLayer)
    dialog.layer_combo.setAllowEmptyLayer(True)
    dialog.layer_combo.setFixedHeight(28)
    aoi_row_lay.addWidget(dialog.layer_combo, 1)

    dialog.btn_draw_aoi = QPushButton(_tr("Draw AOI"))
    dialog.btn_draw_aoi.setToolTip(
        _tr("Drag on the map to draw a box (Shift = square, Esc = cancel)")
    )
    dialog.btn_draw_aoi.setFixedHeight(28)
    dialog.btn_draw_aoi.setSizePolicy(
        QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed
    )
    dialog.btn_draw_aoi.setStyleSheet(STYLE_BTN_SECONDARY)
    aoi_row_lay.addWidget(dialog.btn_draw_aoi)

    dialog.btn_hybrid_layer = QPushButton(_tr("Add Google Hybrid Layer"))
    dialog.btn_hybrid_layer.setFixedHeight(28)
    dialog.btn_hybrid_layer.setSizePolicy(
        QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed
    )
    dialog.btn_hybrid_layer.setStyleSheet(STYLE_BTN_SECONDARY)
    aoi_row_lay.addWidget(dialog.btn_hybrid_layer)

    scroll_lay.addWidget(aoi_row)

    scroll_lay.addSpacing(6)

    dem_lbl = QLabel(_tr("DEM DATASET"))
    dem_lbl.setObjectName("aoiFieldLabel")
    scroll_lay.addWidget(dem_lbl)

    dialog.dem_combo = LimitedPopupComboBox(popup_height=170)
    dialog.dem_combo.setObjectName("demCombo")
    dialog.dem_combo.setFixedHeight(28)
    dialog.dem_combo.setMaxVisibleItems(10)
    dialog.dem_combo.setMinimumContentsLength(28)
    dialog.dem_combo.setSizeAdjustPolicy(
        QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon
    )
    dem_combo_view = QListView(dialog.dem_combo)
    dem_combo_view.setUniformItemSizes(True)
    dem_combo_view.setVerticalScrollMode(QListView.ScrollMode.ScrollPerItem)
    dem_combo_view.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
    dialog.dem_combo.setView(dem_combo_view)
    scroll_lay.addWidget(dialog.dem_combo)

    scroll_lay.addSpacing(2)

    dialog.dem_info = QTextBrowser()
    dialog.dem_info.setObjectName("demInfo")
    dialog.dem_info.setOpenExternalLinks(True)
    dialog.dem_info.setMinimumHeight(80)
    dialog.dem_info.setMaximumHeight(110)
    dialog.dem_info.setSizePolicy(
        QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred
    )
    scroll_lay.addWidget(dialog.dem_info)

    scroll_lay.addSpacing(6)

    separator = QFrame()
    separator.setFrameShape(QFrame.Shape.HLine)
    separator.setStyleSheet("color: #e0e0e0;")
    scroll_lay.addWidget(separator)

    scroll_lay.addSpacing(4)

    buffer_lbl = QLabel(_tr("AOI BUFFER"))
    buffer_lbl.setObjectName("aoiFieldLabel")
    scroll_lay.addWidget(buffer_lbl)

    buffer_desc = QLabel(
        _tr(
            "Use a positive buffer to include terrain just outside your area, or a negative buffer to crop the edges."
        )
    )
    buffer_desc.setWordWrap(True)
    buffer_desc.setStyleSheet("color: #757575; font-size: 9px;")
    scroll_lay.addWidget(buffer_desc)

    scroll_lay.addSpacing(4)

    buffer_row = QHBoxLayout()
    buffer_row.setContentsMargins(0, 0, 0, 0)
    buffer_row.setSpacing(8)

    minus_lbl = QLabel("−300 m")
    minus_lbl.setStyleSheet("color: #9e9e9e; font-size: 9px;")
    buffer_row.addWidget(minus_lbl)

    dialog.buffer_slider = QSlider(Qt.Orientation.Horizontal)
    dialog.buffer_slider.setMinimum(-300)
    dialog.buffer_slider.setMaximum(300)
    dialog.buffer_slider.setSingleStep(1)
    dialog.buffer_slider.setPageStep(10)
    dialog.buffer_slider.setValue(0)
    dialog.buffer_slider.setTickInterval(100)
    dialog.buffer_slider.setTickPosition(QSlider.TickPosition.NoTicks)
    dialog.buffer_slider.setStyleSheet(_SLIDER_STYLE)
    buffer_row.addWidget(dialog.buffer_slider, 1)

    plus_lbl = QLabel("+300 m")
    plus_lbl.setStyleSheet("color: #9e9e9e; font-size: 9px;")
    buffer_row.addWidget(plus_lbl)

    scroll_lay.addLayout(buffer_row)

    dialog.buffer_value_lbl = QLabel(_tr("Buffer: 0 m"))
    dialog.buffer_value_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
    dialog.buffer_value_lbl.setStyleSheet("color: #616161; font-size: 10px;")
    scroll_lay.addWidget(dialog.buffer_value_lbl)

    def _set_buffer_value(value):
        value = 0 if -3 <= value <= 3 else value
        if dialog.buffer_slider.value() != value:
            dialog.buffer_slider.blockSignals(True)
            dialog.buffer_slider.setValue(value)
            dialog.buffer_slider.blockSignals(False)
        dialog.buffer_value_lbl.setText(
            _tr("Buffer: %+d m") % value if value != 0 else _tr("Buffer: 0 m")
        )

    dialog.buffer_slider.valueChanged.connect(_set_buffer_value)

    scroll_lay.addStretch()

    # Action row scrolls with the rest of the content (no fixed footer).
    footer_separator = QFrame()
    footer_separator.setFrameShape(QFrame.Shape.HLine)
    footer_separator.setStyleSheet("color: #e8e8e8;")
    scroll_lay.addWidget(footer_separator)

    scroll_lay.addSpacing(6)

    action_row = QHBoxLayout()
    action_row.setContentsMargins(0, 0, 0, 0)
    action_row.setSpacing(8)

    action_row.addStretch(1)

    dialog.btn_download_dem = QPushButton(_tr("Download DEM"))
    dialog.btn_download_dem.setFixedSize(160, 32)
    dialog.btn_download_dem.setStyleSheet(STYLE_BTN_PRIMARY)
    action_row.addWidget(dialog.btn_download_dem)

    action_row.addStretch(1)

    scroll_lay.addLayout(action_row)

    scroll_area.setWidget(scroll_content)
    panel_lay.addWidget(scroll_area, 1)

    outer.addWidget(panel)
