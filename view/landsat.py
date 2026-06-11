# -*- coding: utf-8 -*-
"""
Landsat Super-Resolution page for the RAVI dialog.

Three-tab layout: Intro → Inputs → Results, mirroring the Optical and SAR pages.
Headline feature is HSV pan-sharpening — merging Landsat's 15 m panchromatic
band into RGB for an effective 15 m "super-resolution" image. Pan-sharpening is
only valid on Top-of-Atmosphere (TOA) products in agrigee_lite, so super-res
output is TOA; vegetation indices and multispectral RGB use the 30 m Surface
Reflectance product instead.

Signal connections are wired externally by ``farm_tools.py``. All interactive widgets
are exposed on ``dialog`` as ``ls_*`` attributes.
"""

from qgis.core import QgsMapLayerProxyModel
from qgis.gui import QgsMapLayerComboBox
from qgis.PyQt.QtCore import Qt, QCoreApplication, QDate
from qgis.PyQt.QtWebKitWidgets import QWebView
from qgis.PyQt.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDateEdit,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QSlider,
    QSplitter,
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
    _flow,
    _labeled,
    _make_divider,
    _prepare_field,
    _section_panel,
)
from .styles import STYLE_BTN_PRIMARY, STYLE_BTN_SECONDARY, STYLE_CHECKBOX
from ..services.landsat_service import (
    LANDSAT_INDEX_ORDER,
    MULTISPECTRAL_MODES,
)


def _tr(text):
    return QCoreApplication.translate("RAVI", text)


_COLOR_RAMPS = ["Viridis", "Magma", "Plasma", "Inferno", "RdYlGn", "Greys"]

# AgriGEE.lite credit links — kept in sync with the welcome page (view/auth.py).
_URL_AGRIGEE = "https://github.com/mateuspinto/AgriGEE.lite"
_URL_MATEUS = "https://www.linkedin.com/in/mateuspinto/"
_LINK_STYLE = "color:#1b6b39; font-weight:bold; text-decoration:none;"

# Multispectral RGB modes (label, stable English key). Keys match
# LandsatService.MULTISPECTRAL_MODES so the renderer survives a translated UI.
_MS_MODE_LABELS = {
    "RGB: Real Color": _tr("Real Color (Red, Green, Blue)"),
    "RGB: NIR-Red-Green": _tr("NIR, Red, Green"),
    "RGB: SWIR1-NIR-Red": _tr("SWIR1, NIR, Red"),
    "RGB: SWIR2-NIR-Green": _tr("SWIR2, NIR, Green"),
}


def _h_lbl(html, style=""):
    lbl = QLabel(html)
    lbl.setWordWrap(True)
    lbl.setOpenExternalLinks(True)
    lbl.setTextFormat(Qt.TextFormat.RichText)
    if style:
        lbl.setStyleSheet(style)
    return lbl


def _build_intro_tab(_dialog, parent):
    """Native-widget intro explaining the Landsat super-resolution suite."""
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

    def _h1(text):
        return _h_lbl(text, "font-size:15px;font-weight:bold;color:#1b6b39;margin-bottom:4px;")

    def _h2(text):
        return _h_lbl(text, "font-size:12px;font-weight:bold;color:#2a5d84;"
                            "padding-bottom:3px;margin-top:12px;margin-bottom:2px;")

    def _para(html):
        return _h_lbl(html, "font-size:12px;color:#333;")

    def _divider():
        line = QFrame()
        line.setFrameShape(QFrame.Shape.HLine)
        line.setStyleSheet("color:#e6f2fa;")
        return line

    lay.addWidget(_h1(_tr("🛰️ Landsat Super-Resolution")))
    lay.addSpacing(2)
    lay.addWidget(_para(_tr(
        "This module sharpens <b>Landsat 7/8/9</b> imagery from 30 m to an "
        "effective <b>15 m</b> using HSV pan-sharpening — merging the 15 m "
        "panchromatic band into the visible RGB channels. Pick an area, a date "
        "range and a mission, then preview and download super-resolution "
        "imagery, vegetation indices and multispectral composites."
    )))

    lay.addWidget(_h2(_tr("📋 Workflow")))
    lay.addWidget(_divider())
    wf_frame = QFrame()
    wf_frame.setStyleSheet("QFrame{background:#f0f8ff;border-radius:4px;padding:4px;}")
    wf_lay = QVBoxLayout(wf_frame)
    wf_lay.setContentsMargins(12, 6, 12, 6)
    wf_lay.setSpacing(4)
    for i, text in enumerate([
        _tr("<b>Inputs:</b> Select the area (AOI), date range and Landsat mission"),
        _tr("<b>Run:</b> List the available acquisition dates over the AOI"),
        _tr("<b>Results:</b> Preview and download super-res RGB, indices and composites"),
    ], 1):
        wf_lay.addWidget(_para(f"{i}. {text}"))
    lay.addWidget(wf_frame)

    lay.addWidget(_h2(_tr("✨ Main Features")))
    lay.addWidget(_divider())
    for text in [
        _tr("<b>Super-Resolution RGB (15 m):</b> Pan-sharpened real-colour imagery for any date"),
        _tr("<b>Vegetation Indices:</b> NDVI, EVI, SAVI and more on 30 m surface reflectance"),
        _tr("<b>Multispectral RGB:</b> True- and false-colour composites from the SR bands"),
        _tr("<b>Batch Download:</b> Pull the super-res image of every available date"),
        _tr("<b>Cloud Masking:</b> USGS QA_PIXEL bitmask removes clouds, shadows and cirrus"),
    ]:
        lay.addWidget(_para(f"✓  {text}"))

    lay.addWidget(_h2(_tr("ℹ️ About the bands")))
    lay.addWidget(_divider())
    lay.addWidget(_para(_tr(
        "Pan-sharpening is only available on <b>Top-of-Atmosphere (TOA)</b> "
        "products, so super-resolution previews are TOA reflectance. Vegetation "
        "indices and multispectral composites use the atmospherically-corrected "
        "<b>Surface Reflectance (SR)</b> product at the native 30 m. Landsat 5 is "
        "not offered — it has no panchromatic band."
    )))

    lay.addWidget(_h2(_tr("🔧 Initial Setup")))
    lay.addWidget(_divider())
    lay.addWidget(_para(_tr(
        "To use this module you need authentication to Google Earth Engine via a "
        '<b>Google Cloud Project ID</b>. Configure this in the "Auth" tab.'
    )))

    credit = QLabel(
        _tr(
            "🛰️ Landsat super-resolution and the vegetation-index time series are "
            "powered by <a href='{agrigee}' style='{ls}'>AgriGEE.lite</a>, in "
            "collaboration with its author "
            "<a href='{mateus}' style='{ls}'>Mateus Pinto</a>."
        ).format(agrigee=_URL_AGRIGEE, mateus=_URL_MATEUS, ls=_LINK_STYLE)
    )
    credit.setWordWrap(True)
    credit.setTextFormat(Qt.TextFormat.RichText)
    credit.setOpenExternalLinks(True)
    credit.setStyleSheet(
        "color: #1b5e20; font-size: 11px; background: #e8f5e9;"
        " border-radius: 4px; padding: 8px 10px;"
    )
    lay.addSpacing(8)
    lay.addWidget(credit)

    lay.addStretch(1)
    scroll.setWidget(w)
    outer.addWidget(scroll, 1)


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

    dialog.ls_layer_combo = QgsMapLayerComboBox()
    dialog.ls_layer_combo.setFilters(QgsMapLayerProxyModel.VectorLayer)
    _prepare_field(dialog.ls_layer_combo)
    dialog.ls_layer_combo.setAllowEmptyLayer(True)
    dialog.ls_layer_combo.view().setStyleSheet(_POPUP_VIEW_STYLE)
    aoi_row_lay.addWidget(dialog.ls_layer_combo, 1)

    dialog.ls_btn_draw_aoi = QPushButton(_tr("Draw AOI"))
    dialog.ls_btn_draw_aoi.setToolTip(
        _tr("Drag on the map to draw a box (Shift = square, Esc = cancel)")
    )
    dialog.ls_btn_draw_aoi.setFixedHeight(28)
    dialog.ls_btn_draw_aoi.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
    dialog.ls_btn_draw_aoi.adjustSize()
    dialog.ls_btn_draw_aoi.setStyleSheet(STYLE_BTN_SECONDARY)
    aoi_row_lay.addWidget(dialog.ls_btn_draw_aoi)

    dialog.ls_btn_hybrid_layer = QPushButton(_tr("Add Google Hybrid Layer"))
    dialog.ls_btn_hybrid_layer.setFixedHeight(28)
    dialog.ls_btn_hybrid_layer.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
    dialog.ls_btn_hybrid_layer.adjustSize()
    dialog.ls_btn_hybrid_layer.setStyleSheet(STYLE_BTN_SECONDARY)
    aoi_row_lay.addWidget(dialog.ls_btn_hybrid_layer)

    inputs_lay.addWidget(aoi_row)
    inputs_lay.addSpacing(6)

    fields_grid = QGridLayout()
    fields_grid.setContentsMargins(0, 0, 0, 0)
    fields_grid.setHorizontalSpacing(16)
    fields_grid.setVerticalSpacing(8)
    fields_grid.setColumnStretch(0, 1)
    fields_grid.setColumnStretch(1, 1)

    dialog.ls_date_start = QDateEdit()
    dialog.ls_date_start.setDisplayFormat("yyyy-MM-dd")
    dialog.ls_date_start.setCalendarPopup(True)
    dialog.ls_date_start.setDate(QDate.currentDate().addYears(-5))
    _prepare_field(dialog.ls_date_start)
    dialog.ls_date_end = QDateEdit()
    dialog.ls_date_end.setDisplayFormat("yyyy-MM-dd")
    dialog.ls_date_end.setCalendarPopup(True)
    dialog.ls_date_end.setDate(QDate.currentDate())
    _prepare_field(dialog.ls_date_end)
    for _cal in (
        dialog.ls_date_start.calendarWidget(),
        dialog.ls_date_end.calendarWidget(),
    ):
        if _cal is not None:
            _cal.setStyleSheet(_CALENDAR_STYLE)

    fields_grid.addWidget(_field_label(_tr("START DATE")), 0, 0)
    fields_grid.addWidget(_field_label(_tr("END DATE")), 0, 1)
    fields_grid.addWidget(dialog.ls_date_start, 1, 0)
    fields_grid.addWidget(dialog.ls_date_end, 1, 1)
    inputs_lay.addLayout(fields_grid)

    coverage_hint = QLabel(_tr(
        "📅 Available coverage: <b>1999 to present</b> — Landsat 7 (1999–2022), "
        "Landsat 8 (2013–) and Landsat 9 (2021–). Dates outside a mission's "
        "lifespan are skipped automatically."
    ))
    coverage_hint.setWordWrap(True)
    coverage_hint.setTextFormat(Qt.TextFormat.RichText)
    coverage_hint.setStyleSheet(
        "color: #1b5e20; font-size: 11px; background: #e8f5e9;"
        " border-radius: 4px; padding: 7px 9px;"
    )
    inputs_lay.addWidget(coverage_hint)

    lay.addWidget(inputs_panel)

    # --- Vegetation index (drives the plot + single-date index image) ----
    index_panel = _section_panel()
    index_lay = QVBoxLayout(index_panel)
    index_lay.setContentsMargins(16, 14, 16, 14)
    index_lay.setSpacing(10)
    index_lay.addWidget(_field_label(_tr("VEGETATION INDEX")))

    dialog.ls_index_combo = QComboBox()
    for name in LANDSAT_INDEX_ORDER:
        dialog.ls_index_combo.addItem(name, name)
    dialog.ls_index_combo.setCurrentText("NDVI")
    _prepare_field(dialog.ls_index_combo)
    dialog.ls_index_combo.view().setStyleSheet(_POPUP_VIEW_STYLE)
    index_lay.addWidget(dialog.ls_index_combo)

    index_hint = QLabel(_tr(
        "Used for the Results time-series plot and the single-date index image. "
        "Only indices computable from Landsat bands are listed (no red-edge)."
    ))
    index_hint.setWordWrap(True)
    index_hint.setStyleSheet("color: #757575; font-size: 11px; background: transparent; border: none;")
    index_lay.addWidget(index_hint)

    index_lay.addWidget(_make_divider())
    index_lay.addWidget(_field_label(_tr("TIME-SERIES SPATIAL REDUCER")))
    dialog.ls_ts_reducer_combo = QComboBox()
    _prepare_field(dialog.ls_ts_reducer_combo)
    dialog.ls_ts_reducer_combo.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToContents)
    # Label, stable agrigee_lite reducer key.
    for _label, _key in ((_tr("Median"), "median"), (_tr("Mean"), "mean")):
        dialog.ls_ts_reducer_combo.addItem(_label, _key)
    dialog.ls_ts_reducer_combo.view().setStyleSheet(_POPUP_VIEW_STYLE)
    index_lay.addWidget(dialog.ls_ts_reducer_combo)

    reducer_hint = QLabel(_tr(
        "How pixels inside the AOI are aggregated to one value per date in the "
        "time-series plot (built automatically when you Run)."
    ))
    reducer_hint.setWordWrap(True)
    reducer_hint.setStyleSheet("color: #757575; font-size: 11px; background: transparent; border: none;")
    index_lay.addWidget(reducer_hint)

    lay.addWidget(index_panel)

    # --- Processing (all missions; cloud mask) --------------------------
    proc_panel = _section_panel()
    proc_lay = QVBoxLayout(proc_panel)
    proc_lay.setContentsMargins(16, 14, 16, 14)
    proc_lay.setSpacing(10)
    proc_lay.addWidget(_field_label(_tr("PROCESSING")))

    missions_hint = QLabel(_tr(
        "Every run searches <b>Landsat 7, 8 and 9</b> together. Each available "
        "date is tagged with its mission in the Results date list."
    ))
    missions_hint.setWordWrap(True)
    missions_hint.setStyleSheet("color: #757575; font-size: 11px; background: transparent; border: none;")
    proc_lay.addWidget(missions_hint)

    proc_lay.addWidget(_make_divider())

    dialog.ls_chk_cloud_mask = QCheckBox(_tr("Apply cloud mask (QA_PIXEL)"))
    dialog.ls_chk_cloud_mask.setChecked(True)
    dialog.ls_chk_cloud_mask.setStyleSheet(STYLE_CHECKBOX)
    proc_lay.addWidget(dialog.ls_chk_cloud_mask)

    cloud_hint = QLabel(_tr(
        "Removes clouds, cloud shadows, cirrus and saturated pixels. Disabling "
        "delivers more dates but with much more noise."
    ))
    cloud_hint.setWordWrap(True)
    cloud_hint.setStyleSheet("color: #757575; font-size: 11px; background: transparent; border: none;")
    proc_lay.addWidget(cloud_hint)

    proc_lay.addWidget(_make_divider())
    proc_lay.addWidget(_field_label(_tr("MIN VALID COVERAGE")))

    coverage_row = QHBoxLayout()
    coverage_row.setContentsMargins(0, 0, 0, 0)
    coverage_row.setSpacing(8)
    dialog.ls_min_valid_slider = QSlider(Qt.Orientation.Horizontal)
    dialog.ls_min_valid_slider.setMinimum(0)
    dialog.ls_min_valid_slider.setMaximum(100)
    dialog.ls_min_valid_slider.setSingleStep(1)
    dialog.ls_min_valid_slider.setPageStep(10)
    dialog.ls_min_valid_slider.setValue(80)
    dialog.ls_min_valid_slider.setStyleSheet(_SLIDER_STYLE)
    coverage_row.addWidget(dialog.ls_min_valid_slider, 1)
    dialog.ls_min_valid_value = QLabel("80%")
    dialog.ls_min_valid_value.setMinimumWidth(42)
    dialog.ls_min_valid_value.setAlignment(
        Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
    )
    dialog.ls_min_valid_value.setStyleSheet(
        "color: #1b6b39; font-size: 11px; font-weight: bold;"
        " background: transparent; border: none;"
    )
    coverage_row.addWidget(dialog.ls_min_valid_value)
    proc_lay.addLayout(coverage_row)

    dialog.ls_min_valid_slider.valueChanged.connect(
        lambda v: dialog.ls_min_valid_value.setText(f"{v}%")
    )

    coverage_filter_hint = QLabel(_tr(
        "Minimum share of the AOI that must hold valid (cloud-free) pixels for a "
        "date to be kept — measured against a fully-covered image at native "
        "resolution. Applies to the available-date list, the time-series plot and "
        "every preview/download. ↑ Higher = stricter (fewer dates). 0% = no filter."
    ))
    coverage_filter_hint.setWordWrap(True)
    coverage_filter_hint.setStyleSheet("color: #757575; font-size: 11px; background: transparent; border: none;")
    proc_lay.addWidget(coverage_filter_hint)

    lay.addWidget(proc_panel)
    lay.addStretch(1)
    scroll.setWidget(scroll_w)
    outer.addWidget(scroll)


def _build_results_tab(dialog, parent):
    outer = QVBoxLayout(parent)
    outer.setContentsMargins(0, 0, 0, 0)
    outer.setSpacing(0)

    # Plotly time-series chart fixed on top, controls below — mirrors the
    # Optical (Sentinel-2) results layout.
    dialog.ls_results_splitter = QSplitter(Qt.Orientation.Vertical)
    dialog.ls_results_splitter.setChildrenCollapsible(False)
    dialog.ls_results_splitter.setHandleWidth(4)
    dialog.ls_results_splitter.setStyleSheet("""
        QSplitter::handle {
            background: transparent;
            margin: 0px 6px;
            border-top: 2px solid #d6e0d9;
        }
        QSplitter::handle:hover { border-top-color: #1b6b39; }
    """)

    dialog.ls_web_view = QWebView()
    dialog.ls_web_view.setStyleSheet(
        "border: 1px solid #dce6df; border-radius: 8px; background: #ffffff;"
    )
    dialog.ls_web_view.setMinimumHeight(200)
    dialog.ls_results_splitter.addWidget(dialog.ls_web_view)

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

    # --- Index time series (agrigee_lite SITS) --------------------------
    ts_panel = _section_panel()
    ts_lay = QVBoxLayout(ts_panel)
    ts_lay.setContentsMargins(16, 14, 16, 14)
    ts_lay.setSpacing(8)
    ts_lay.addWidget(_caption(_tr("INDEX TIME SERIES")))
    ts_hint = QLabel(_tr(
        "The chart above plots the index and reducer chosen on the Inputs tab "
        "across Landsat 7/8/9 — built automatically when you Run."
    ))
    ts_hint.setWordWrap(True)
    ts_hint.setStyleSheet("color: #616161; font-size: 11px; background: transparent; border: none;")
    ts_lay.addWidget(ts_hint)

    dialog.ls_btn_ts_browser = QPushButton(_tr("Open in Browser"))
    dialog.ls_btn_ts_browser.setFixedHeight(30)
    dialog.ls_btn_ts_browser.setStyleSheet(STYLE_BTN_SECONDARY)
    ts_lay.addWidget(_flow([dialog.ls_btn_ts_browser], spacing=12))
    lay.addWidget(ts_panel)

    # --- Shared date selector -------------------------------------------
    date_panel = _section_panel()
    date_lay = QVBoxLayout(date_panel)
    date_lay.setContentsMargins(16, 12, 16, 12)
    date_lay.setSpacing(6)
    date_lay.addWidget(_caption(_tr("ACQUISITION DATE")))
    dialog.ls_date_combo = QComboBox()
    _prepare_field(dialog.ls_date_combo, 30)
    dialog.ls_date_combo.setMinimumWidth(160)
    dialog.ls_date_combo.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToContents)
    dialog.ls_date_combo.view().setStyleSheet(_POPUP_VIEW_STYLE)
    date_lay.addWidget(_labeled(_tr("Date"), dialog.ls_date_combo, 34))
    lay.addWidget(date_panel)

    # --- Super-resolution RGB (headline) --------------------------------
    sr_panel = _section_panel()
    sr_lay = QVBoxLayout(sr_panel)
    sr_lay.setContentsMargins(16, 14, 16, 14)
    sr_lay.setSpacing(8)
    sr_lay.addWidget(_caption(_tr("SUPER-RESOLUTION RGB (15 m)")))
    sr_note = QLabel(_tr(
        "Pan-sharpened real-colour image. Previews are top-of-atmosphere (TOA)."
    ))
    sr_note.setWordWrap(True)
    sr_note.setStyleSheet("color: #616161; font-size: 11px; background: transparent; border: none;")
    sr_lay.addWidget(sr_note)

    dialog.ls_btn_sr_preview = QPushButton(_tr("Preview"))
    dialog.ls_btn_sr_preview.setFixedHeight(30)
    dialog.ls_btn_sr_preview.setStyleSheet(STYLE_BTN_PRIMARY)
    dialog.ls_btn_sr_download = QPushButton(_tr("Download & Preview").replace("&", "&&"))
    dialog.ls_btn_sr_download.setFixedHeight(30)
    dialog.ls_btn_sr_download.setStyleSheet(STYLE_BTN_SECONDARY)
    dialog.ls_btn_sr_batch = QPushButton(_tr("Batch Download (All Dates)"))
    dialog.ls_btn_sr_batch.setFixedHeight(30)
    dialog.ls_btn_sr_batch.setStyleSheet(STYLE_BTN_SECONDARY)
    sr_lay.addWidget(_flow([
        dialog.ls_btn_sr_preview,
        dialog.ls_btn_sr_download,
        dialog.ls_btn_sr_batch,
    ], spacing=10))
    lay.addWidget(sr_panel)

    # --- Vegetation index (30 m SR) -------------------------------------
    vi_panel = _section_panel()
    vi_lay = QVBoxLayout(vi_panel)
    vi_lay.setContentsMargins(16, 14, 16, 14)
    vi_lay.setSpacing(8)
    vi_lay.addWidget(_caption(_tr("VEGETATION INDEX (30 m)")))
    vi_hint = QLabel(_tr(
        "Single-date image of the index chosen on the Inputs tab, on 30 m "
        "surface reflectance."
    ))
    vi_hint.setWordWrap(True)
    vi_hint.setStyleSheet("color: #616161; font-size: 11px; background: transparent; border: none;")
    vi_lay.addWidget(vi_hint)

    dialog.ls_index_ramp_combo = QComboBox()
    _prepare_field(dialog.ls_index_ramp_combo, 30)
    dialog.ls_index_ramp_combo.setMinimumWidth(90)
    dialog.ls_index_ramp_combo.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToContents)
    dialog.ls_index_ramp_combo.addItems(_COLOR_RAMPS)
    dialog.ls_index_ramp_combo.setCurrentText("RdYlGn")
    dialog.ls_index_ramp_combo.view().setStyleSheet(_POPUP_VIEW_STYLE)

    dialog.ls_btn_index_preview = QPushButton(_tr("Preview"))
    dialog.ls_btn_index_preview.setFixedHeight(30)
    dialog.ls_btn_index_preview.setStyleSheet(STYLE_BTN_PRIMARY)
    dialog.ls_btn_index_download = QPushButton(_tr("Download & Preview").replace("&", "&&"))
    dialog.ls_btn_index_download.setFixedHeight(30)
    dialog.ls_btn_index_download.setStyleSheet(STYLE_BTN_SECONDARY)
    vi_lay.addWidget(_flow([
        _labeled(_tr("Color Ramp"), dialog.ls_index_ramp_combo, 80),
        dialog.ls_btn_index_preview,
        dialog.ls_btn_index_download,
    ], spacing=12))
    lay.addWidget(vi_panel)

    # --- Multispectral RGB (30 m SR) ------------------------------------
    ms_panel = _section_panel()
    ms_lay = QVBoxLayout(ms_panel)
    ms_lay.setContentsMargins(16, 14, 16, 14)
    ms_lay.setSpacing(8)
    ms_lay.addWidget(_caption(_tr("MULTISPECTRAL RGB (30 m)")))

    dialog.ls_ms_mode_combo = QComboBox()
    _prepare_field(dialog.ls_ms_mode_combo, 30)
    dialog.ls_ms_mode_combo.setMinimumWidth(200)
    dialog.ls_ms_mode_combo.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToContents)
    for key in MULTISPECTRAL_MODES:
        dialog.ls_ms_mode_combo.addItem(_MS_MODE_LABELS.get(key, key), key)
    dialog.ls_ms_mode_combo.view().setStyleSheet(_POPUP_VIEW_STYLE)

    dialog.ls_btn_ms_preview = QPushButton(_tr("Preview"))
    dialog.ls_btn_ms_preview.setFixedHeight(30)
    dialog.ls_btn_ms_preview.setStyleSheet(STYLE_BTN_PRIMARY)
    dialog.ls_btn_ms_download = QPushButton(_tr("Download & Preview").replace("&", "&&"))
    dialog.ls_btn_ms_download.setFixedHeight(30)
    dialog.ls_btn_ms_download.setStyleSheet(STYLE_BTN_SECONDARY)
    ms_lay.addWidget(_flow([
        _labeled(_tr("Rendering"), dialog.ls_ms_mode_combo, 70),
        dialog.ls_btn_ms_preview,
        dialog.ls_btn_ms_download,
    ], spacing=12))
    lay.addWidget(ms_panel)

    # --- Download buffer -------------------------------------------------
    buffer_panel = _section_panel()
    buffer_lay = QVBoxLayout(buffer_panel)
    buffer_lay.setContentsMargins(16, 14, 16, 14)
    buffer_lay.setSpacing(10)
    buffer_lay.addWidget(_caption(_tr("DOWNLOAD BUFFER")))
    buffer_hint = QLabel(
        _tr("Use a positive buffer to include terrain just outside your area, or a "
            "negative buffer to crop the edges. Applies to every previewed and "
            "downloaded image.")
    )
    buffer_hint.setWordWrap(True)
    buffer_hint.setStyleSheet("color: #757575; font-size: 11px; background: transparent; border: none;")
    buffer_lay.addWidget(buffer_hint)

    buffer_row = QHBoxLayout()
    buffer_row.setContentsMargins(0, 0, 0, 0)
    buffer_row.setSpacing(8)
    minus_lbl = QLabel("−300 m")
    minus_lbl.setStyleSheet("color: #9e9e9e; font-size: 9px; background: transparent; border: none;")
    buffer_row.addWidget(minus_lbl)
    dialog.ls_buffer_slider = QSlider(Qt.Orientation.Horizontal)
    dialog.ls_buffer_slider.setMinimum(-300)
    dialog.ls_buffer_slider.setMaximum(300)
    dialog.ls_buffer_slider.setSingleStep(1)
    dialog.ls_buffer_slider.setPageStep(10)
    dialog.ls_buffer_slider.setValue(0)
    dialog.ls_buffer_slider.setStyleSheet(_SLIDER_STYLE)
    buffer_row.addWidget(dialog.ls_buffer_slider, 1)
    plus_lbl = QLabel("+300 m")
    plus_lbl.setStyleSheet("color: #9e9e9e; font-size: 9px; background: transparent; border: none;")
    buffer_row.addWidget(plus_lbl)
    buffer_lay.addLayout(buffer_row)

    dialog.ls_buffer_value = QLabel(_tr("Buffer: 0 m"))
    dialog.ls_buffer_value.setAlignment(Qt.AlignmentFlag.AlignCenter)
    dialog.ls_buffer_value.setStyleSheet("color: #616161; font-size: 10px; background: transparent; border: none;")
    buffer_lay.addWidget(dialog.ls_buffer_value)

    def _set_ls_buffer_value(value):
        value = 0 if -3 <= value <= 3 else value
        if dialog.ls_buffer_slider.value() != value:
            dialog.ls_buffer_slider.blockSignals(True)
            dialog.ls_buffer_slider.setValue(value)
            dialog.ls_buffer_slider.blockSignals(False)
        dialog.ls_buffer_value.setText(
            _tr("Buffer: %+d m") % value if value != 0 else _tr("Buffer: 0 m")
        )

    dialog.ls_buffer_slider.valueChanged.connect(_set_ls_buffer_value)
    lay.addWidget(buffer_panel)
    lay.addStretch(1)

    # Mouse-driven buttons: drop from the focus chain so disabling one mid-run
    # does not show a stray focus ring on the next (same as optical/SAR).
    for _btn in scroll_w.findChildren(QPushButton):
        _btn.setFocusPolicy(Qt.FocusPolicy.NoFocus)

    scroll.setWidget(scroll_w)
    dialog.ls_results_splitter.addWidget(scroll)
    dialog.ls_results_splitter.setStretchFactor(0, 1)
    dialog.ls_results_splitter.setStretchFactor(1, 0)
    outer.addWidget(dialog.ls_results_splitter)


def setup_landsat_page(dialog, page):
    """
    Populate the Landsat Super-Resolution page with a three-tab layout.

    Exposes on dialog (selected):
      ls_layer_combo, ls_btn_draw_aoi, ls_btn_hybrid_layer,
      ls_date_start, ls_date_end, ls_index_combo, ls_ts_reducer_combo,
      ls_chk_cloud_mask, ls_min_valid_slider, ls_min_valid_value,
      ls_date_combo, ls_web_view, ls_btn_ts_browser,
      ls_btn_sr_preview, ls_btn_sr_download, ls_btn_sr_batch,
      ls_index_ramp_combo, ls_btn_index_preview, ls_btn_index_download,
      ls_ms_mode_combo, ls_btn_ms_preview, ls_btn_ms_download,
      ls_buffer_slider, ls_buffer_value,
      ls_stack, ls_set_tab, ls_btn_back, ls_btn_run
    """
    page.setObjectName("landsatPage")
    page.setStyleSheet("""
        QWidget#landsatPage { background-color: #ffffff; }
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
    tab_bar.setObjectName("landsatTabBar")
    tab_bar.setFixedHeight(40)
    tab_bar.setStyleSheet("""
        QFrame#landsatTabBar {
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
    btn_tab_results = QPushButton(_tr("Results"))
    btn_tab_results.setFixedHeight(40)
    btn_tab_results.setCursor(Qt.CursorShape.PointingHandCursor)

    tab_bar_lay.addWidget(btn_tab_intro)
    tab_bar_lay.addWidget(btn_tab_inputs)
    tab_bar_lay.addWidget(btn_tab_results)
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

    results_page = QWidget()
    _build_results_tab(dialog, results_page)
    stack.addWidget(results_page)

    outer.addWidget(stack, 1)
    dialog.ls_stack = stack

    nav_bar = QFrame()
    nav_bar.setObjectName("landsatNavBar")
    nav_bar.setFixedHeight(46)
    nav_bar.setStyleSheet("""
        QFrame#landsatNavBar {
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

    btn_run = QPushButton(_tr("Run"))
    btn_run.setMinimumWidth(90)
    btn_run.setFixedHeight(30)
    btn_run.setStyleSheet(STYLE_BTN_PRIMARY)
    nav_lay.addWidget(btn_run)
    outer.addWidget(nav_bar)

    dialog.ls_btn_back = btn_back
    dialog.ls_btn_run = btn_run
    dialog.ls_step_lbl = step_lbl

    def _set_tab(index):
        stack.setCurrentIndex(index)
        btn_back.setEnabled(index > 0)
        step_lbl.setText(_tr("Step %d of 3") % (index + 1))
        btn_intro_next.setVisible(index == 0)
        btn_run.setVisible(index == 1)
        btn_tab_intro.setStyleSheet(_TAB_ACTIVE if index == 0 else _TAB_INACTIVE)
        btn_tab_inputs.setStyleSheet(_TAB_ACTIVE if index == 1 else _TAB_INACTIVE)
        btn_tab_results.setStyleSheet(_TAB_ACTIVE if index == 2 else _TAB_INACTIVE)

    dialog.ls_set_tab = _set_tab

    btn_tab_intro.clicked.connect(lambda: _set_tab(0))
    btn_tab_inputs.clicked.connect(lambda: _set_tab(1))
    btn_tab_results.clicked.connect(lambda: _set_tab(2))
    btn_intro_next.clicked.connect(lambda: _set_tab(1))
    btn_back.clicked.connect(
        lambda: _set_tab(stack.currentIndex() - 1) if stack.currentIndex() > 0 else None
    )

    _set_tab(0)
