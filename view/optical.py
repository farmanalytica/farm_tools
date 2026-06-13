# -*- coding: utf-8 -*-
"""
Optical Imagery (Sentinel-2) page for the RAVI dialog.

Three-tab layout: Intro → Inputs → Results, mirroring the SAR page
(``view/radar.py``). The Inputs tab is intentionally minimal (AOI layer, date
range, vegetation index + inline custom builder); all cloud / SCL / coverage /
date / smoothing filtering lives in the Results "Adjust filter" popup, which
re-filters cached image metadata client-side (no new GEE call).

Signal connections will be wired externally by ``farm_tools.py`` once the service
layer is in place. All interactive widgets are exposed on ``dialog`` as
``s2_*`` attributes.
"""

from qgis.core import QgsMapLayerProxyModel
from qgis.gui import QgsMapLayerComboBox
from qgis.PyQt.QtCore import Qt, QCoreApplication, QDate
from qgis.PyQt.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDateEdit,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QSlider,
    QAbstractSpinBox,
    QSpinBox,
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
from .optical_filter_dialog import OpticalFilterDialog
from .optical_index_info import (
    CUSTOM_BAND_REFERENCE,
    CUSTOM_INDEX_LABEL,
    INDEX_ORDER,
    VEGETATION_INDICES,
)
from .webcompat import QWebView
from ..tools.indexes import load_custom_indexes


def _tr(text):
    return QCoreApplication.translate("RAVI", text)


# RGB composite render modes for the multispectral single-date image. itemData
# holds a stable English key so the renderer keeps working under a translated UI
# (same trick as SAR).
_RGB_RENDER_MODES = [
    (_tr("Real Color (B4, B3, B2)"), "RGB: Real Color"),
    (_tr("Red, NIR, Green"), "RGB: Red-NIR-Green"),
    (_tr("NIR, Red, Green"), "RGB: NIR-Red-Green"),
    (_tr("SWIR2, NIR, Green"), "RGB: SWIR2-NIR-Green"),
    (_tr("SWIR1, NIR, SWIR2"), "RGB: SWIR1-NIR-SWIR2"),
]

_COMPOSITE_METRICS = [
    "Mean",
    "Median",
    "Min",
    "Max",
    "Amplitude",
    "Standard Deviation",
    "Sum",
    "Area Under Curve (AUC)",
]

_COLOR_RAMPS = ["Viridis", "Magma", "Plasma", "Inferno", "RdYlGn", "Greys"]

# Segmented toggle over the plot (AOI / Points / Features). The %s slot carries
# the per-segment corner-radius so the three buttons join into one control.
# Checked = active view (green); disabled = no data yet for that view.
_SEGMENT_STYLE = """
QPushButton {
    background: #ffffff;
    color: #1b6b39;
    border: 1px solid #cfe0d5;
    padding: 0 16px;
    font-size: 11px;
    font-weight: bold;
    %s
}
QPushButton:checked {
    background: #1b6b39;
    color: #ffffff;
    border-color: #1b6b39;
}
QPushButton:hover:!checked:enabled { background: #eef5f0; }
QPushButton:disabled { color: #b8c4bc; background: #f5f7f6; }
"""

# Sentinel-2 Scene Classification Layer classes (0–11). Masking these changes
# the pixel values used for indices and imagery, so the selection lives on the
# Inputs tab (applied at run time), not in the client-side filter popup. The
# cloud / shadow / defect classes are masked by default.
_SCL_CLASSES = [
    (0, "No Data", True),
    (1, "Saturated / defective", True),
    (2, "Dark area pixels", False),
    (3, "Cloud shadows", True),
    (4, "Vegetation", False),
    (5, "Bare soils", False),
    (6, "Water", False),
    (7, "Cloud low probability", False),
    (8, "Cloud medium probability", True),
    (9, "Cloud high probability", True),
    (10, "Thin cirrus", True),
    (11, "Snow or ice", False),
]


def _h_lbl(html, style=""):
    lbl = QLabel(html)
    lbl.setWordWrap(True)
    lbl.setOpenExternalLinks(True)
    lbl.setTextFormat(Qt.TextFormat.RichText)
    if style:
        lbl.setStyleSheet(style)
    return lbl


def _build_intro_tab(_dialog, parent):
    """Native-widget intro explaining the optical suite (no WebView)."""
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
        return _h_lbl(
            text, "font-size:15px;font-weight:bold;color:#1b6b39;margin-bottom:4px;"
        )

    def _h2(text):
        return _h_lbl(
            text,
            "font-size:12px;font-weight:bold;color:#2a5d84;"
            "padding-bottom:3px;margin-top:12px;margin-bottom:2px;",
        )

    def _para(html):
        return _h_lbl(html, "font-size:12px;color:#333;")

    def _divider():
        line = QFrame()
        line.setFrameShape(QFrame.Shape.HLine)
        line.setStyleSheet("color:#e6f2fa;")
        return line

    lay.addWidget(_h1(_tr("🛰️ Optical Imagery Module - Sentinel-2")))
    lay.addSpacing(2)
    lay.addWidget(
        _para(
            _tr(
                "The Optical module analyses the <b>Sentinel-2 Harmonized Surface "
                "Reflectance</b> collection in Google Earth Engine. Pick an area, a date "
                "range and a vegetation index to build an interactive time series, then "
                "download imagery, composites and indices — no coding required."
            )
        )
    )

    lay.addWidget(_h2(_tr("📋 Workflow")))
    lay.addWidget(_divider())
    wf_frame = QFrame()
    wf_frame.setStyleSheet("QFrame{background:#f0f8ff;border-radius:4px;padding:4px;}")
    wf_lay = QVBoxLayout(wf_frame)
    wf_lay.setContentsMargins(12, 6, 12, 6)
    wf_lay.setSpacing(4)
    for i, text in enumerate(
        [
            _tr(
                "<b>Inputs:</b> Select the area (AOI), date range and vegetation index"
            ),
            _tr("<b>Run:</b> Build the per-date time series over the AOI"),
            _tr(
                "<b>Results:</b> Inspect the plot, adjust the filter, preview and download outputs"
            ),
        ],
        1,
    ):
        wf_lay.addWidget(_para(f"{i}. {text}"))
    lay.addWidget(wf_frame)

    lay.addWidget(_h2(_tr("✨ Main Features")))
    lay.addWidget(_divider())
    for text in [
        _tr(
            "<b>Vegetation Index Time Series:</b> 19 built-in indices plus a custom index builder"
        ),
        _tr("<b>Index Explanations:</b> Description and formula for every index"),
        _tr(
            "<b>True-Color &amp; False-Color Imagery:</b> Download styled RGB rasters for any date"
        ),
        _tr(
            "<b>Synthetic Composite:</b> Aggregate the series (mean, median, AUC, …) into one image"
        ),
        _tr(
            "<b>Batch Download &amp; CSV Export:</b> Pull every selected date and export the table"
        ),
        _tr(
            "<b>Live Filtering:</b> Cloud %, SCL classes, AOI coverage, date selection and "
            "Savitzky-Golay smoothing — re-applied to the cached series with no new GEE call"
        ),
        _tr(
            "<b>Climate Overlay:</b> NASA POWER precipitation and temperature on the plot"
        ),
        _tr(
            "<b>Point &amp; Per-Feature Analysis:</b> Time series per clicked point or per polygon"
        ),
    ]:
        lay.addWidget(_para(f"✓  {text}"))

    lay.addWidget(_h2(_tr("☁️ Filtering (new)")))
    lay.addWidget(_divider())
    lay.addWidget(
        _para(
            _tr(
                "Filtering no longer happens when the collection runs. Every image keeps "
                "its cloud, SCL and coverage metadata, so the <b>Adjust filter</b> button "
                "on the Results tab re-filters and re-plots the series instantly, without "
                "contacting Earth Engine again."
            )
        )
    )

    lay.addWidget(_h2(_tr("🔧 Initial Setup")))
    lay.addWidget(_divider())
    lay.addWidget(
        _para(
            _tr(
                "To use this module you need authentication to Google Earth Engine via a "
                '<b>Google Cloud Project ID</b>. Configure this in the "Auth" tab.'
            )
        )
    )

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

    dialog.s2_layer_combo = QgsMapLayerComboBox()
    dialog.s2_layer_combo.setFilters(QgsMapLayerProxyModel.VectorLayer)
    _prepare_field(dialog.s2_layer_combo)
    dialog.s2_layer_combo.setAllowEmptyLayer(True)
    dialog.s2_layer_combo.view().setStyleSheet(_POPUP_VIEW_STYLE)
    aoi_row_lay.addWidget(dialog.s2_layer_combo, 1)

    dialog.s2_btn_draw_aoi = QPushButton(_tr("Draw AOI"))
    dialog.s2_btn_draw_aoi.setToolTip(
        _tr("Drag on the map to draw a box (Shift = square, Esc = cancel)")
    )
    dialog.s2_btn_draw_aoi.setFixedHeight(28)
    dialog.s2_btn_draw_aoi.setSizePolicy(
        QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed
    )
    dialog.s2_btn_draw_aoi.adjustSize()
    dialog.s2_btn_draw_aoi.setStyleSheet(STYLE_BTN_SECONDARY)
    aoi_row_lay.addWidget(dialog.s2_btn_draw_aoi)

    dialog.s2_btn_hybrid_layer = QPushButton(_tr("Add Google Hybrid Layer"))
    dialog.s2_btn_hybrid_layer.setFixedHeight(28)
    dialog.s2_btn_hybrid_layer.setSizePolicy(
        QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed
    )
    dialog.s2_btn_hybrid_layer.adjustSize()
    dialog.s2_btn_hybrid_layer.setStyleSheet(STYLE_BTN_SECONDARY)
    aoi_row_lay.addWidget(dialog.s2_btn_hybrid_layer)

    inputs_lay.addWidget(aoi_row)
    inputs_lay.addSpacing(6)

    fields_grid = QGridLayout()
    fields_grid.setContentsMargins(0, 0, 0, 0)
    fields_grid.setHorizontalSpacing(16)
    fields_grid.setVerticalSpacing(8)
    fields_grid.setColumnStretch(0, 1)
    fields_grid.setColumnStretch(1, 1)

    dialog.s2_date_start = QDateEdit()
    dialog.s2_date_start.setDisplayFormat("yyyy-MM-dd")
    dialog.s2_date_start.setCalendarPopup(True)
    dialog.s2_date_start.setDate(QDate.currentDate().addYears(-1))
    _prepare_field(dialog.s2_date_start)
    dialog.s2_date_end = QDateEdit()
    dialog.s2_date_end.setDisplayFormat("yyyy-MM-dd")
    dialog.s2_date_end.setCalendarPopup(True)
    dialog.s2_date_end.setDate(QDate.currentDate())
    _prepare_field(dialog.s2_date_end)
    for _cal in (
        dialog.s2_date_start.calendarWidget(),
        dialog.s2_date_end.calendarWidget(),
    ):
        if _cal is not None:
            _cal.setStyleSheet(_CALENDAR_STYLE)

    fields_grid.addWidget(_field_label(_tr("START DATE")), 0, 0)
    fields_grid.addWidget(_field_label(_tr("END DATE")), 0, 1)
    fields_grid.addWidget(dialog.s2_date_start, 1, 0)
    fields_grid.addWidget(dialog.s2_date_end, 1, 1)
    inputs_lay.addLayout(fields_grid)

    lay.addWidget(inputs_panel)

    # --- Vegetation index ------------------------------------------------
    index_panel = _section_panel()
    index_lay = QVBoxLayout(index_panel)
    index_lay.setContentsMargins(16, 14, 16, 14)
    index_lay.setSpacing(10)

    index_lay.addWidget(_field_label(_tr("VEGETATION INDEX")))

    dialog.s2_index_combo = QComboBox()
    for name in INDEX_ORDER:
        dialog.s2_index_combo.addItem(name, name)
    dialog.s2_index_combo.addItem(_tr(CUSTOM_INDEX_LABEL), CUSTOM_INDEX_LABEL)
    dialog.s2_index_combo.setCurrentText("NDVI")
    _prepare_field(dialog.s2_index_combo)
    dialog.s2_index_combo.view().setStyleSheet(_POPUP_VIEW_STYLE)
    index_lay.addWidget(dialog.s2_index_combo)

    dialog.s2_index_info = QLabel()
    dialog.s2_index_info.setWordWrap(True)
    dialog.s2_index_info.setTextFormat(Qt.TextFormat.RichText)
    dialog.s2_index_info.setStyleSheet(
        "color: #4a5650; font-size: 11px; background: #f0f8ff;"
        " border: 1px solid #d6e4ef; border-radius: 6px; padding: 8px;"
    )
    index_lay.addWidget(dialog.s2_index_info)

    # --- Inline custom-index builder (hidden unless Custom… selected) ----
    dialog.s2_custom_container = QWidget()
    dialog.s2_custom_container.setStyleSheet("background: transparent;")
    custom_lay = QVBoxLayout(dialog.s2_custom_container)
    custom_lay.setContentsMargins(0, 4, 0, 0)
    custom_lay.setSpacing(8)

    custom_lay.addWidget(_make_divider())

    name_row = QGridLayout()
    name_row.setContentsMargins(0, 0, 0, 0)
    name_row.setHorizontalSpacing(16)
    name_row.setColumnStretch(0, 1)
    name_row.setColumnStretch(1, 2)
    name_row.addWidget(_field_label(_tr("INDEX NAME")), 0, 0)
    name_row.addWidget(_field_label(_tr("EXPRESSION")), 0, 1)
    dialog.s2_custom_name = QLineEdit()
    dialog.s2_custom_name.setPlaceholderText(_tr("My Index"))
    _prepare_field(dialog.s2_custom_name, 28)
    dialog.s2_custom_expression = QLineEdit()
    dialog.s2_custom_expression.setPlaceholderText("(B8 - B4) / (B8 + B4)")
    _prepare_field(dialog.s2_custom_expression, 28)
    name_row.addWidget(dialog.s2_custom_name, 1, 0)
    name_row.addWidget(dialog.s2_custom_expression, 1, 1)
    custom_lay.addLayout(name_row)

    band_lines = "&nbsp;&nbsp;".join(
        f"<b>{code}</b> {desc}" for code, desc in CUSTOM_BAND_REFERENCE
    )
    band_ref = QLabel(
        _tr("Use these band names in the expression:") + "<br>" + band_lines
    )
    band_ref.setWordWrap(True)
    band_ref.setTextFormat(Qt.TextFormat.RichText)
    band_ref.setStyleSheet(
        "color: #757575; font-size: 10px; background: transparent; border: none;"
    )
    custom_lay.addWidget(band_ref)

    expr_help = QLabel(
        _tr(
            "<b>How to build an expression</b><br>"
            "Combine band names with operators. Bands are scaled to 0–1 reflectance."
            "<br>"
            "&bull; Arithmetic: <b>+ &minus; * /</b> &nbsp; power <b>**</b> &nbsp; "
            "grouping <b>( )</b><br>"
            "&bull; Math functions: <b>sqrt() abs() exp() log() pow(x, y) "
            "min(a, b) max(a, b)</b><br>"
            "&bull; Compare: <b>&lt; &lt;= &gt; &gt;= == !=</b> &nbsp; "
            "logic <b>&amp;&amp; || !</b><br>"
            "&bull; Conditional: <b>condition ? value_if_true : value_if_false</b>"
            "<br><br>"
            "<b>Examples</b><br>"
            "&bull; NDVI: <code>(B8 - B4) / (B8 + B4)</code><br>"
            "&bull; SAVI: <code>1.5 * (B8 - B4) / (B8 + B4 + 0.5)</code><br>"
            "&bull; Mask low NIR: <code>B8 > 0.2 ? (B8 - B4) / (B8 + B4) : 0</code>"
        )
    )
    expr_help.setWordWrap(True)
    expr_help.setTextFormat(Qt.TextFormat.RichText)
    expr_help.setStyleSheet(
        "color: #4a5650; font-size: 10px; background: #f7faf7;"
        " border: 1px solid #dde7dd; border-radius: 6px; padding: 8px;"
    )
    custom_lay.addWidget(expr_help)

    dialog.s2_btn_custom_save = QPushButton(_tr("Save custom index"))
    dialog.s2_btn_custom_save.setFixedHeight(28)
    dialog.s2_btn_custom_save.setStyleSheet(STYLE_BTN_SECONDARY)
    dialog.s2_btn_custom_save.setSizePolicy(
        QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed
    )
    custom_lay.addWidget(dialog.s2_btn_custom_save, 0, Qt.AlignmentFlag.AlignLeft)

    index_lay.addWidget(dialog.s2_custom_container)
    lay.addWidget(index_panel)

    def _update_index_info(_idx=None):
        key = dialog.s2_index_combo.currentData()

        custom_saved = load_custom_indexes()

        if key == CUSTOM_INDEX_LABEL:
            dialog.s2_custom_container.setVisible(True)
            dialog.s2_index_info.setText(
                _tr(
                    "<b>Custom index.</b> Define a Sentinel-2 band expression below, "
                    "give it a name and save it. Reflectance bands are scaled to 0–1."
                )
            )
        elif key in custom_saved:
            dialog.s2_custom_container.setVisible(False)
            dialog.s2_index_info.setText(custom_saved[key])

        else:
            dialog.s2_custom_container.setVisible(False)
            dialog.s2_index_info.setText(VEGETATION_INDICES.get(key, ""))

    dialog.s2_index_combo.currentIndexChanged.connect(_update_index_info)
    _update_index_info()

    # --- SCL cloud mask (applied at run time) ----------------------------
    # Masking SCL classes changes the pixels feeding the indices and the
    # downloaded imagery, so it must be chosen before the run — not in the
    # client-side filter popup (which only re-filters cached results).
    scl_panel = _section_panel()
    scl_lay = QVBoxLayout(scl_panel)
    scl_lay.setContentsMargins(16, 14, 16, 14)
    scl_lay.setSpacing(10)
    scl_lay.addWidget(_field_label(_tr("SCL CLOUD MASK")))

    dialog.s2_chk_apply_scl = QCheckBox(_tr("Apply Scene Classification (SCL) mask"))
    dialog.s2_chk_apply_scl.setChecked(True)
    dialog.s2_chk_apply_scl.setStyleSheet(STYLE_CHECKBOX)
    scl_lay.addWidget(dialog.s2_chk_apply_scl)

    scl_hint = QLabel(
        _tr(
            "Checked classes always define the valid-pixel count used by the Results "
            "filter. When the mask above is enabled, they are also masked out of "
            "every image before indices are computed, affecting the time series and "
            "downloaded rasters."
        )
    )
    scl_hint.setWordWrap(True)
    scl_hint.setStyleSheet(
        "color: #757575; font-size: 11px; background: transparent; border: none;"
    )
    scl_lay.addWidget(scl_hint)

    scl_grid = QGridLayout()
    scl_grid.setContentsMargins(0, 0, 0, 0)
    scl_grid.setHorizontalSpacing(14)
    scl_grid.setVerticalSpacing(6)
    dialog.s2_scl_checks = {}
    for idx, (cls, name, default_on) in enumerate(_SCL_CLASSES):
        chk = QCheckBox(f"{cls} — {_tr(name)}")
        chk.setChecked(default_on)
        chk.setStyleSheet(STYLE_CHECKBOX)
        dialog.s2_scl_checks[cls] = chk
        scl_grid.addWidget(chk, idx // 2, idx % 2)
    scl_grid_host = QWidget()
    scl_grid_host.setStyleSheet("background: transparent;")
    scl_grid_host.setLayout(scl_grid)
    scl_lay.addWidget(scl_grid_host)

    lay.addWidget(scl_panel)

    lay.addStretch(1)
    scroll.setWidget(scroll_w)
    outer.addWidget(scroll)


def _build_results_tab(dialog, parent):
    outer = QVBoxLayout(parent)
    outer.setContentsMargins(0, 0, 0, 0)
    outer.setSpacing(0)

    dialog.s2_results_splitter = QSplitter(Qt.Orientation.Vertical)
    dialog.s2_results_splitter.setChildrenCollapsible(False)
    dialog.s2_results_splitter.setHandleWidth(4)
    dialog.s2_results_splitter.setStyleSheet("""
        QSplitter::handle {
            background: transparent;
            margin: 0px 6px;
            border-top: 2px solid #d6e0d9;
        }
        QSplitter::handle:hover { border-top-color: #1b6b39; }
    """)

    # Plot area: a segmented toggle (AOI / Points / Features) over the web view.
    # All three views share this one plot space; the controller swaps the chart
    # and enables a segment only once that view has data.
    plot_container = QWidget()
    plot_container.setStyleSheet("background: transparent;")
    plot_lay = QVBoxLayout(plot_container)
    plot_lay.setContentsMargins(0, 0, 0, 0)
    plot_lay.setSpacing(6)

    seg_bar = QFrame()
    dialog.s2_plot_view_bar = seg_bar
    seg_bar.setStyleSheet("background: transparent; border: none;")
    seg_lay = QHBoxLayout(seg_bar)
    seg_lay.setContentsMargins(0, 0, 0, 0)
    seg_lay.setSpacing(0)

    dialog.s2_plot_view_aoi = QPushButton(_tr("AOI"))
    dialog.s2_plot_view_points = QPushButton(_tr("Points"))
    dialog.s2_plot_view_features = QPushButton(_tr("Features"))
    dialog.s2_plot_view_buttons = (
        dialog.s2_plot_view_aoi,
        dialog.s2_plot_view_points,
        dialog.s2_plot_view_features,
    )
    for _i, _seg in enumerate(dialog.s2_plot_view_buttons):
        _seg.setCheckable(True)
        _seg.setFixedHeight(26)
        _seg.setCursor(Qt.CursorShape.PointingHandCursor)
        _seg.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        # Round the outer corners of the first/last segment only, so the three
        # buttons read as one joined control.
        if _i == 0:
            radius = "border-top-left-radius: 6px; border-bottom-left-radius: 6px;"
        elif _i == len(dialog.s2_plot_view_buttons) - 1:
            radius = "border-top-right-radius: 6px; border-bottom-right-radius: 6px;"
        else:
            radius = ""
        _seg.setStyleSheet(_SEGMENT_STYLE % radius)
        seg_lay.addWidget(_seg)
    seg_lay.addStretch(1)

    dialog.s2_plot_view_aoi.setChecked(True)
    # Points / Features views unlock once their series exist (the controller
    # enables them in _update_view_buttons).
    dialog.s2_plot_view_points.setEnabled(False)
    dialog.s2_plot_view_features.setEnabled(False)
    # Toggle bar stays hidden until Points/Features series exist (controller
    # reveals it in _update_view_buttons).
    seg_bar.setVisible(False)
    plot_lay.addWidget(seg_bar)

    dialog.s2_web_view = QWebView()
    dialog.s2_web_view.setStyleSheet(
        "border: 1px solid #dce6df; border-radius: 8px; background: #ffffff;"
    )
    dialog.s2_web_view.setMinimumHeight(200)
    plot_lay.addWidget(dialog.s2_web_view, 1)
    dialog.s2_results_splitter.addWidget(plot_container)

    scroll = QScrollArea()
    scroll.setWidgetResizable(True)
    scroll.setFrameShape(QFrame.Shape.NoFrame)
    scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
    scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
    scroll.setStyleSheet("QScrollArea { background: transparent; border: none; }")

    scroll_w = QWidget()
    scroll_w.setStyleSheet("background: transparent;")
    lay = QVBoxLayout(scroll_w)
    lay.setContentsMargins(6, 0, 6, 14)
    lay.setSpacing(12)

    # --- Time series controls -------------------------------------------
    ts_panel = _section_panel()
    ts_lay = QVBoxLayout(ts_panel)
    ts_lay.setContentsMargins(16, 14, 16, 14)
    ts_lay.setSpacing(10)
    ts_lay.addWidget(_caption(_tr("TIME SERIES")))

    dialog.s2_btn_adjust_filter = QPushButton(_tr("Adjust filter"))
    dialog.s2_btn_adjust_filter.setFixedHeight(30)
    dialog.s2_btn_adjust_filter.setStyleSheet(STYLE_BTN_SECONDARY)
    dialog.s2_btn_filter_dates = QPushButton(_tr("Filter dates"))
    dialog.s2_btn_filter_dates.setFixedHeight(30)
    dialog.s2_btn_filter_dates.setStyleSheet(STYLE_BTN_SECONDARY)
    dialog.s2_btn_open_browser = QPushButton(_tr("Open in Browser"))
    dialog.s2_btn_open_browser.setFixedHeight(30)
    dialog.s2_btn_open_browser.setStyleSheet(STYLE_BTN_SECONDARY)
    dialog.s2_btn_download_csv = QPushButton(_tr("Export CSV"))
    dialog.s2_btn_download_csv.setFixedHeight(30)
    dialog.s2_btn_download_csv.setStyleSheet(STYLE_BTN_SECONDARY)
    dialog.s2_btn_batch_download = QPushButton(_tr("Batch Download (All Dates)"))
    dialog.s2_btn_batch_download.setFixedHeight(30)
    dialog.s2_btn_batch_download.setStyleSheet(STYLE_BTN_SECONDARY)
    ts_lay.addWidget(
        _flow(
            [
                dialog.s2_btn_adjust_filter,
                dialog.s2_btn_filter_dates,
                dialog.s2_btn_open_browser,
                dialog.s2_btn_download_csv,
                dialog.s2_btn_batch_download,
            ]
        )
    )

    ts_lay.addWidget(_make_divider())

    # Savitzky-Golay smoothing acts on the already-computed series, so it lives
    # with the time-series controls (a render-time tweak, not a GEE filter). The
    # window / poly-order spinboxes appear inline once smoothing is enabled.
    dialog.s2_chk_smoothing = QCheckBox(_tr("Savitzky-Golay smoothing"))
    dialog.s2_chk_smoothing.setStyleSheet(STYLE_CHECKBOX)

    def _spin_widget(spinbox, height=30):
        try:
            spinbox.setButtonSymbols(QAbstractSpinBox.ButtonSymbols.NoButtons)
        except AttributeError:
            spinbox.setButtonSymbols(QAbstractSpinBox.NoButtons)  # type: ignore[attr-defined]
        spinbox.setStyleSheet(
            "QSpinBox {"
            " background: #ffffff; color: #1a1a1a;"
            " border-top: 1.5px solid #b8dcc8; border-bottom: 1.5px solid #b8dcc8;"
            " border-left: none; border-right: none; border-radius: 0px;"
            " padding: 0px 4px; font-size: 13px; font-weight: 600; min-width: 36px;"
            "}"
        )
        spinbox.setAlignment(Qt.AlignmentFlag.AlignCenter)
        spinbox.setFixedHeight(height)

        _btn_base = (
            " background-color: #edf7f1; color: #1b6b39;"
            " font-size: 16px; font-weight: 600;"
            " min-width: 26px; max-width: 26px; padding: 0px;"
        )
        btn_m = QPushButton("−")
        btn_p = QPushButton("+")
        btn_m.setStyleSheet(
            "QPushButton {"
            + _btn_base
            + " border: 1.5px solid #b8dcc8; border-right: 1px solid #d4e8dc;"
            " border-top-left-radius: 6px; border-bottom-left-radius: 6px;"
            " border-top-right-radius: 0px; border-bottom-right-radius: 0px; }"
            " QPushButton:hover { background-color: #c5e8d0; border-color: #1b6b39; }"
            " QPushButton:pressed { background-color: #1b6b39; color: #ffffff; border-color: #1b6b39; }"
        )
        btn_p.setStyleSheet(
            "QPushButton {"
            + _btn_base
            + " border: 1.5px solid #b8dcc8; border-left: 1px solid #d4e8dc;"
            " border-top-right-radius: 6px; border-bottom-right-radius: 6px;"
            " border-top-left-radius: 0px; border-bottom-left-radius: 0px; }"
            " QPushButton:hover { background-color: #c5e8d0; border-color: #1b6b39; }"
            " QPushButton:pressed { background-color: #1b6b39; color: #ffffff; border-color: #1b6b39; }"
        )
        for b in (btn_m, btn_p):
            b.setFixedHeight(height)
            b.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        btn_m.clicked.connect(spinbox.stepDown)
        btn_p.clicked.connect(spinbox.stepUp)
        wrap = QWidget()
        wrap.setStyleSheet("background: transparent; border: none;")
        wlay = QHBoxLayout(wrap)
        wlay.setContentsMargins(0, 0, 0, 0)
        wlay.setSpacing(0)
        wlay.addWidget(btn_m)
        wlay.addWidget(spinbox)
        wlay.addWidget(btn_p)
        wrap.setFixedHeight(height)
        return wrap

    dialog.s2_smooth_window = QSpinBox()
    dialog.s2_smooth_window.setRange(3, 99)
    dialog.s2_smooth_window.setSingleStep(2)
    dialog.s2_smooth_window.setValue(7)
    window_widget = _spin_widget(dialog.s2_smooth_window)
    window_widget.setMinimumWidth(84)
    dialog.s2_smooth_polyorder = QSpinBox()
    dialog.s2_smooth_polyorder.setRange(1, 10)
    dialog.s2_smooth_polyorder.setValue(2)
    polyorder_widget = _spin_widget(dialog.s2_smooth_polyorder)
    polyorder_widget.setMinimumWidth(84)

    # Window must stay odd and the polynomial order below it (valid SG).
    def _force_odd(v):
        if v % 2 == 0:
            dialog.s2_smooth_window.blockSignals(True)
            dialog.s2_smooth_window.setValue(v + 1 if v + 1 <= 99 else v - 1)
            dialog.s2_smooth_window.blockSignals(False)
        dialog.s2_smooth_polyorder.setMaximum(
            min(10, dialog.s2_smooth_window.value() - 1)
        )

    dialog.s2_smooth_window.valueChanged.connect(_force_odd)
    _force_odd(dialog.s2_smooth_window.value())

    # Group the params so they reveal/hide together with the checkbox.
    smooth_params = QWidget()
    smooth_params.setStyleSheet("background: transparent;")
    smooth_params_lay = QHBoxLayout(smooth_params)
    smooth_params_lay.setContentsMargins(0, 0, 0, 0)
    smooth_params_lay.setSpacing(12)
    smooth_params_lay.addWidget(_labeled(_tr("Window"), window_widget, 56))
    smooth_params_lay.addWidget(_labeled(_tr("Poly order"), polyorder_widget, 70))

    def _sync_smoothing():
        smooth_params.setVisible(dialog.s2_chk_smoothing.isChecked())

    dialog.s2_chk_smoothing.toggled.connect(lambda _v: _sync_smoothing())
    ts_lay.addWidget(
        _flow(
            [
                dialog.s2_chk_smoothing,
                smooth_params,
            ],
            spacing=12,
        )
    )
    _sync_smoothing()
    lay.addWidget(ts_panel)

    # --- Single-date image (shared date; RGB or VI output) --------------
    single_panel = _section_panel()
    single_lay = QVBoxLayout(single_panel)
    single_lay.setContentsMargins(16, 12, 16, 12)
    single_lay.setSpacing(6)
    single_lay.addWidget(_caption(_tr("SINGLE-DATE IMAGE")))

    dialog.s2_result_date_combo = QComboBox()
    _prepare_field(dialog.s2_result_date_combo, 30)
    dialog.s2_result_date_combo.setMinimumWidth(136)
    dialog.s2_result_date_combo.setSizeAdjustPolicy(
        QComboBox.SizeAdjustPolicy.AdjustToContents
    )
    dialog.s2_result_date_combo.view().setStyleSheet(_POPUP_VIEW_STYLE)

    def _subrow(title, widgets):
        """A light inner card: an inline caption followed by the controls and
        per-output download buttons, all on one wrapping row."""
        frame = QFrame()
        frame.setStyleSheet(
            "QFrame { background: #fbfcfb; border: 1px solid #e8eee9;"
            " border-radius: 6px; }"
            "QLabel { background: transparent; border: none; }"
        )
        box = QVBoxLayout(frame)
        box.setContentsMargins(10, 6, 10, 6)
        box.setSpacing(0)
        cap = QLabel(title)
        cap.setStyleSheet(
            "color: #1b6b39; font-size: 10px; font-weight: bold; letter-spacing: 1px;"
        )
        box.addWidget(_flow([cap, *widgets], spacing=10))
        return frame

    # Shared date selector for both single-date outputs.
    single_lay.addWidget(_labeled(_tr("Date"), dialog.s2_result_date_combo, 34))

    # --- Multispectral (RGB) ---
    dialog.s2_rgb_render_combo = QComboBox()
    _prepare_field(dialog.s2_rgb_render_combo, 30)
    dialog.s2_rgb_render_combo.setMinimumWidth(200)
    dialog.s2_rgb_render_combo.setSizeAdjustPolicy(
        QComboBox.SizeAdjustPolicy.AdjustToContents
    )
    for _label, _key in _RGB_RENDER_MODES:
        dialog.s2_rgb_render_combo.addItem(_label, _key)
    dialog.s2_rgb_render_combo.view().setStyleSheet(_POPUP_VIEW_STYLE)
    dialog.s2_btn_rgb_preview = QPushButton(_tr("Preview"))
    dialog.s2_btn_rgb_preview.setFixedHeight(30)
    dialog.s2_btn_rgb_preview.setStyleSheet(STYLE_BTN_PRIMARY)
    dialog.s2_btn_rgb_download = QPushButton(
        _tr("Download & Preview").replace("&", "&&")
    )
    dialog.s2_btn_rgb_download.setFixedHeight(30)
    dialog.s2_btn_rgb_download.setStyleSheet(STYLE_BTN_SECONDARY)
    single_lay.addWidget(
        _subrow(
            _tr("RGB"),
            [
                _labeled(_tr("Rendering"), dialog.s2_rgb_render_combo, 70),
                dialog.s2_btn_rgb_preview,
                dialog.s2_btn_rgb_download,
            ],
        )
    )

    # --- Vegetation index ---
    dialog.s2_vi_index_combo = QComboBox()
    _prepare_field(dialog.s2_vi_index_combo, 30)
    dialog.s2_vi_index_combo.setMinimumWidth(76)
    dialog.s2_vi_index_combo.setSizeAdjustPolicy(
        QComboBox.SizeAdjustPolicy.AdjustToContents
    )
    for name in INDEX_ORDER:
        dialog.s2_vi_index_combo.addItem(name, name)
    dialog.s2_vi_index_combo.view().setStyleSheet(_POPUP_VIEW_STYLE)
    dialog.s2_vi_ramp_combo = QComboBox()
    _prepare_field(dialog.s2_vi_ramp_combo, 30)
    dialog.s2_vi_ramp_combo.setMinimumWidth(90)
    dialog.s2_vi_ramp_combo.setSizeAdjustPolicy(
        QComboBox.SizeAdjustPolicy.AdjustToContents
    )
    dialog.s2_vi_ramp_combo.addItems(_COLOR_RAMPS)
    dialog.s2_vi_ramp_combo.setCurrentText("RdYlGn")
    dialog.s2_vi_ramp_combo.view().setStyleSheet(_POPUP_VIEW_STYLE)
    dialog.s2_btn_vi_preview = QPushButton(_tr("Preview"))
    dialog.s2_btn_vi_preview.setFixedHeight(30)
    dialog.s2_btn_vi_preview.setStyleSheet(STYLE_BTN_PRIMARY)
    dialog.s2_btn_vi_download = QPushButton(
        _tr("Download & Preview").replace("&", "&&")
    )
    dialog.s2_btn_vi_download.setFixedHeight(30)
    dialog.s2_btn_vi_download.setStyleSheet(STYLE_BTN_SECONDARY)
    single_lay.addWidget(
        _subrow(
            _tr("INDEX"),
            [
                _labeled(_tr("Index"), dialog.s2_vi_index_combo, 44),
                _labeled(_tr("Color Ramp"), dialog.s2_vi_ramp_combo, 80),
                dialog.s2_btn_vi_preview,
                dialog.s2_btn_vi_download,
            ],
        )
    )

    lay.addWidget(single_panel)

    # --- Synthetic composite --------------------------------------------
    composite_panel = _section_panel()
    composite_lay = QVBoxLayout(composite_panel)
    composite_lay.setContentsMargins(16, 14, 16, 14)
    composite_lay.setSpacing(10)
    composite_lay.addWidget(_caption(_tr("SYNTHETIC IMAGE (COMPOSITE)")))
    composite_hint = QLabel(
        _tr("Composite a vegetation index over the selected dates.")
    )
    composite_hint.setWordWrap(True)
    composite_hint.setStyleSheet(
        "color: #616161; font-size: 11px; background: transparent; border: none;"
    )
    composite_lay.addWidget(composite_hint)

    dialog.s2_composite_index_combo = QComboBox()
    _prepare_field(dialog.s2_composite_index_combo, 30)
    dialog.s2_composite_index_combo.setMinimumWidth(76)
    dialog.s2_composite_index_combo.setSizeAdjustPolicy(
        QComboBox.SizeAdjustPolicy.AdjustToContents
    )
    for name in INDEX_ORDER:
        dialog.s2_composite_index_combo.addItem(name, name)
    dialog.s2_composite_index_combo.view().setStyleSheet(_POPUP_VIEW_STYLE)

    dialog.s2_composite_metric_combo = QComboBox()
    _prepare_field(dialog.s2_composite_metric_combo, 30)
    dialog.s2_composite_metric_combo.setMinimumWidth(200)
    dialog.s2_composite_metric_combo.setSizeAdjustPolicy(
        QComboBox.SizeAdjustPolicy.AdjustToContents
    )
    for _metric_key in _COMPOSITE_METRICS:
        dialog.s2_composite_metric_combo.addItem(_tr(_metric_key), _metric_key)
    dialog.s2_composite_metric_combo.view().setStyleSheet(_POPUP_VIEW_STYLE)

    dialog.s2_composite_ramp_combo = QComboBox()
    _prepare_field(dialog.s2_composite_ramp_combo, 30)
    dialog.s2_composite_ramp_combo.setMinimumWidth(200)
    dialog.s2_composite_ramp_combo.setSizeAdjustPolicy(
        QComboBox.SizeAdjustPolicy.AdjustToContents
    )
    dialog.s2_composite_ramp_combo.addItems(_COLOR_RAMPS)
    dialog.s2_composite_ramp_combo.setCurrentText("RdYlGn")
    dialog.s2_composite_ramp_combo.view().setStyleSheet(_POPUP_VIEW_STYLE)

    dialog.s2_btn_composite_preview = QPushButton(_tr("Preview Composite"))
    dialog.s2_btn_composite_preview.setFixedHeight(30)
    dialog.s2_btn_composite_preview.setStyleSheet(STYLE_BTN_PRIMARY)
    dialog.s2_btn_composite_download = QPushButton(
        _tr("Download & Preview").replace("&", "&&")
    )
    dialog.s2_btn_composite_download.setFixedHeight(30)
    dialog.s2_btn_composite_download.setStyleSheet(STYLE_BTN_SECONDARY)
    composite_lay.addWidget(
        _flow(
            [
                _labeled(_tr("Index"), dialog.s2_composite_index_combo, 44),
                _labeled(_tr("Metric"), dialog.s2_composite_metric_combo, 80),
                _labeled(_tr("Color Ramp"), dialog.s2_composite_ramp_combo, 80),
                dialog.s2_btn_composite_preview,
                dialog.s2_btn_composite_download,
            ],
            spacing=12,
        )
    )
    lay.addWidget(composite_panel)

    # --- Climate (NASA POWER) -------------------------------------------
    climate_panel = _section_panel()
    climate_lay = QVBoxLayout(climate_panel)
    climate_lay.setContentsMargins(16, 14, 16, 14)
    climate_lay.setSpacing(10)
    climate_lay.addWidget(_caption(_tr("CLIMATE (NASA POWER)")))
    climate_hint = QLabel(
        _tr(
            "Overlay accumulated monthly precipitation (NASA POWER) as bars on the "
            "time-series plot, over the same date range. Temperature is fetched too "
            "and included in the CSV export."
        )
    )
    climate_hint.setWordWrap(True)
    climate_hint.setStyleSheet(
        "color: #616161; font-size: 11px; background: transparent; border: none;"
    )
    climate_lay.addWidget(climate_hint)

    dialog.s2_btn_climate_overlay = QPushButton(_tr("Overlay on plot"))
    dialog.s2_btn_climate_overlay.setFixedHeight(30)
    dialog.s2_btn_climate_overlay.setStyleSheet(STYLE_BTN_PRIMARY)
    dialog.s2_btn_climate_save = QPushButton(_tr("Export CSV"))
    dialog.s2_btn_climate_save.setFixedHeight(30)
    dialog.s2_btn_climate_save.setStyleSheet(STYLE_BTN_SECONDARY)
    dialog.s2_btn_climate_clear = QPushButton(_tr("Clear"))
    dialog.s2_btn_climate_clear.setFixedHeight(30)
    dialog.s2_btn_climate_clear.setStyleSheet(STYLE_BTN_SECONDARY)
    climate_lay.addWidget(
        _flow(
            [
                dialog.s2_btn_climate_overlay,
                dialog.s2_btn_climate_save,
                dialog.s2_btn_climate_clear,
            ],
            spacing=12,
        )
    )
    lay.addWidget(climate_panel)

    # --- Point & per-feature analysis -----------------------------------
    feature_panel = _section_panel()
    feature_lay = QVBoxLayout(feature_panel)
    feature_lay.setContentsMargins(16, 14, 16, 14)
    feature_lay.setSpacing(10)
    feature_lay.addWidget(_caption(_tr("POINT & FEATURE ANALYSIS")))
    feature_hint = QLabel(
        _tr(
            "Extract a time series per clicked map point, or one series per polygon "
            "feature of the AOI layer keyed by an attribute."
        )
    )
    feature_hint.setWordWrap(True)
    feature_hint.setStyleSheet(
        "color: #616161; font-size: 11px; background: transparent; border: none;"
    )
    feature_lay.addWidget(feature_hint)

    dialog.s2_btn_capture_points = QPushButton(_tr("Capture points on map"))
    dialog.s2_btn_capture_points.setCheckable(True)
    dialog.s2_btn_capture_points.setFixedHeight(30)
    dialog.s2_btn_capture_points.setStyleSheet(STYLE_BTN_SECONDARY)
    dialog.s2_btn_clear_points = QPushButton(_tr("Clear points"))
    dialog.s2_btn_clear_points.setFixedHeight(30)
    dialog.s2_btn_clear_points.setStyleSheet(STYLE_BTN_SECONDARY)

    dialog.s2_feature_id_combo = QComboBox()
    _prepare_field(dialog.s2_feature_id_combo, 30)
    dialog.s2_feature_id_combo.setMinimumWidth(140)
    dialog.s2_feature_id_combo.setSizeAdjustPolicy(
        QComboBox.SizeAdjustPolicy.AdjustToContents
    )
    dialog.s2_feature_id_combo.view().setStyleSheet(_POPUP_VIEW_STYLE)
    dialog.s2_btn_plot_features = QPushButton(_tr("Plot per-feature series"))
    dialog.s2_btn_plot_features.setFixedHeight(30)
    dialog.s2_btn_plot_features.setStyleSheet(STYLE_BTN_PRIMARY)

    feature_lay.addWidget(
        _flow(
            [
                dialog.s2_btn_capture_points,
                dialog.s2_btn_clear_points,
                _labeled(_tr("Feature ID"), dialog.s2_feature_id_combo, 70),
                dialog.s2_btn_plot_features,
            ],
            spacing=12,
        )
    )
    lay.addWidget(feature_panel)

    # --- Download buffer -------------------------------------------------
    buffer_panel = _section_panel()
    buffer_lay = QVBoxLayout(buffer_panel)
    buffer_lay.setContentsMargins(16, 14, 16, 14)
    buffer_lay.setSpacing(10)
    buffer_lay.addWidget(_caption(_tr("DOWNLOAD BUFFER")))
    buffer_hint = QLabel(
        _tr(
            "Use a positive buffer to include terrain just outside your area, or a "
            "negative buffer to crop the edges. Applies to every downloaded and "
            "previewed optical output (single date, batch, composite)."
        )
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
    dialog.s2_buffer_slider = QSlider(Qt.Orientation.Horizontal)
    dialog.s2_buffer_slider.setMinimum(-300)
    dialog.s2_buffer_slider.setMaximum(300)
    dialog.s2_buffer_slider.setSingleStep(1)
    dialog.s2_buffer_slider.setPageStep(10)
    dialog.s2_buffer_slider.setValue(0)
    dialog.s2_buffer_slider.setStyleSheet(_SLIDER_STYLE)
    buffer_row.addWidget(dialog.s2_buffer_slider, 1)
    plus_lbl = QLabel("+300 m")
    plus_lbl.setStyleSheet(
        "color: #9e9e9e; font-size: 9px; background: transparent; border: none;"
    )
    buffer_row.addWidget(plus_lbl)
    buffer_lay.addLayout(buffer_row)

    dialog.s2_buffer_value = QLabel(_tr("Buffer: 0 m"))
    dialog.s2_buffer_value.setAlignment(Qt.AlignmentFlag.AlignCenter)
    dialog.s2_buffer_value.setStyleSheet(
        "color: #616161; font-size: 10px; background: transparent; border: none;"
    )
    buffer_lay.addWidget(dialog.s2_buffer_value)

    def _set_s2_buffer_value(value):
        value = 0 if -3 <= value <= 3 else value
        if dialog.s2_buffer_slider.value() != value:
            dialog.s2_buffer_slider.blockSignals(True)
            dialog.s2_buffer_slider.setValue(value)
            dialog.s2_buffer_slider.blockSignals(False)
        dialog.s2_buffer_value.setText(
            _tr("Buffer: %+d m") % value if value != 0 else _tr("Buffer: 0 m")
        )

    dialog.s2_buffer_slider.valueChanged.connect(_set_s2_buffer_value)
    lay.addWidget(buffer_panel)
    lay.addStretch(1)

    # Mouse-driven buttons: drop from the focus chain so disabling one mid-run
    # does not show a stray focus ring on the next (same as SAR).
    for _btn in scroll_w.findChildren(QPushButton):
        _btn.setFocusPolicy(Qt.FocusPolicy.NoFocus)

    scroll.setWidget(scroll_w)
    dialog.s2_results_splitter.addWidget(scroll)
    dialog.s2_results_splitter.setStretchFactor(0, 1)
    dialog.s2_results_splitter.setStretchFactor(1, 0)
    outer.addWidget(dialog.s2_results_splitter)


def _wire_filter_dialog(dialog):
    """Attach the lazy openers for the client-side filter popup and the per-date
    selection dialog.

    The filter popup shows a live image count while the sliders move
    (``optical_filter_count_fn``), but only applies to the plot on OK, via
    ``on_optical_filter_applied`` (both set by the controller).
    """
    dialog.s2_filter_settings = None
    dialog.s2_active_dates = None

    def _open_filter():
        popup = OpticalFilterDialog(
            settings=dialog.s2_filter_settings,
            count_fn=getattr(dialog, "optical_filter_count_fn", None),
            parent=dialog,
        )
        if popup.exec():
            settings = popup.get_settings()
            dialog.s2_filter_settings = settings
            hook = getattr(dialog, "on_optical_filter_applied", None)
            if hook is not None:
                hook(settings)

    # The "Filter dates" button is wired to OpticalCtrl.handle_filter_dates in
    # farm_tools.py (it owns the active-date state and re-renders the plot).
    dialog.open_optical_filter_dialog = _open_filter
    dialog.s2_btn_adjust_filter.clicked.connect(_open_filter)


def setup_optical_page(dialog, page):
    """
    Populate the Optical (Sentinel-2) page with a three-tab layout.

    Exposes on dialog (selected):
      s2_layer_combo, s2_btn_draw_aoi, s2_btn_hybrid_layer,
      s2_date_start, s2_date_end, s2_index_combo, s2_index_info,
      s2_custom_container, s2_custom_name, s2_custom_expression, s2_btn_custom_save,
      s2_web_view, s2_btn_adjust_filter, s2_btn_filter_dates, s2_btn_open_browser,
      s2_btn_download_csv, s2_btn_batch_download,
      s2_chk_smoothing, s2_smooth_window, s2_smooth_polyorder,
      s2_result_date_combo,
      s2_rgb_render_combo, s2_btn_rgb_preview, s2_btn_rgb_download,
      s2_vi_index_combo, s2_vi_ramp_combo, s2_btn_vi_preview, s2_btn_vi_download,
      s2_composite_metric_combo, s2_composite_ramp_combo,
      s2_btn_composite_preview, s2_btn_composite_download,
      s2_btn_climate_overlay, s2_btn_climate_save, s2_btn_climate_clear,
      s2_btn_capture_points, s2_btn_clear_points, s2_feature_id_combo,
      s2_btn_plot_features, s2_buffer_slider, s2_buffer_value,
      s2_stack, s2_set_tab, s2_btn_back, s2_btn_run, s2_step_lbl,
      open_optical_filter_dialog, open_optical_date_filter,
      s2_filter_settings, s2_active_dates
    """
    page.setObjectName("opticalPage")
    page.setStyleSheet("""
        QWidget#opticalPage { background-color: #ffffff; }
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
        QLineEdit {
            background-color: #ffffff;
            color: #212121;
            border: 1px solid #d0d0d0;
            border-radius: 6px;
            padding: 4px 8px;
            font-size: 12px;
        }
        QLineEdit:focus { border: 1.5px solid #1b6b39; }
        QDateEdit {
            background-color: #ffffff;
            color: #212121;
            border: 1px solid #d0d0d0;
            border-radius: 6px;
            padding: 2px 4px 2px 8px;
            font-size: 12px;
        }
        QDateEdit:focus { border: 1.5px solid #1b6b39; }
        QSpinBox {
            background-color: #ffffff;
            color: #212121;
            border: 1px solid #d0d0d0;
            border-radius: 6px;
            padding: 2px 24px 2px 6px;
            font-size: 12px;
        }
        QSpinBox:focus { border: 1.5px solid #1b6b39; }
        QSpinBox:disabled { color: #bdbdbd; background: #f2f2f2; border-color: #e6e6e6; }
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
    tab_bar.setObjectName("opticalTabBar")
    tab_bar.setFixedHeight(40)
    tab_bar.setStyleSheet("""
        QFrame#opticalTabBar {
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
    dialog.s2_stack = stack

    nav_bar = QFrame()
    nav_bar.setObjectName("opticalNavBar")
    nav_bar.setFixedHeight(46)
    nav_bar.setStyleSheet("""
        QFrame#opticalNavBar {
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

    dialog.s2_btn_back = btn_back
    dialog.s2_btn_run = btn_run
    dialog.s2_step_lbl = step_lbl

    def _set_tab(index):
        stack.setCurrentIndex(index)
        btn_back.setEnabled(index > 0)
        step_lbl.setText(_tr("Step %d of 3") % (index + 1))
        btn_intro_next.setVisible(index == 0)
        btn_run.setVisible(index == 1)
        btn_tab_intro.setStyleSheet(_TAB_ACTIVE if index == 0 else _TAB_INACTIVE)
        btn_tab_inputs.setStyleSheet(_TAB_ACTIVE if index == 1 else _TAB_INACTIVE)
        btn_tab_results.setStyleSheet(_TAB_ACTIVE if index == 2 else _TAB_INACTIVE)

    dialog.s2_set_tab = _set_tab

    btn_tab_intro.clicked.connect(lambda: _set_tab(0))
    btn_tab_inputs.clicked.connect(lambda: _set_tab(1))
    btn_tab_results.clicked.connect(lambda: _set_tab(2))
    btn_intro_next.clicked.connect(lambda: _set_tab(1))
    btn_back.clicked.connect(
        lambda: _set_tab(stack.currentIndex() - 1) if stack.currentIndex() > 0 else None
    )

    _wire_filter_dialog(dialog)
    _set_tab(0)
