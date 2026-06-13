# -*- coding: utf-8 -*-
"""
MapBiomas page for the FARM tools dialog.

Three-tab layout (Inputs | Coverage | Transition). MapBiomas is browsed
*inside the module* (not loaded as QGIS layers), mirroring the FARM web app:

  • **Coverage** — the annual classification PNG for each year, browsed with a
    year slider, alongside the official class legend.
  • **Transition** — the Pasture→Crop first-transition-year PNG plus the
    per-year converted-area bar chart.

Signal connections are wired externally by ``farm_tools.py``.
"""

from qgis.core import QgsMapLayerProxyModel
from qgis.gui import QgsMapLayerComboBox
from qgis.PyQt.QtCore import QCoreApplication, Qt
from qgis.PyQt.QtWidgets import (
    QComboBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QProgressBar,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QSlider,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from .radar import (
    _POPUP_VIEW_STYLE,
    _SLIDER_STYLE,
    _TAB_ACTIVE,
    _TAB_INACTIVE,
    _field_label,
    _prepare_field,
    _section_panel,
)
from .range_slider import RangeSlider
from .styles import STYLE_BTN_PRIMARY, STYLE_BTN_SECONDARY, STYLE_COMBO_YEAR
from .webcompat import QWebView

from ..services.mapbiomas_service import (
    MAPBIOMAS_CLASS_LABELS,
    MAPBIOMAS_FIRST_YEAR,
    MAPBIOMAS_LATEST_YEAR,
    MAPBIOMAS_PALETTE,
    MAPBIOMAS_TRANSITION_FIRST_YEAR,
    MAPBIOMAS_TRANSITION_LAST_YEAR,
    MAPBIOMAS_TRANSITION_PRESETS,
)


def _tr(text):
    return QCoreApplication.translate("RAVI", text)


def _make_webview():
    view = QWebView()
    view.setFocusPolicy(Qt.FocusPolicy.NoFocus)
    view.setContextMenuPolicy(Qt.ContextMenuPolicy.NoContextMenu)
    view.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
    return view


def _progress_bar():
    """A hidden, thin progress bar for embedding inside a feature panel.

    Each loading feature (coverage / single-year download / transition) gets its
    own bar so the feedback shows up *in* the section that triggered it, rather
    than in one shared bar detached from the action.
    """
    bar = QProgressBar()
    bar.setRange(0, 100)
    bar.setValue(0)
    bar.setTextVisible(True)
    bar.setVisible(False)
    bar.setFixedHeight(16)
    bar.setStyleSheet(
        "QProgressBar { border: none; border-radius: 4px; background: #e0e0e0;"
        " font-size: 10px; color: #333; }"
        "QProgressBar::chunk { background: #1b6b39; border-radius: 4px; }"
    )
    return bar


def _image_label(placeholder):
    lbl = QLabel(placeholder)
    lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
    lbl.setWordWrap(True)
    lbl.setMinimumHeight(220)
    lbl.setStyleSheet(
        "color: #9e9e9e; font-size: 12px; background: #f5f7f6;"
        " border: 1px dashed #d0d5d2; border-radius: 8px;"
    )
    lbl.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
    return lbl


def _legend_html():
    """Static MapBiomas Collection 9 legend as rich-text swatch rows.

    QLabel rich text ignores sized ``inline-block`` spans, so the color cue is a
    colored ■ glyph (which Qt rich text does honor) followed by the class label;
    a two-column table keeps the labels aligned.
    """
    rows = [
        "<table cellspacing='0' cellpadding='2' "
        "style='font-size:11px;color:#333;'>"
    ]
    for class_id, label in MAPBIOMAS_CLASS_LABELS.items():
        hex_color = (
            MAPBIOMAS_PALETTE[class_id]
            if class_id < len(MAPBIOMAS_PALETTE)
            else "808080"
        )
        rows.append(
            "<tr>"
            f"<td><font size='4' color='#{hex_color}'>■</font></td>"
            f"<td>{label}</td>"
            "</tr>"
        )
    rows.append("</table>")
    return "".join(rows)


# --------------------------------------------------------------------- inputs
def _build_inputs_tab(dialog, parent):
    outer = QVBoxLayout(parent)
    outer.setContentsMargins(0, 0, 0, 0)
    outer.setSpacing(0)

    scroll = QScrollArea()
    scroll.setWidgetResizable(True)
    scroll.setFrameShape(QFrame.Shape.NoFrame)
    scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
    scroll.setStyleSheet("QScrollArea { background: transparent; border: none; }")

    scroll_w = QWidget()
    scroll_w.setStyleSheet("background: transparent;")
    lay = QVBoxLayout(scroll_w)
    lay.setContentsMargins(6, 16, 6, 14)
    lay.setSpacing(12)

    intro = QLabel(_tr(
        "Browse the <b>MapBiomas Brasil Collection 9</b> land-use / land-cover "
        "archive inside the module. Pick an AOI, then load the coverage years "
        "(browse them with the slider) or the Pasture→Crop transition. "
        "MapBiomas covers <b>Brazil only</b>."
    ))
    intro.setWordWrap(True)
    intro.setTextFormat(Qt.TextFormat.RichText)
    intro.setStyleSheet("color:#444; font-size:12px; background:transparent;")
    lay.addWidget(intro)

    # --- AOI -------------------------------------------------------------
    aoi_panel = _section_panel()
    aoi_lay = QVBoxLayout(aoi_panel)
    aoi_lay.setContentsMargins(16, 14, 16, 14)
    aoi_lay.setSpacing(10)
    aoi_lay.addWidget(_field_label(_tr("AOI LAYER")))

    aoi_row = QWidget()
    aoi_row_lay = QHBoxLayout(aoi_row)
    aoi_row_lay.setContentsMargins(0, 0, 0, 0)
    aoi_row_lay.setSpacing(6)

    dialog.mb_layer_combo = QgsMapLayerComboBox()
    dialog.mb_layer_combo.setFilters(QgsMapLayerProxyModel.VectorLayer)
    _prepare_field(dialog.mb_layer_combo)
    dialog.mb_layer_combo.setAllowEmptyLayer(True)
    dialog.mb_layer_combo.view().setStyleSheet(_POPUP_VIEW_STYLE)
    aoi_row_lay.addWidget(dialog.mb_layer_combo, 1)

    dialog.mb_btn_draw_aoi = QPushButton(_tr("Draw AOI"))
    dialog.mb_btn_draw_aoi.setToolTip(
        _tr("Drag on the map to draw a box (Shift = square, Esc = cancel)")
    )
    dialog.mb_btn_draw_aoi.setFixedHeight(28)
    dialog.mb_btn_draw_aoi.setSizePolicy(
        QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed
    )
    dialog.mb_btn_draw_aoi.adjustSize()
    dialog.mb_btn_draw_aoi.setStyleSheet(STYLE_BTN_SECONDARY)
    aoi_row_lay.addWidget(dialog.mb_btn_draw_aoi)

    dialog.mb_btn_hybrid_layer = QPushButton(_tr("Add Google Hybrid Layer"))
    dialog.mb_btn_hybrid_layer.setFixedHeight(28)
    dialog.mb_btn_hybrid_layer.setSizePolicy(
        QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed
    )
    dialog.mb_btn_hybrid_layer.adjustSize()
    dialog.mb_btn_hybrid_layer.setStyleSheet(STYLE_BTN_SECONDARY)
    aoi_row_lay.addWidget(dialog.mb_btn_hybrid_layer)

    aoi_lay.addWidget(aoi_row)
    lay.addWidget(aoi_panel)

    # --- Coverage --------------------------------------------------------
    cov_panel = _section_panel()
    cov_lay = QVBoxLayout(cov_panel)
    cov_lay.setContentsMargins(16, 14, 16, 14)
    cov_lay.setSpacing(10)
    cov_lay.addWidget(_field_label(_tr("COVERAGE")))

    cov_note = QLabel(_tr(
        "Renders all years (1985–2023) so you can browse them with the slider — "
        "this takes a moment."
    ))
    cov_note.setWordWrap(True)
    cov_note.setStyleSheet("color:#757575; font-size:11px; background:transparent;")
    cov_lay.addWidget(cov_note)

    dialog.mb_btn_load_coverage = QPushButton(_tr("Load coverage"))
    dialog.mb_btn_load_coverage.setFixedHeight(32)
    dialog.mb_btn_load_coverage.setStyleSheet(STYLE_BTN_PRIMARY)
    dialog.mb_btn_load_coverage.setToolTip(
        _tr("Render every MapBiomas year and browse them with the slider")
    )
    cov_lay.addWidget(dialog.mb_btn_load_coverage)

    dialog.mb_cov_progress = _progress_bar()
    cov_lay.addWidget(dialog.mb_cov_progress)
    lay.addWidget(cov_panel)

    # --- Quick single-year download -------------------------------------
    dl_panel = _section_panel()
    dl_lay = QVBoxLayout(dl_panel)
    dl_lay.setContentsMargins(16, 14, 16, 14)
    dl_lay.setSpacing(10)
    dl_lay.addWidget(_field_label(_tr("DOWNLOAD A SINGLE YEAR TO QGIS")))

    dl_note = QLabel(_tr(
        "Just need one year? Download that year's classification straight into "
        "QGIS as a styled raster layer — no need to render every year first."
    ))
    dl_note.setWordWrap(True)
    dl_note.setStyleSheet("color:#757575; font-size:11px; background:transparent;")
    dl_lay.addWidget(dl_note)

    dl_row = QHBoxLayout()
    dl_row.setSpacing(8)
    dl_year_lbl = QLabel(_tr("Year"))
    dl_year_lbl.setStyleSheet(
        "color:#616161; font-size:12px; font-weight:bold;"
        " background:transparent; border:none;"
    )
    dl_row.addWidget(dl_year_lbl)
    dialog.mb_dl_year_combo = QComboBox()
    for year in range(MAPBIOMAS_LATEST_YEAR, MAPBIOMAS_FIRST_YEAR - 1, -1):
        dialog.mb_dl_year_combo.addItem(str(year), year)
    dialog.mb_dl_year_combo.setCursor(Qt.CursorShape.PointingHandCursor)
    dialog.mb_dl_year_combo.setMinimumHeight(30)
    dialog.mb_dl_year_combo.setMaxVisibleItems(12)
    dialog.mb_dl_year_combo.setStyleSheet(STYLE_COMBO_YEAR)
    dl_row.addWidget(dialog.mb_dl_year_combo, 1)

    dialog.mb_btn_download_year = QPushButton(_tr("Download to QGIS"))
    dialog.mb_btn_download_year.setFixedHeight(28)
    dialog.mb_btn_download_year.setStyleSheet(STYLE_BTN_PRIMARY)
    dialog.mb_btn_download_year.setToolTip(
        _tr("Download the selected year's classification as a QGIS raster layer")
    )
    dl_row.addWidget(dialog.mb_btn_download_year)
    dl_lay.addLayout(dl_row)

    dialog.mb_dl_progress = _progress_bar()
    dl_lay.addWidget(dialog.mb_dl_progress)
    lay.addWidget(dl_panel)

    # --- Transition ------------------------------------------------------
    tx_panel = _section_panel()
    tx_lay = QVBoxLayout(tx_panel)
    tx_lay.setContentsMargins(16, 14, 16, 14)
    tx_lay.setSpacing(10)
    tx_lay.addWidget(_field_label(_tr("TRANSITION (SOURCE → TARGET)")))

    tx_note = QLabel(_tr(
        "Map the first year each pixel went from a source class to a target "
        "class, and chart the converted area per year. Pick a preset or build "
        "a custom source → target."
    ))
    tx_note.setWordWrap(True)
    tx_note.setStyleSheet("color:#757575; font-size:11px; background:transparent;")
    tx_lay.addWidget(tx_note)

    dialog.mb_tx_preset_combo = QComboBox()
    for key, (label, _src, _tgt) in MAPBIOMAS_TRANSITION_PRESETS.items():
        dialog.mb_tx_preset_combo.addItem(_tr(label), key)
    dialog.mb_tx_preset_combo.addItem(_tr("Custom…"), "custom")
    dialog.mb_tx_preset_combo.setCursor(Qt.CursorShape.PointingHandCursor)
    dialog.mb_tx_preset_combo.setMinimumHeight(30)
    dialog.mb_tx_preset_combo.setMaxVisibleItems(12)
    dialog.mb_tx_preset_combo.setStyleSheet(STYLE_COMBO_YEAR)
    tx_lay.addWidget(dialog.mb_tx_preset_combo)

    # Custom source/target pickers — hidden unless the "Custom…" preset is chosen.
    dialog.mb_tx_custom_panel = QWidget()
    dialog.mb_tx_custom_panel.setStyleSheet("background:transparent;")
    custom_lay = QHBoxLayout(dialog.mb_tx_custom_panel)
    custom_lay.setContentsMargins(0, 0, 0, 0)
    custom_lay.setSpacing(10)

    def _class_list():
        widget = QListWidget()
        widget.setStyleSheet(
            "QListWidget {"
            " background:#ffffff; color:#212121; border:1px solid #d0d0d0;"
            " border-radius:6px; font-size:11px; padding:3px; outline:0; }"
            "QListWidget:focus { border:1.5px solid #1b6b39; }"
            "QListWidget::item {"
            " min-height:22px; padding:2px 6px; border-radius:4px; }"
            "QListWidget::item:hover { background:#f1f8f3; }"
            "QListWidget::item:selected {"
            " background:#e8f5e9; color:#1a1a1a; }"
            "QListWidget::indicator { width:15px; height:15px; }"
            "QListWidget::indicator:unchecked {"
            " background:#ffffff; border:1.5px solid #9e9e9e; border-radius:3px; }"
            "QListWidget::indicator:unchecked:hover { border-color:#1b6b39; }"
            "QListWidget::indicator:checked {"
            " background:#1b6b39; border:1.5px solid #1b6b39; border-radius:3px; }"
        )
        widget.setFixedHeight(150)
        widget.setCursor(Qt.CursorShape.PointingHandCursor)
        for class_id, class_label in MAPBIOMAS_CLASS_LABELS.items():
            item = QListWidgetItem(class_label)
            item.setData(Qt.ItemDataRole.UserRole, class_id)
            item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            item.setCheckState(Qt.CheckState.Unchecked)
            widget.addItem(item)
        return widget

    src_col = QVBoxLayout()
    src_col.setSpacing(3)
    src_col.addWidget(_field_label(_tr("FROM (SOURCE)")))
    dialog.mb_tx_src_list = _class_list()
    src_col.addWidget(dialog.mb_tx_src_list)
    custom_lay.addLayout(src_col, 1)

    tgt_col = QVBoxLayout()
    tgt_col.setSpacing(3)
    tgt_col.addWidget(_field_label(_tr("TO (TARGET)")))
    dialog.mb_tx_tgt_list = _class_list()
    tgt_col.addWidget(dialog.mb_tx_tgt_list)
    custom_lay.addLayout(tgt_col, 1)

    dialog.mb_tx_custom_panel.setVisible(False)
    tx_lay.addWidget(dialog.mb_tx_custom_panel)

    dialog.mb_btn_load_transition = QPushButton(_tr("Load transition"))
    dialog.mb_btn_load_transition.setFixedHeight(32)
    dialog.mb_btn_load_transition.setStyleSheet(STYLE_BTN_PRIMARY)
    dialog.mb_btn_load_transition.setToolTip(
        _tr("Map the selected transition and chart its yearly area")
    )
    tx_lay.addWidget(dialog.mb_btn_load_transition)

    dialog.mb_tx_progress = _progress_bar()
    tx_lay.addWidget(dialog.mb_tx_progress)
    lay.addWidget(tx_panel)

    lay.addStretch(1)
    scroll.setWidget(scroll_w)
    outer.addWidget(scroll)


# ------------------------------------------------------------------- coverage
def _build_coverage_tab(dialog, parent):
    lay = QVBoxLayout(parent)
    lay.setContentsMargins(10, 10, 10, 10)
    lay.setSpacing(8)

    body = QHBoxLayout()
    body.setSpacing(10)

    # Left: the year image.
    dialog.mb_cov_image = _image_label(
        _tr("Load coverage from the Inputs tab to browse MapBiomas by year.")
    )
    body.addWidget(dialog.mb_cov_image, 1)

    # Right: scrollable class legend.
    legend_scroll = QScrollArea()
    legend_scroll.setWidgetResizable(True)
    legend_scroll.setFixedWidth(220)
    legend_scroll.setFrameShape(QFrame.Shape.NoFrame)
    legend_scroll.setStyleSheet(
        "QScrollArea { background: #ffffff; border: 1px solid #e4e7e5;"
        " border-radius: 8px; }"
    )
    legend_inner = QWidget()
    legend_inner.setStyleSheet("background: #ffffff;")
    legend_inner_lay = QVBoxLayout(legend_inner)
    legend_inner_lay.setContentsMargins(10, 10, 10, 10)
    legend_inner_lay.setSpacing(0)
    legend_title = QLabel(_tr("Legend — Collection 9"))
    legend_title.setStyleSheet(
        "color:#1b6b39; font-size:11px; font-weight:bold; background:transparent;"
    )
    legend_inner_lay.addWidget(legend_title)
    legend_body = QLabel(_legend_html())
    legend_body.setTextFormat(Qt.TextFormat.RichText)
    legend_body.setWordWrap(True)
    legend_body.setStyleSheet("background:transparent;")
    legend_inner_lay.addWidget(legend_body)
    legend_inner_lay.addStretch(1)
    legend_scroll.setWidget(legend_inner)
    body.addWidget(legend_scroll)

    lay.addLayout(body, 1)

    # Year slider row.
    slider_row = QHBoxLayout()
    slider_row.setSpacing(10)
    min_lbl = QLabel(str(MAPBIOMAS_FIRST_YEAR))
    min_lbl.setStyleSheet("color:#9e9e9e; font-size:10px; background:transparent;")
    slider_row.addWidget(min_lbl)

    dialog.mb_cov_slider = QSlider(Qt.Orientation.Horizontal)
    dialog.mb_cov_slider.setMinimum(MAPBIOMAS_FIRST_YEAR)
    dialog.mb_cov_slider.setMaximum(MAPBIOMAS_LATEST_YEAR)
    dialog.mb_cov_slider.setValue(MAPBIOMAS_LATEST_YEAR)
    dialog.mb_cov_slider.setSingleStep(1)
    dialog.mb_cov_slider.setPageStep(1)
    dialog.mb_cov_slider.setEnabled(False)
    dialog.mb_cov_slider.setStyleSheet(_SLIDER_STYLE)
    slider_row.addWidget(dialog.mb_cov_slider, 1)

    max_lbl = QLabel(str(MAPBIOMAS_LATEST_YEAR))
    max_lbl.setStyleSheet("color:#9e9e9e; font-size:10px; background:transparent;")
    slider_row.addWidget(max_lbl)

    dialog.mb_cov_year_lbl = QLabel(str(MAPBIOMAS_LATEST_YEAR))
    dialog.mb_cov_year_lbl.setFixedWidth(46)
    dialog.mb_cov_year_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
    dialog.mb_cov_year_lbl.setStyleSheet(
        "color:#1b6b39; font-size:14px; font-weight:bold; background:transparent;"
    )
    slider_row.addWidget(dialog.mb_cov_year_lbl)

    dialog.mb_btn_download_qgis = QPushButton(_tr("Download year to QGIS"))
    dialog.mb_btn_download_qgis.setFixedHeight(28)
    dialog.mb_btn_download_qgis.setStyleSheet(STYLE_BTN_SECONDARY)
    dialog.mb_btn_download_qgis.setToolTip(
        _tr("Download the selected year's classification as a GeoTIFF raster "
            "layer (real class IDs, styled with the MapBiomas palette)")
    )
    slider_row.addWidget(dialog.mb_btn_download_qgis)
    lay.addLayout(slider_row)


# ----------------------------------------------------------------- transition
def _build_transition_tab(dialog, parent):
    lay = QVBoxLayout(parent)
    lay.setContentsMargins(10, 10, 10, 10)
    lay.setSpacing(8)

    top = QHBoxLayout()
    top.setSpacing(6)
    dialog.mb_stats_summary = QLabel(
        _tr("Load the transition from the Inputs tab.")
    )
    dialog.mb_stats_summary.setStyleSheet(
        "color:#616161; font-size:12px; font-weight:bold; background:transparent;"
    )
    top.addWidget(dialog.mb_stats_summary)
    top.addStretch(1)
    dialog.mb_btn_download_tx_qgis = QPushButton(_tr("Download to QGIS"))
    dialog.mb_btn_download_tx_qgis.setStyleSheet(STYLE_BTN_SECONDARY)
    dialog.mb_btn_download_tx_qgis.setFixedHeight(28)
    dialog.mb_btn_download_tx_qgis.setToolTip(
        _tr("Download the transition raster (classed by transition year, "
            "limited to the selected year range) as a QGIS layer")
    )
    top.addWidget(dialog.mb_btn_download_tx_qgis)
    dialog.mb_btn_browser_transition = QPushButton(_tr("Open chart in browser"))
    dialog.mb_btn_browser_transition.setStyleSheet(STYLE_BTN_SECONDARY)
    dialog.mb_btn_browser_transition.setFixedHeight(28)
    dialog.mb_btn_browser_transition.setToolTip(
        _tr("Open the per-year chart full-screen in your web browser")
    )
    top.addWidget(dialog.mb_btn_browser_transition)
    lay.addLayout(top)

    body = QHBoxLayout()
    body.setSpacing(10)
    dialog.mb_tx_image = _image_label(_tr("The transition map appears here."))
    body.addWidget(dialog.mb_tx_image, 1)
    dialog.mb_web_transition = _make_webview()
    body.addWidget(dialog.mb_web_transition, 1)
    lay.addLayout(body, 1)

    # Year range filter — drives the chart live and limits the exported layer.
    range_row = QHBoxLayout()
    range_row.setSpacing(10)
    dialog.mb_tx_range_lbl = QLabel(
        _tr("Years: {0}–{1}").format(
            MAPBIOMAS_TRANSITION_FIRST_YEAR, MAPBIOMAS_TRANSITION_LAST_YEAR
        )
    )
    dialog.mb_tx_range_lbl.setFixedWidth(140)
    dialog.mb_tx_range_lbl.setStyleSheet(
        "color:#1b6b39; font-size:12px; font-weight:bold; background:transparent;"
    )
    range_row.addWidget(dialog.mb_tx_range_lbl)
    dialog.mb_tx_range = RangeSlider(
        MAPBIOMAS_TRANSITION_FIRST_YEAR, MAPBIOMAS_TRANSITION_LAST_YEAR,
        MAPBIOMAS_TRANSITION_FIRST_YEAR, MAPBIOMAS_TRANSITION_LAST_YEAR,
        decimals=0,
    )
    range_row.addWidget(dialog.mb_tx_range, 1)
    lay.addLayout(range_row)


def setup_mapbiomas_page(dialog, page):
    """
    Populate the MapBiomas page with a three-tab layout (Inputs | Coverage |
    Transition).

    Exposes on dialog (mb_* prefix): mb_layer_combo, mb_btn_draw_aoi,
    mb_btn_hybrid_layer, mb_btn_load_coverage, mb_btn_load_transition,
    mb_cov_progress, mb_dl_progress, mb_tx_progress, mb_cov_image,
    mb_cov_slider, mb_cov_year_lbl, mb_tx_image,
    mb_stats_summary, mb_web_transition, mb_btn_browser_transition, mb_stack,
    mb_set_tab.
    """
    page.setObjectName("mapbiomasPage")
    page.setStyleSheet("""
        QWidget#mapbiomasPage { background-color: #ffffff; }
        QLabel { background: transparent; border: none; }
        QgsMapLayerComboBox {
            combobox-popup: 0;
            background-color: #ffffff;
            color: #212121;
            border: 1px solid #d0d0d0;
            border-radius: 6px;
            padding: 4px 9px;
            font-size: 12px;
        }
        QgsMapLayerComboBox:focus { border: 1.5px solid #1b6b39; }
        QgsMapLayerComboBox QAbstractItemView {
            background-color: #ffffff;
            color: #212121;
            border: 1px solid #bdbdbd;
            selection-background-color: #e8f5e9;
            selection-color: #1a1a1a;
            outline: 0;
        }
    """)

    outer = QVBoxLayout(page)
    outer.setContentsMargins(0, 0, 0, 0)
    outer.setSpacing(0)

    tab_bar = QFrame()
    tab_bar.setObjectName("mapbiomasTabBar")
    tab_bar.setFixedHeight(40)
    tab_bar.setStyleSheet("""
        QFrame#mapbiomasTabBar {
            background-color: #f8f9fa;
            border-bottom: 1px solid #e0e0e0;
        }
    """)
    tab_bar_lay = QHBoxLayout(tab_bar)
    tab_bar_lay.setContentsMargins(6, 0, 6, 0)
    tab_bar_lay.setSpacing(8)

    tab_buttons = []
    for label in (_tr("Inputs"), _tr("Coverage"), _tr("Transition")):
        btn = QPushButton(label)
        btn.setFixedHeight(40)
        btn.setCursor(Qt.CursorShape.PointingHandCursor)
        tab_bar_lay.addWidget(btn)
        tab_buttons.append(btn)
    tab_bar_lay.addStretch(1)
    outer.addWidget(tab_bar)

    stack = QStackedWidget()
    stack.setStyleSheet("QStackedWidget { background: transparent; border: none; }")

    inputs_page = QWidget()
    _build_inputs_tab(dialog, inputs_page)
    stack.addWidget(inputs_page)

    coverage_page = QWidget()
    _build_coverage_tab(dialog, coverage_page)
    stack.addWidget(coverage_page)

    transition_page = QWidget()
    _build_transition_tab(dialog, transition_page)
    stack.addWidget(transition_page)

    outer.addWidget(stack, 1)
    dialog.mb_stack = stack

    # Bottom nav bar: Back / Next walk through the three tabs.
    nav_bar = QFrame()
    nav_bar.setObjectName("mapbiomasNavBar")
    nav_bar.setFixedHeight(46)
    nav_bar.setStyleSheet("""
        QFrame#mapbiomasNavBar {
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

    btn_next = QPushButton(_tr("Next"))
    btn_next.setMinimumWidth(90)
    btn_next.setFixedHeight(30)
    btn_next.setStyleSheet(STYLE_BTN_PRIMARY)
    nav_lay.addWidget(btn_next)
    outer.addWidget(nav_bar)

    dialog.mb_btn_back = btn_back
    dialog.mb_btn_next = btn_next

    last = len(tab_buttons) - 1

    def _set_tab(index):
        stack.setCurrentIndex(index)
        for i, btn in enumerate(tab_buttons):
            btn.setStyleSheet(_TAB_ACTIVE if i == index else _TAB_INACTIVE)
        btn_back.setEnabled(index > 0)
        btn_next.setVisible(index < last)
        step_lbl.setText(_tr("Step %d of %d") % (index + 1, last + 1))

    dialog.mb_set_tab = _set_tab

    for i, btn in enumerate(tab_buttons):
        btn.clicked.connect(lambda _checked=False, index=i: _set_tab(index))
    btn_back.clicked.connect(
        lambda: _set_tab(max(0, stack.currentIndex() - 1))
    )
    btn_next.clicked.connect(
        lambda: _set_tab(min(last, stack.currentIndex() + 1))
    )

    _set_tab(0)
