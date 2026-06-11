# -*- coding: utf-8 -*-
"""
Field Guide page for the RAVI dialog.

Builds the field-work page: canvas point capture, polygon feature sampling,
session point list, manual WGS84 input, Google Maps routes, and CSV/GPX/PDF
import-export actions.  Signal connections are wired externally by
``farm_tools.py`` and ``fieldguide_ctrl.py``.
"""

from qgis.PyQt.QtCore import Qt, QCoreApplication
from qgis.PyQt.QtWidgets import (
    QAbstractItemView,
    QComboBox,
    QDoubleSpinBox,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)
from qgis.core import QgsMapLayerProxyModel
from qgis.gui import QgsMapLayerComboBox

from .styles import STYLE_AOI_PAGE, STYLE_BTN_PRIMARY, STYLE_BTN_SECONDARY


def _tr(text):
    return QCoreApplication.translate("RAVI", text)


_HINT_STYLE = "color: #757575; font-size: 9px;"
_SUMMARY_KEY_STYLE = "color: #9e9e9e; font-size: 11px;"
_SUMMARY_VALUE_STYLE = "color: #212121; font-size: 11px; font-weight: bold;"

_POINTS_LIST_STYLE = """
QListWidget {
    background-color: #fbfcfb;
    color: #212121;
    border: 1px solid #e0e0e0;
    border-radius: 8px;
    padding: 4px;
    font-size: 11px;
}
QListWidget::item {
    padding: 3px 4px;
    border-radius: 4px;
}
QListWidget::item:selected {
    background-color: #e8f5e9;
    color: #1a1a1a;
}
"""


def _field_label(text):
    lbl = QLabel(text)
    lbl.setObjectName("aoiFieldLabel")
    return lbl


def _hint_label(text=""):
    lbl = QLabel(text)
    lbl.setWordWrap(True)
    lbl.setStyleSheet(_HINT_STYLE)
    return lbl


def _section_separator():
    separator = QFrame()
    separator.setFrameShape(QFrame.Shape.HLine)
    separator.setStyleSheet("color: #e0e0e0;")
    return separator


def setup_fieldguide_page(dialog, page):
    """
    Populate the Field Guide page.

    The white panel is split into two areas:

    - **Scrollable area** (top, expands): capture toggle, polygon sampling
      settings, session state list, manual coordinate input, route and
      import/export actions.
    - **Fixed footer** (always visible): the Generate PDF report action.

    All interactive widgets are exposed on ``dialog`` as ``fg_*`` attributes so
    ``farm_tools.py`` and ``fieldguide_ctrl.py`` can wire signal connections
    without importing this module directly.
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

    title_lbl = QLabel(_tr("Field Guide"))
    title_lbl.setObjectName("aoiTitle")
    scroll_lay.addWidget(title_lbl)

    subtitle_lbl = QLabel(
        _tr(
            "Capture field points on the map, sample polygon features, and "
            "export routes, files, and PDF reports."
        )
    )
    subtitle_lbl.setObjectName("aoiSubtitle")
    subtitle_lbl.setWordWrap(True)
    scroll_lay.addWidget(subtitle_lbl)

    scroll_lay.addSpacing(4)

    # ------------------------------------------------------------------
    # Capture
    # ------------------------------------------------------------------
    scroll_lay.addWidget(_field_label(_tr("CAPTURE")))

    capture_hint = _hint_label(
        _tr(
            "Use direct map clicks for field capture, or select a polygon "
            "layer below to generate marks inside each feature."
        )
    )
    scroll_lay.addWidget(capture_hint)

    capture_row = QWidget()
    capture_row_lay = QHBoxLayout(capture_row)
    capture_row_lay.setContentsMargins(0, 0, 0, 0)
    capture_row_lay.setSpacing(6)

    dialog.fg_btn_capture = QPushButton(_tr("Capture points on map"))
    dialog.fg_btn_capture.setCheckable(True)
    dialog.fg_btn_capture.setToolTip(
        _tr("Toggle capture mode, then click on the map to add points")
    )
    dialog.fg_btn_capture.setFixedHeight(28)
    dialog.fg_btn_capture.setStyleSheet(STYLE_BTN_SECONDARY)
    capture_row_lay.addWidget(dialog.fg_btn_capture, 1)

    dialog.fg_capture_status_lbl = QLabel(_tr("Capture OFF"))
    dialog.fg_capture_status_lbl.setStyleSheet(_SUMMARY_KEY_STYLE)
    capture_row_lay.addWidget(dialog.fg_capture_status_lbl)

    dialog.fg_btn_hybrid_layer = QPushButton(_tr("Add Google Hybrid Layer"))
    dialog.fg_btn_hybrid_layer.setFixedHeight(28)
    dialog.fg_btn_hybrid_layer.setSizePolicy(
        QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed
    )
    dialog.fg_btn_hybrid_layer.setStyleSheet(STYLE_BTN_SECONDARY)
    capture_row_lay.addWidget(dialog.fg_btn_hybrid_layer)

    scroll_lay.addWidget(capture_row)

    scroll_lay.addSpacing(6)
    scroll_lay.addWidget(_section_separator())
    scroll_lay.addSpacing(4)

    # ------------------------------------------------------------------
    # Polygon sampling
    # ------------------------------------------------------------------
    scroll_lay.addWidget(_field_label(_tr("POLYGON SAMPLING")))

    dialog.fg_layer_combo = QgsMapLayerComboBox()
    dialog.fg_layer_combo.setObjectName("fgLayerCombo")
    dialog.fg_layer_combo.setFilters(QgsMapLayerProxyModel.PolygonLayer)
    dialog.fg_layer_combo.setAllowEmptyLayer(True)
    dialog.fg_layer_combo.setFixedHeight(28)
    scroll_lay.addWidget(dialog.fg_layer_combo)

    sampling_grid = QGridLayout()
    sampling_grid.setContentsMargins(0, 0, 0, 0)
    sampling_grid.setHorizontalSpacing(8)
    sampling_grid.setVerticalSpacing(6)

    dialog.fg_quantity_mode_lbl = QLabel(_tr("Sampling quantity"))
    sampling_grid.addWidget(dialog.fg_quantity_mode_lbl, 0, 0)
    dialog.fg_quantity_mode_combo = QComboBox()
    dialog.fg_quantity_mode_combo.addItem(_tr("Fixed marks per feature"), "fixed_count")
    dialog.fg_quantity_mode_combo.addItem(_tr("Density by area"), "area_density")
    sampling_grid.addWidget(dialog.fg_quantity_mode_combo, 0, 1)

    dialog.fg_samples_lbl = QLabel(_tr("Marks per feature"))
    sampling_grid.addWidget(dialog.fg_samples_lbl, 1, 0)
    dialog.fg_samples_spin = QSpinBox()
    dialog.fg_samples_spin.setRange(1, 50)
    dialog.fg_samples_spin.setValue(1)
    dialog.fg_samples_spin.setFixedHeight(26)
    sampling_grid.addWidget(dialog.fg_samples_spin, 1, 1)

    dialog.fg_density_lbl = QLabel(_tr("Hectares per mark"))
    sampling_grid.addWidget(dialog.fg_density_lbl, 2, 0)
    dialog.fg_density_spin = QDoubleSpinBox()
    dialog.fg_density_spin.setRange(0.1, 100000.0)
    dialog.fg_density_spin.setDecimals(2)
    dialog.fg_density_spin.setSingleStep(0.25)
    dialog.fg_density_spin.setValue(1.0)
    dialog.fg_density_spin.setSuffix(" ha")
    dialog.fg_density_spin.setFixedHeight(26)
    sampling_grid.addWidget(dialog.fg_density_spin, 2, 1)

    dialog.fg_distribution_lbl = QLabel(_tr("Distribution method"))
    sampling_grid.addWidget(dialog.fg_distribution_lbl, 3, 0)
    dialog.fg_distribution_combo = QComboBox()
    dialog.fg_distribution_combo.addItem(_tr("Spread optimized"), "spread_optimized")
    dialog.fg_distribution_combo.addItem(_tr("Systematic grid"), "systematic_grid")
    dialog.fg_distribution_combo.addItem(_tr("Zigzag transect"), "zigzag_transect")
    sampling_grid.addWidget(dialog.fg_distribution_combo, 3, 1)

    scroll_lay.addLayout(sampling_grid)

    dialog.fg_sampling_hint_lbl = _hint_label()
    scroll_lay.addWidget(dialog.fg_sampling_hint_lbl)

    dialog.fg_btn_mark_samples = QPushButton(_tr("Mark feature centroids"))
    dialog.fg_btn_mark_samples.setFixedHeight(28)
    dialog.fg_btn_mark_samples.setStyleSheet(STYLE_BTN_SECONDARY)
    scroll_lay.addWidget(dialog.fg_btn_mark_samples)

    def _update_sampling_controls(*_args):
        """Refresh polygon sampling hints and control states from current values."""
        quantity_mode = dialog.fg_quantity_mode_combo.currentData()
        sample_count = int(dialog.fg_samples_spin.value())
        density_value = float(dialog.fg_density_spin.value())
        uses_density = quantity_mode == "area_density"
        uses_centroid = (not uses_density) and sample_count == 1

        dialog.fg_samples_lbl.setEnabled(not uses_density)
        dialog.fg_samples_spin.setEnabled(not uses_density)
        dialog.fg_density_lbl.setEnabled(uses_density)
        dialog.fg_density_spin.setEnabled(uses_density)
        dialog.fg_distribution_lbl.setEnabled(not uses_centroid)
        dialog.fg_distribution_combo.setEnabled(not uses_centroid)

        method = dialog.fg_distribution_combo.currentData()
        if uses_density:
            density_text = "{:g}".format(round(density_value, 2))
            if method == "systematic_grid":
                hint_text = _tr(
                    "Generates the mark count from feature area using 1 mark per "
                    "{0} ha. Features that resolve to 1 mark use the centroid "
                    "automatically; larger features follow a regular internal grid."
                ).format(density_text)
            elif method == "zigzag_transect":
                hint_text = _tr(
                    "Generates the mark count from feature area using 1 mark per "
                    "{0} ha. Features that resolve to 1 mark use the centroid "
                    "automatically; larger features follow a zigzag field transect."
                ).format(density_text)
            else:
                hint_text = _tr(
                    "Generates the mark count from feature area using 1 mark per "
                    "{0} ha. Features that resolve to 1 mark use the centroid "
                    "automatically; larger features maximize internal spacing."
                ).format(density_text)
            dialog.fg_sampling_hint_lbl.setText(hint_text)
            dialog.fg_btn_mark_samples.setText(_tr("Mark feature samples by density"))
        elif uses_centroid:
            dialog.fg_sampling_hint_lbl.setText(
                _tr("One mark per feature uses the polygon centroid.")
            )
            dialog.fg_btn_mark_samples.setText(_tr("Mark feature centroids"))
        else:
            if method == "systematic_grid":
                hint_text = _tr(
                    "Places marks from a regular grid clipped to each polygon. "
                    "Good for balanced field coverage and repeatable spacing."
                )
            elif method == "zigzag_transect":
                hint_text = _tr(
                    "Builds a serpentine walk pattern across each polygon, similar "
                    "to common zigzag soil sampling in the field."
                )
            else:
                hint_text = _tr(
                    "Chooses marks that maximize spacing inside each polygon. Good "
                    "default for irregular areas and strong spatial distribution."
                )
            dialog.fg_sampling_hint_lbl.setText(hint_text)
            dialog.fg_btn_mark_samples.setText(_tr("Mark feature samples"))

        dialog.fg_btn_mark_samples.setEnabled(
            dialog.fg_layer_combo.currentLayer() is not None
        )

    dialog.fg_quantity_mode_combo.currentIndexChanged.connect(_update_sampling_controls)
    dialog.fg_samples_spin.valueChanged.connect(_update_sampling_controls)
    dialog.fg_density_spin.valueChanged.connect(_update_sampling_controls)
    dialog.fg_distribution_combo.currentIndexChanged.connect(_update_sampling_controls)
    dialog.fg_layer_combo.layerChanged.connect(_update_sampling_controls)
    _update_sampling_controls()

    scroll_lay.addSpacing(6)
    scroll_lay.addWidget(_section_separator())
    scroll_lay.addSpacing(4)

    # ------------------------------------------------------------------
    # Session state
    # ------------------------------------------------------------------
    scroll_lay.addWidget(_field_label(_tr("SESSION")))

    summary_grid = QGridLayout()
    summary_grid.setContentsMargins(0, 0, 0, 0)
    summary_grid.setHorizontalSpacing(8)
    summary_grid.setVerticalSpacing(2)

    points_key_lbl = QLabel(_tr("Points"))
    points_key_lbl.setStyleSheet(_SUMMARY_KEY_STYLE)
    summary_grid.addWidget(points_key_lbl, 0, 0)
    dialog.fg_point_count_lbl = QLabel("0")
    dialog.fg_point_count_lbl.setStyleSheet(_SUMMARY_VALUE_STYLE)
    summary_grid.addWidget(dialog.fg_point_count_lbl, 0, 1)

    last_key_lbl = QLabel(_tr("Last point"))
    last_key_lbl.setStyleSheet(_SUMMARY_KEY_STYLE)
    summary_grid.addWidget(last_key_lbl, 1, 0)
    dialog.fg_last_point_lbl = QLabel(_tr("No points yet"))
    dialog.fg_last_point_lbl.setWordWrap(True)
    dialog.fg_last_point_lbl.setStyleSheet(_SUMMARY_VALUE_STYLE)
    summary_grid.addWidget(dialog.fg_last_point_lbl, 1, 1)

    route_key_lbl = QLabel(_tr("Route readiness"))
    route_key_lbl.setStyleSheet(_SUMMARY_KEY_STYLE)
    summary_grid.addWidget(route_key_lbl, 2, 0)
    dialog.fg_route_status_lbl = QLabel(_tr("Add at least 2 points"))
    dialog.fg_route_status_lbl.setWordWrap(True)
    dialog.fg_route_status_lbl.setStyleSheet(_SUMMARY_VALUE_STYLE)
    summary_grid.addWidget(dialog.fg_route_status_lbl, 2, 1)

    summary_grid.setColumnStretch(1, 1)
    scroll_lay.addLayout(summary_grid)

    points_hint = _hint_label(_tr("Captured points appear here in collection order."))
    scroll_lay.addWidget(points_hint)

    dialog.fg_points_list = QListWidget()
    dialog.fg_points_list.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
    dialog.fg_points_list.setMinimumHeight(140)
    dialog.fg_points_list.setStyleSheet(_POINTS_LIST_STYLE)
    scroll_lay.addWidget(dialog.fg_points_list)

    session_actions = QHBoxLayout()
    session_actions.setContentsMargins(0, 0, 0, 0)
    session_actions.setSpacing(6)

    dialog.fg_btn_remove_last = QPushButton(_tr("Remove last mark"))
    dialog.fg_btn_remove_last.setFixedHeight(26)
    dialog.fg_btn_remove_last.setStyleSheet(STYLE_BTN_SECONDARY)
    session_actions.addWidget(dialog.fg_btn_remove_last)

    dialog.fg_btn_delete_selected = QPushButton(_tr("Delete selected mark"))
    dialog.fg_btn_delete_selected.setFixedHeight(26)
    dialog.fg_btn_delete_selected.setStyleSheet(STYLE_BTN_SECONDARY)
    session_actions.addWidget(dialog.fg_btn_delete_selected)

    dialog.fg_btn_clear = QPushButton(_tr("Clear marks"))
    dialog.fg_btn_clear.setFixedHeight(26)
    dialog.fg_btn_clear.setStyleSheet(STYLE_BTN_SECONDARY)
    session_actions.addWidget(dialog.fg_btn_clear)

    scroll_lay.addLayout(session_actions)

    scroll_lay.addSpacing(6)
    scroll_lay.addWidget(_section_separator())
    scroll_lay.addSpacing(4)

    # ------------------------------------------------------------------
    # Manual coordinate
    # ------------------------------------------------------------------
    scroll_lay.addWidget(_field_label(_tr("MANUAL COORDINATE (WGS84)")))

    manual_hint = _hint_label(
        _tr("Accepts decimal coordinates with dot or comma separators.")
    )
    scroll_lay.addWidget(manual_hint)

    manual_row = QHBoxLayout()
    manual_row.setContentsMargins(0, 0, 0, 0)
    manual_row.setSpacing(6)

    dialog.fg_lat_input = QLineEdit()
    dialog.fg_lat_input.setPlaceholderText(_tr("Latitude (e.g.: -23.550520)"))
    dialog.fg_lat_input.setFixedHeight(28)
    manual_row.addWidget(dialog.fg_lat_input, 1)

    dialog.fg_lon_input = QLineEdit()
    dialog.fg_lon_input.setPlaceholderText(_tr("Longitude (e.g.: -46.633308)"))
    dialog.fg_lon_input.setFixedHeight(28)
    manual_row.addWidget(dialog.fg_lon_input, 1)

    dialog.fg_btn_add_manual = QPushButton(_tr("Add coordinate"))
    dialog.fg_btn_add_manual.setFixedHeight(28)
    dialog.fg_btn_add_manual.setStyleSheet(STYLE_BTN_SECONDARY)
    manual_row.addWidget(dialog.fg_btn_add_manual)

    scroll_lay.addLayout(manual_row)

    scroll_lay.addSpacing(6)
    scroll_lay.addWidget(_section_separator())
    scroll_lay.addSpacing(4)

    # ------------------------------------------------------------------
    # Route + import/export
    # ------------------------------------------------------------------
    scroll_lay.addWidget(_field_label(_tr("ROUTE")))

    route_hint = _hint_label(
        _tr("Open the current route in Google Maps when at least 2 points exist.")
    )
    scroll_lay.addWidget(route_hint)

    dialog.fg_btn_route = QPushButton(_tr("Open route in Google Maps"))
    dialog.fg_btn_route.setFixedHeight(28)
    dialog.fg_btn_route.setStyleSheet(STYLE_BTN_SECONDARY)
    scroll_lay.addWidget(dialog.fg_btn_route)

    scroll_lay.addSpacing(6)
    scroll_lay.addWidget(_section_separator())
    scroll_lay.addSpacing(4)

    scroll_lay.addWidget(_field_label(_tr("IMPORT / EXPORT")))

    output_hint = _hint_label(
        _tr(
            "Import coordinates from CSV, export the current session to CSV or "
            "GPX, or add the marks as a temporary layer."
        )
    )
    scroll_lay.addWidget(output_hint)

    io_grid = QGridLayout()
    io_grid.setContentsMargins(0, 0, 0, 0)
    io_grid.setHorizontalSpacing(6)
    io_grid.setVerticalSpacing(6)

    dialog.fg_btn_import_csv = QPushButton(_tr("Import points CSV"))
    dialog.fg_btn_import_csv.setFixedHeight(26)
    dialog.fg_btn_import_csv.setStyleSheet(STYLE_BTN_SECONDARY)
    io_grid.addWidget(dialog.fg_btn_import_csv, 0, 0)

    dialog.fg_btn_export_csv = QPushButton(_tr("Export points CSV"))
    dialog.fg_btn_export_csv.setFixedHeight(26)
    dialog.fg_btn_export_csv.setStyleSheet(STYLE_BTN_SECONDARY)
    io_grid.addWidget(dialog.fg_btn_export_csv, 0, 1)

    dialog.fg_btn_export_gpx = QPushButton(_tr("Export GPS GPX"))
    dialog.fg_btn_export_gpx.setFixedHeight(26)
    dialog.fg_btn_export_gpx.setStyleSheet(STYLE_BTN_SECONDARY)
    io_grid.addWidget(dialog.fg_btn_export_gpx, 1, 0)

    dialog.fg_btn_temp_layer = QPushButton(_tr("Add Temporary Layer"))
    dialog.fg_btn_temp_layer.setFixedHeight(26)
    dialog.fg_btn_temp_layer.setStyleSheet(STYLE_BTN_SECONDARY)
    io_grid.addWidget(dialog.fg_btn_temp_layer, 1, 1)

    scroll_lay.addLayout(io_grid)

    scroll_lay.addStretch()
    scroll_area.setWidget(scroll_content)
    panel_lay.addWidget(scroll_area, 1)

    footer_separator = QFrame()
    footer_separator.setFrameShape(QFrame.Shape.HLine)
    footer_separator.setStyleSheet("color: #e8e8e8;")
    panel_lay.addWidget(footer_separator)

    panel_lay.addSpacing(6)

    action_row = QHBoxLayout()
    action_row.setContentsMargins(0, 0, 0, 0)
    action_row.setSpacing(8)

    action_row.addStretch(1)

    dialog.fg_btn_pdf = QPushButton(_tr("Generate PDF report"))
    dialog.fg_btn_pdf.setFixedSize(170, 32)
    dialog.fg_btn_pdf.setStyleSheet(STYLE_BTN_PRIMARY)
    action_row.addWidget(dialog.fg_btn_pdf)

    action_row.addStretch(1)

    panel_lay.addLayout(action_row)

    outer.addWidget(panel)
