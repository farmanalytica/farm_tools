# -*- coding: utf-8 -*-
"""
SYSI (Synthetic Soil Image) page for the RAVI dialog.

Two-tab layout: Intro (what SYSI is) → Inputs (parameters + generate).
SYSI builds a bare-soil reflectance composite from Sentinel-2 using GEOS3
bare-soil detection, NDVI/NBR2 thresholds, cloud filtering and a month
selection. Signal connections are wired externally by ``farm_tools.py`` once the
service layer is in place.
"""

from qgis.core import QgsMapLayerProxyModel
from qgis.gui import QgsMapLayerComboBox
from qgis.PyQt.QtCore import (
    Qt,
    QCoreApplication,
    QDate,
)
from qgis.PyQt.QtWidgets import (
    QCheckBox,
    QDateEdit,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QSlider,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from .radar import (
    _CALENDAR_STYLE,
    _POPUP_VIEW_STYLE,
    _SLIDER_STYLE,
    _TAB_ACTIVE,
    _TAB_INACTIVE,
    _caption,
    _field_label,
    _prepare_field,
    _section_panel,
)
from .range_slider import RangeSlider
from .styles import STYLE_BTN_PRIMARY, STYLE_BTN_SECONDARY, STYLE_CHECKBOX


def _tr(text):
    return QCoreApplication.translate("RAVI", text)


def _value_lbl(text):
    lbl = QLabel(text)
    lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
    lbl.setStyleSheet(
        "color: #616161; font-size: 10px; background: transparent; border: none;"
    )
    return lbl


_MONTHS = [
    ("Jan", 1), ("Feb", 2), ("Mar", 3), ("Apr", 4),
    ("May", 5), ("Jun", 6), ("Jul", 7), ("Aug", 8),
    ("Sep", 9), ("Oct", 10), ("Nov", 11), ("Dec", 12),
]


def _build_intro_tab(_dialog, parent):
    """Build the Intro tab explaining what the SYSI module does."""
    outer = QVBoxLayout(parent)
    outer.setContentsMargins(0, 0, 0, 0)
    outer.setSpacing(0)

    scroll = QScrollArea()
    scroll.setWidgetResizable(True)
    scroll.setFrameShape(QFrame.Shape.NoFrame)
    scroll.setStyleSheet("QScrollArea { background: #ffffff; border: none; }")

    w = QWidget()
    w.setStyleSheet("background: #ffffff;")
    lay = QVBoxLayout(w)
    lay.setContentsMargins(24, 16, 24, 16)
    lay.setSpacing(4)

    def _lbl(html, style=""):
        l = QLabel(html)
        l.setWordWrap(True)
        l.setOpenExternalLinks(True)
        l.setTextFormat(Qt.TextFormat.RichText)
        if style:
            l.setStyleSheet(style)
        return l

    def _h1(text):
        return _lbl(text, "font-size:15px;font-weight:bold;color:#1b6b39;margin-bottom:4px;")

    def _h2(text):
        return _lbl(text, "font-size:12px;font-weight:bold;color:#2a5d84;"
                          "padding-bottom:3px;margin-top:12px;margin-bottom:2px;")

    def _para(html):
        return _lbl(html, "font-size:12px;color:#333;")

    def _divider():
        line = QFrame()
        line.setFrameShape(QFrame.Shape.HLine)
        line.setStyleSheet("color:#e6f2fa;")
        return line

    lay.addWidget(_h1(_tr("🌱 SYSI Module - Synthetic Soil Image")))
    lay.addSpacing(2)
    lay.addWidget(_para(_tr(
        "The SYSI module builds a <b>Synthetic Soil Image</b>: a bare-soil "
        "reflectance composite derived from a multi-temporal Sentinel-2 "
        "collection. It runs the <b>GEOS3</b> (Geospatial Soil Sensing System) "
        "algorithm of Demattê et al. (2018) on Google Earth Engine, keeping "
        "only the pixels that are bare soil across many dates and reducing them "
        "with a temporal <b>median</b>. The result reveals the underlying soil "
        "surface free of vegetation and crop residue — no coding required."
    )))

    lay.addWidget(_h2(_tr("📋 Workflow")))
    lay.addWidget(_divider())
    wf_frame = QFrame()
    wf_frame.setStyleSheet("QFrame{background:#f0f8ff;border-radius:4px;padding:4px;}")
    wf_lay = QVBoxLayout(wf_frame)
    wf_lay.setContentsMargins(12, 6, 12, 6)
    wf_lay.setSpacing(4)
    for i, text in enumerate([
        _tr("<b>Inputs:</b> Select the area (AOI), date range and bare-soil parameters"),
        _tr("<b>Generate:</b> Run the composite to build the synthetic soil image"),
        _tr("<b>Load:</b> The SYSI raster is loaded into QGIS automatically"),
    ], 1):
        wf_lay.addWidget(_para(f"{i}. {text}"))
    lay.addWidget(wf_frame)

    lay.addWidget(_h2(_tr("✨ Main Features")))
    lay.addWidget(_divider())
    for text in [
        _tr("<b>Area &amp; Date Selection:</b> Define the AOI and the period to scan"),
        _tr("<b>Month Filter:</b> Restrict the composite to chosen months of the year"),
        _tr("<b>GEOS3 Bare-Soil Detection:</b> NDVI and NBR2 thresholds isolate bare soil"),
        _tr("<b>Cloud Filtering:</b> Drop scenes above a cloud-cover threshold"),
        _tr("<b>Download Buffer:</b> Expand or crop the clipped output around the AOI"),
        _tr("<b>Auto-Load:</b> The generated soil image loads in QGIS automatically"),
    ]:
        lay.addWidget(_para(f"✓  {text}"))

    lay.addWidget(_h2(_tr("🛰️ Bands")))
    lay.addWidget(_divider())
    lay.addWidget(_para(_tr(
        "The synthetic soil image carries the Sentinel-2 surface-reflectance "
        "bands together with the soil indices computed during processing:"
    )))
    for text in [
        _tr("<b>Blue, Green, Red, Red-edge, NIR, SWIR1, SWIR2:</b> surface reflectance"),
        _tr("<b>NDVI:</b> Normalized Difference Vegetation Index"),
        _tr("<b>NBR2:</b> Normalized Burn Ratio 2"),
    ]:
        lay.addWidget(_para(f"• {text}"))

    lay.addWidget(_h2(_tr("🔬 How It Works")))
    lay.addWidget(_divider())
    lay.addWidget(_para(_tr(
        "Processing runs entirely in the cloud on Google Earth Engine, using "
        "the Sentinel-2 surface-reflectance collection "
        "(<tt>COPERNICUS/S2_SR_HARMONIZED</tt>), in four steps:"
    )))
    for i, text in enumerate([
        _tr("<b>Collection &amp; filtering:</b> scenes are filtered by AOI, by "
            "cloud cover (with the QA60 quality mask) and by the months you choose"),
        _tr("<b>Spectral indices:</b> NDVI, NBR2, the Green-Blue (GRBL) and "
            "Red-Green (REGR) band differences and the VNSIR tendency index are "
            "computed per scene"),
        _tr("<b>GEOS3 mask:</b> a pixel is kept as bare soil only when it meets "
            "the NDVI and NBR2 thresholds, VNSIR ≤ 0.9, and GRBL &gt; 0 and REGR &gt; 0"),
        _tr("<b>Temporal median:</b> surviving soil pixels are reduced with a "
            "median, removing transient moisture and filling cloud/vegetation gaps"),
    ], 1):
        lay.addWidget(_para(f"{i}. {text}"))

    lay.addWidget(_h2(_tr("🔧 Initial Setup")))
    lay.addWidget(_divider())
    lay.addWidget(_para(_tr(
        "To use this module you need authentication to Google Earth Engine via "
        'a <b>Google Cloud Project ID</b>. Configure this in the "Auth" tab of '
        "the plugin."
    )))

    lay.addWidget(_h2(_tr("📚 Reference")))
    lay.addWidget(_divider())
    lay.addWidget(_para(_tr(
        "DEMATTÊ, J. A. M.; FONGARO, C. T.; RIZZO, R.; SAFANELLI, J. L. "
        "<i>Geospatial Soil Sensing System (GEOS3): A powerful data mining "
        "procedure to retrieve soil spectral reflectance from satellite "
        "images.</i> Remote Sensing of Environment, v. 212, p. 161–175, 2018. "
        '<a href="https://doi.org/10.1016/j.rse.2018.04.047">'
        "doi:10.1016/j.rse.2018.04.047</a>"
    )))

    lay.addStretch(1)
    scroll.setWidget(w)
    outer.addWidget(scroll, 1)


def _threshold_row(label_text, range_slider):
    """A labeled range-slider row for NDVI/NBR2 thresholds."""
    box = QWidget()
    box.setStyleSheet("background: transparent;")
    row = QHBoxLayout(box)
    row.setContentsMargins(0, 0, 0, 0)
    row.setSpacing(8)

    name = QLabel(label_text)
    name.setMinimumWidth(54)
    name.setStyleSheet(
        "color: #616161; font-size: 12px; font-weight: bold;"
        " background: transparent; border: none;"
    )
    row.addWidget(name)
    row.addWidget(range_slider, 1)
    return box


def _build_inputs_tab(dialog, parent):
    outer = QVBoxLayout(parent)
    outer.setContentsMargins(0, 0, 0, 0)
    outer.setSpacing(0)

    scroll = QScrollArea()
    scroll.setWidgetResizable(True)
    scroll.setFrameShape(QFrame.Shape.NoFrame)
    scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
    scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
    scroll.setStyleSheet("QScrollArea { background: transparent; border: none; }")

    scroll_w = QWidget()
    scroll_w.setStyleSheet("background: transparent;")
    lay = QVBoxLayout(scroll_w)
    lay.setContentsMargins(6, 16, 6, 14)
    lay.setSpacing(12)

    # --- AOI + dates -----------------------------------------------------
    inputs_panel = _section_panel()
    inputs_lay = QVBoxLayout(inputs_panel)
    inputs_lay.setContentsMargins(16, 14, 16, 14)
    inputs_lay.setSpacing(10)

    inputs_lay.addWidget(_field_label(_tr("AOI LAYER")))

    aoi_row = QWidget()
    aoi_row_lay = QHBoxLayout(aoi_row)
    aoi_row_lay.setContentsMargins(0, 0, 0, 0)
    aoi_row_lay.setSpacing(6)

    dialog.sysi_layer_combo = QgsMapLayerComboBox()
    dialog.sysi_layer_combo.setFilters(QgsMapLayerProxyModel.VectorLayer)
    _prepare_field(dialog.sysi_layer_combo)
    dialog.sysi_layer_combo.setAllowEmptyLayer(True)
    dialog.sysi_layer_combo.view().setStyleSheet(_POPUP_VIEW_STYLE)
    aoi_row_lay.addWidget(dialog.sysi_layer_combo, 1)

    dialog.sysi_btn_draw_aoi = QPushButton(_tr("Draw AOI"))
    dialog.sysi_btn_draw_aoi.setToolTip(
        _tr("Drag on the map to draw a box (Shift = square, Esc = cancel)")
    )
    dialog.sysi_btn_draw_aoi.setFixedHeight(28)
    dialog.sysi_btn_draw_aoi.setSizePolicy(
        QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed
    )
    dialog.sysi_btn_draw_aoi.adjustSize()
    dialog.sysi_btn_draw_aoi.setStyleSheet(STYLE_BTN_SECONDARY)
    aoi_row_lay.addWidget(dialog.sysi_btn_draw_aoi)

    dialog.sysi_btn_hybrid_layer = QPushButton(_tr("Add Google Hybrid Layer"))
    dialog.sysi_btn_hybrid_layer.setFixedHeight(28)
    dialog.sysi_btn_hybrid_layer.setSizePolicy(
        QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed
    )
    dialog.sysi_btn_hybrid_layer.adjustSize()
    dialog.sysi_btn_hybrid_layer.setStyleSheet(STYLE_BTN_SECONDARY)
    aoi_row_lay.addWidget(dialog.sysi_btn_hybrid_layer)

    inputs_lay.addWidget(aoi_row)
    inputs_lay.addSpacing(6)

    fields_grid = QGridLayout()
    fields_grid.setContentsMargins(0, 0, 0, 0)
    fields_grid.setHorizontalSpacing(16)
    fields_grid.setVerticalSpacing(8)
    fields_grid.setColumnStretch(0, 1)
    fields_grid.setColumnStretch(1, 1)

    dialog.sysi_date_start = QDateEdit()
    dialog.sysi_date_start.setDisplayFormat("yyyy-MM-dd")
    dialog.sysi_date_start.setCalendarPopup(True)
    dialog.sysi_date_start.setDate(QDate.fromString("2017-03-28", "yyyy-MM-dd"))
    _prepare_field(dialog.sysi_date_start)
    dialog.sysi_date_end = QDateEdit()
    dialog.sysi_date_end.setDisplayFormat("yyyy-MM-dd")
    dialog.sysi_date_end.setCalendarPopup(True)
    dialog.sysi_date_end.setDate(QDate.currentDate())
    _prepare_field(dialog.sysi_date_end)
    for _cal in (
        dialog.sysi_date_start.calendarWidget(),
        dialog.sysi_date_end.calendarWidget(),
    ):
        if _cal is not None:
            _cal.setStyleSheet(_CALENDAR_STYLE)

    fields_grid.addWidget(_field_label(_tr("START DATE")), 0, 0)
    fields_grid.addWidget(_field_label(_tr("END DATE")), 0, 1)
    fields_grid.addWidget(dialog.sysi_date_start, 1, 0)
    fields_grid.addWidget(dialog.sysi_date_end, 1, 1)
    inputs_lay.addLayout(fields_grid)

    lay.addWidget(inputs_panel)

    # --- Included months -------------------------------------------------
    months_panel = _section_panel()
    months_lay = QVBoxLayout(months_panel)
    months_lay.setContentsMargins(16, 14, 16, 14)
    months_lay.setSpacing(10)
    months_lay.addWidget(_field_label(_tr("INCLUDED MONTHS")))

    months_grid = QGridLayout()
    months_grid.setContentsMargins(0, 0, 0, 0)
    months_grid.setHorizontalSpacing(14)
    months_grid.setVerticalSpacing(8)
    dialog.sysi_month_checks = {}
    for idx, (name, month) in enumerate(_MONTHS):
        chk = QCheckBox(_tr(name))
        chk.setChecked(True)
        chk.setStyleSheet(STYLE_CHECKBOX)
        dialog.sysi_month_checks[month] = chk
        months_grid.addWidget(chk, idx // 6, idx % 6)
    months_lay.addLayout(months_grid)
    lay.addWidget(months_panel)

    # --- Thresholds ------------------------------------------------------
    thr_panel = _section_panel()
    thr_lay = QVBoxLayout(thr_panel)
    thr_lay.setContentsMargins(16, 14, 16, 14)
    thr_lay.setSpacing(10)
    thr_lay.addWidget(_field_label(_tr("BARE-SOIL THRESHOLDS")))

    dialog.sysi_ndvi_range_slider = RangeSlider(-1.0, 1.0, -0.25, 0.25)
    thr_lay.addWidget(_threshold_row(_tr("NDVI"), dialog.sysi_ndvi_range_slider))

    dialog.sysi_nbr_range_slider = RangeSlider(-1.0, 1.0, -0.30, 0.10)
    thr_lay.addWidget(_threshold_row(_tr("NBR2"), dialog.sysi_nbr_range_slider))

    hint = QLabel(_tr("Keep Min &lt; Max. Pixels inside both ranges are kept as bare soil."))
    hint.setWordWrap(True)
    hint.setTextFormat(Qt.TextFormat.RichText)
    hint.setStyleSheet(
        "color: #9e9e9e; font-size: 10px; background: transparent; border: none;"
    )
    thr_lay.addWidget(hint)
    lay.addWidget(thr_panel)

    # --- Cloud cover -----------------------------------------------------
    cloud_panel = _section_panel()
    cloud_lay = QVBoxLayout(cloud_panel)
    cloud_lay.setContentsMargins(16, 14, 16, 14)
    cloud_lay.setSpacing(8)
    cloud_lay.addWidget(_caption(_tr("CLOUD PIXEL PERCENTAGE (TILE)")))

    cloud_row = QHBoxLayout()
    cloud_row.setContentsMargins(0, 0, 0, 0)
    cloud_row.setSpacing(8)
    cloud_min = QLabel("0%")
    cloud_min.setStyleSheet(
        "color: #9e9e9e; font-size: 9px; background: transparent; border: none;"
    )
    cloud_row.addWidget(cloud_min)
    dialog.sysi_cloud_slider = QSlider(Qt.Orientation.Horizontal)
    dialog.sysi_cloud_slider.setMinimum(0)
    dialog.sysi_cloud_slider.setMaximum(100)
    dialog.sysi_cloud_slider.setValue(10)
    dialog.sysi_cloud_slider.setStyleSheet(_SLIDER_STYLE)
    cloud_row.addWidget(dialog.sysi_cloud_slider, 1)
    cloud_max = QLabel("100%")
    cloud_max.setStyleSheet(
        "color: #9e9e9e; font-size: 9px; background: transparent; border: none;"
    )
    cloud_row.addWidget(cloud_max)
    cloud_lay.addLayout(cloud_row)

    dialog.sysi_cloud_value = _value_lbl("10%")
    cloud_lay.addWidget(dialog.sysi_cloud_value)

    def _sync_cloud(v):
        dialog.sysi_cloud_value.setText(f"{v}%")

    dialog.sysi_cloud_slider.valueChanged.connect(_sync_cloud)
    lay.addWidget(cloud_panel)

    # --- Download buffer -------------------------------------------------
    buffer_panel = _section_panel()
    buffer_lay = QVBoxLayout(buffer_panel)
    buffer_lay.setContentsMargins(16, 14, 16, 14)
    buffer_lay.setSpacing(10)
    buffer_lay.addWidget(_caption(_tr("DOWNLOAD BUFFER")))
    buffer_hint = QLabel(
        _tr("Use a positive buffer to include terrain just outside your area, "
            "or a negative buffer to crop the edges. Applied on the clipped "
            "synthetic soil image.")
    )
    buffer_hint.setWordWrap(True)
    buffer_hint.setStyleSheet(
        "color: #757575; font-size: 11px; background: transparent; border: none;"
    )
    buffer_lay.addWidget(buffer_hint)

    buffer_row = QHBoxLayout()
    buffer_row.setContentsMargins(0, 0, 0, 0)
    buffer_row.setSpacing(8)
    minus_lbl = QLabel("−300 m")
    minus_lbl.setStyleSheet(
        "color: #9e9e9e; font-size: 9px; background: transparent; border: none;"
    )
    buffer_row.addWidget(minus_lbl)
    dialog.sysi_buffer_slider = QSlider(Qt.Orientation.Horizontal)
    dialog.sysi_buffer_slider.setMinimum(-300)
    dialog.sysi_buffer_slider.setMaximum(300)
    dialog.sysi_buffer_slider.setSingleStep(1)
    dialog.sysi_buffer_slider.setPageStep(10)
    dialog.sysi_buffer_slider.setValue(0)
    dialog.sysi_buffer_slider.setStyleSheet(_SLIDER_STYLE)
    buffer_row.addWidget(dialog.sysi_buffer_slider, 1)
    plus_lbl = QLabel("+300 m")
    plus_lbl.setStyleSheet(
        "color: #9e9e9e; font-size: 9px; background: transparent; border: none;"
    )
    buffer_row.addWidget(plus_lbl)
    buffer_lay.addLayout(buffer_row)

    dialog.sysi_buffer_value = _value_lbl(_tr("Buffer: 0 m"))
    buffer_lay.addWidget(dialog.sysi_buffer_value)

    def _set_sysi_buffer_value(value):
        value = 0 if -3 <= value <= 3 else value
        if dialog.sysi_buffer_slider.value() != value:
            dialog.sysi_buffer_slider.blockSignals(True)
            dialog.sysi_buffer_slider.setValue(value)
            dialog.sysi_buffer_slider.blockSignals(False)
        dialog.sysi_buffer_value.setText(
            _tr("Buffer: %+d m") % value if value != 0 else _tr("Buffer: 0 m")
        )

    dialog.sysi_buffer_slider.valueChanged.connect(_set_sysi_buffer_value)
    lay.addWidget(buffer_panel)

    lay.addStretch(1)

    for _btn in scroll_w.findChildren(QPushButton):
        _btn.setFocusPolicy(Qt.FocusPolicy.NoFocus)

    scroll.setWidget(scroll_w)
    outer.addWidget(scroll)


def setup_sysi_page(dialog, page):
    """
    Populate the SYSI page with a two-tab layout (Intro → Inputs).

    Exposes on dialog:
      sysi_layer_combo, sysi_btn_draw_aoi, sysi_btn_hybrid_layer,
      sysi_date_start, sysi_date_end, sysi_month_checks,
      sysi_ndvi_range_slider, sysi_nbr_range_slider  (RangeSlider instances),
      sysi_cloud_slider, sysi_buffer_slider,
      sysi_stack, sysi_set_tab, sysi_btn_back, sysi_btn_generate, sysi_step_lbl
    """
    page.setObjectName("sysiPage")
    page.setStyleSheet("""
        QWidget#sysiPage { background-color: #ffffff; }
        QComboBox, QgsMapLayerComboBox {
            combobox-popup: 0;
            background-color: #ffffff;
            color: #212121;
            border: 1px solid #d0d0d0;
            border-radius: 6px;
            padding: 4px 9px;
            font-size: 12px;
        }
        QComboBox:focus, QgsMapLayerComboBox:focus { border: 1.5px solid #1b6b39; }
        QComboBox QAbstractItemView, QgsMapLayerComboBox QAbstractItemView {
            background-color: #ffffff;
            color: #212121;
            border: 1px solid #bdbdbd;
            selection-background-color: #e8f5e9;
            selection-color: #1a1a1a;
            outline: 0;
        }
        QDateEdit {
            background-color: #ffffff;
            color: #212121;
            border: 1px solid #d0d0d0;
            border-radius: 6px;
            padding: 2px 4px 2px 8px;
            font-size: 12px;
        }
        QDateEdit:focus { border: 1.5px solid #1b6b39; }
        QLabel { background: transparent; border: none; }
        QCalendarWidget QWidget {
            background-color: #ffffff;
            color: #212121;
            alternate-background-color: #f5f5f5;
        }
        QCalendarWidget QAbstractItemView {
            background-color: #ffffff;
            color: #212121;
            selection-background-color: #1b6b39;
            selection-color: #ffffff;
        }
        QCalendarWidget QWidget#qt_calendar_navigationbar {
            background-color: #f8f9fa;
            border-bottom: 1px solid #e0e0e0;
        }
        QCalendarWidget QToolButton {
            background-color: transparent;
            color: #212121;
            border: none;
            padding: 2px 6px;
            font-size: 12px;
        }
        QCalendarWidget QToolButton:hover {
            background-color: #e8f5e9;
            border-radius: 4px;
        }
        QCalendarWidget QMenu { background-color: #ffffff; color: #212121; }
        QCalendarWidget QSpinBox {
            background-color: #ffffff;
            color: #212121;
            border: 1px solid #d0d0d0;
            border-radius: 4px;
            padding: 2px 4px;
        }
    """)

    outer = QVBoxLayout(page)
    outer.setContentsMargins(0, 0, 0, 0)
    outer.setSpacing(0)

    tab_bar = QFrame()
    tab_bar.setObjectName("sysiTabBar")
    tab_bar.setFixedHeight(40)
    tab_bar.setStyleSheet("""
        QFrame#sysiTabBar {
            background-color: #f8f9fa;
            border-bottom: 1px solid #e0e0e0;
        }
    """)
    tab_bar_lay = QHBoxLayout(tab_bar)
    tab_bar_lay.setContentsMargins(6, 0, 6, 0)
    tab_bar_lay.setSpacing(8)

    btn_tab_intro = QPushButton(_tr("Intro"))
    btn_tab_intro.setFixedHeight(40)
    btn_tab_intro.setCursor(Qt.CursorShape.PointingHandCursor)

    btn_tab_inputs = QPushButton(_tr("Inputs"))
    btn_tab_inputs.setFixedHeight(40)
    btn_tab_inputs.setCursor(Qt.CursorShape.PointingHandCursor)

    tab_bar_lay.addWidget(btn_tab_intro)
    tab_bar_lay.addWidget(btn_tab_inputs)
    tab_bar_lay.addStretch(1)

    outer.addWidget(tab_bar)

    stack = QStackedWidget()
    stack.setStyleSheet("QStackedWidget { background: transparent; border: none; }")

    intro_page = QWidget()
    _build_intro_tab(dialog, intro_page)
    stack.addWidget(intro_page)

    inputs_page = QWidget()
    _build_inputs_tab(dialog, inputs_page)
    stack.addWidget(inputs_page)

    outer.addWidget(stack, 1)
    dialog.sysi_stack = stack

    nav_bar = QFrame()
    nav_bar.setObjectName("sysiNavBar")
    nav_bar.setFixedHeight(46)
    nav_bar.setStyleSheet("""
        QFrame#sysiNavBar {
            background-color: #f8f9fa;
            border-top: 1px solid #e0e0e0;
        }
    """)
    nav_lay = QHBoxLayout(nav_bar)
    nav_lay.setContentsMargins(6, 0, 6, 0)
    nav_lay.setSpacing(8)

    btn_back = QPushButton(_tr("Back"))
    btn_back.setMinimumWidth(90)
    btn_back.setFixedHeight(30)
    btn_back.setStyleSheet(STYLE_BTN_SECONDARY)
    nav_lay.addWidget(btn_back)
    nav_lay.addStretch(1)

    step_lbl = QLabel()
    step_lbl.setStyleSheet("color: #bdbdbd; font-size: 11px; background: transparent;")
    nav_lay.addWidget(step_lbl)
    nav_lay.addStretch(1)

    btn_intro_next = QPushButton(_tr("Next"))
    btn_intro_next.setMinimumWidth(90)
    btn_intro_next.setFixedHeight(30)
    btn_intro_next.setStyleSheet(STYLE_BTN_PRIMARY)
    nav_lay.addWidget(btn_intro_next)

    btn_generate = QPushButton(_tr("Generate SYSI"))
    btn_generate.setMinimumWidth(120)
    btn_generate.setFixedHeight(30)
    btn_generate.setStyleSheet(STYLE_BTN_PRIMARY)
    nav_lay.addWidget(btn_generate)
    outer.addWidget(nav_bar)

    dialog.sysi_btn_back = btn_back
    dialog.sysi_btn_generate = btn_generate
    dialog.sysi_step_lbl = step_lbl

    def _set_tab(index):
        stack.setCurrentIndex(index)
        btn_back.setEnabled(index > 0)
        step_lbl.setText(_tr("Step %d of 2") % (index + 1))
        btn_intro_next.setVisible(index == 0)
        btn_generate.setVisible(index == 1)
        btn_tab_intro.setStyleSheet(_TAB_ACTIVE if index == 0 else _TAB_INACTIVE)
        btn_tab_inputs.setStyleSheet(_TAB_ACTIVE if index == 1 else _TAB_INACTIVE)

    dialog.sysi_set_tab = _set_tab

    btn_tab_intro.clicked.connect(lambda: _set_tab(0))
    btn_tab_inputs.clicked.connect(lambda: _set_tab(1))
    btn_intro_next.clicked.connect(lambda: _set_tab(1))
    btn_back.clicked.connect(
        lambda: _set_tab(stack.currentIndex() - 1) if stack.currentIndex() > 0 else None
    )

    _set_tab(0)
