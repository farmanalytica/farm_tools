# -*- coding: utf-8 -*-
"""
Management Zones page for the RAVI dialog (functional fork of precision_zones).

Six-tab layout mirroring the plugin's pipeline: Intro → Data → PCA → Zones →
Filter → Analysis. GEE-free: everything runs locally on rasters already loaded
in the QGIS project (resample/sample → PCA → KMeans zones → mode filter →
variance-reduction analysis).

Signal connections are wired externally by ``farm_tools.py``. All interactive
widgets are exposed on ``dialog`` as ``mz_*`` attributes.
"""

from qgis.core import QgsMapLayerProxyModel, QgsProject, QgsRasterLayer
from qgis.gui import QgsMapLayerComboBox
from qgis.PyQt.QtCore import Qt, QCoreApplication
from qgis.PyQt.QtGui import QGuiApplication
from qgis.PyQt.QtWidgets import (
    QAbstractItemView,
    QComboBox,
    QDialog,
    QFrame,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QPlainTextEdit,
    QPushButton,
    QRadioButton,
    QScrollArea,
    QSpinBox,
    QStackedWidget,
    QTableWidget,
    QVBoxLayout,
    QWidget,
)

# Matplotlib canvas: Qt6 uses qtagg; Qt5 uses qt5agg
try:
    from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas
except Exception:
    from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure

from .radar import (
    _TAB_ACTIVE,
    _TAB_INACTIVE,
    _field_label,
    _make_divider,
    _prepare_field,
    _section_panel,
)
from .styles import STYLE_BTN_PRIMARY, STYLE_BTN_SECONDARY


def _tr(text):
    return QCoreApplication.translate("RAVI", text)


_TAB_KEYS = ("intro", "data", "pca", "zones", "filter", "analysis")

# Chips on the intro tab track the packages the pipeline imports lazily.
_DEP_NAMES = ("pandas", "scikit-learn", "scipy")


def _h_lbl(html, style=""):
    lbl = QLabel(html)
    lbl.setWordWrap(True)
    lbl.setOpenExternalLinks(True)
    lbl.setTextFormat(Qt.TextFormat.RichText)
    if style:
        lbl.setStyleSheet(style)
    return lbl


def _hint(text):
    lbl = QLabel(text)
    lbl.setStyleSheet("color: #9e9e9e; font-size: 11px; background: transparent;")
    lbl.setWordWrap(True)
    return lbl


def _primary(btn):
    btn.setStyleSheet(STYLE_BTN_PRIMARY)
    btn.setMinimumHeight(32)
    btn.setCursor(Qt.CursorShape.PointingHandCursor)
    return btn


def _secondary(btn):
    btn.setStyleSheet(STYLE_BTN_SECONDARY)
    btn.setMinimumHeight(28)
    btn.setCursor(Qt.CursorShape.PointingHandCursor)
    return btn


def _scroll_tab(parent):
    """Standard scroll-wrapped white tab body; returns the content layout."""
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
    lay.setSpacing(10)
    scroll.setWidget(w)
    outer.addWidget(scroll, 1)
    return lay


def _panel(lay):
    """Add a section panel to ``lay``; return its inner layout."""
    panel = _section_panel()
    inner = QVBoxLayout(panel)
    inner.setContentsMargins(14, 12, 14, 12)
    inner.setSpacing(8)
    lay.addWidget(panel)
    return inner


# --------------------------------------------------------------------- intro
def _build_intro_tab(dialog, parent):
    lay = _scroll_tab(parent)

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

    lay.setSpacing(4)
    lay.addWidget(_h1(_tr("🗺️ Management Zones")))
    lay.addSpacing(2)
    lay.addWidget(
        _para(
            _tr(
                "Delineate <b>within-field management zones</b> from rasters already "
                "loaded in QGIS (yield maps, vegetation indices, soil properties, "
                "elevation…). The pipeline resamples all inputs to a common grid, "
                "reduces them with <b>PCA</b>, clusters with <b>KMeans</b> and writes "
                "the zones as a raster — fully local, no Earth Engine required."
            )
        )
    )

    lay.addWidget(_h2(_tr("📋 Workflow")))
    lay.addWidget(_make_divider())
    wf_frame = QFrame()
    wf_frame.setStyleSheet("QFrame{background:#f0f8ff;border-radius:4px;padding:4px;}")
    wf_lay = QVBoxLayout(wf_frame)
    wf_lay.setContentsMargins(12, 6, 12, 6)
    wf_lay.setSpacing(4)
    for i, text in enumerate(
        [
            _tr("<b>Data:</b> Pick the field boundary, input rasters and target resolution"),
            _tr("<b>PCA:</b> Reduce correlated inputs to principal components"),
            _tr("<b>Zones:</b> Evaluate k with Elbow + Silhouette, then generate the zones raster"),
            _tr("<b>Filter:</b> Smooth the zones raster with a majority (mode) filter"),
            _tr("<b>Analysis:</b> Check zone quality with variance-reduction statistics and boxplots"),
        ],
        1,
    ):
        wf_lay.addWidget(_para(f"{i}. {text}"))
    lay.addWidget(wf_frame)

    lay.addWidget(_h2(_tr("✨ Main Features")))
    lay.addWidget(_make_divider())
    for text in [
        _tr("<b>Any raster inputs:</b> combine yield, NDVI composites, soil and terrain layers in any CRS"),
        _tr("<b>Common grid:</b> automatic UTM reprojection, resampling and clipping to the field boundary"),
        _tr("<b>PCA report:</b> eigenvalues, explained variance and loadings, exportable as CSV and GeoTIFF"),
        _tr("<b>Cluster diagnostics:</b> Elbow (inertia) and Silhouette curves for every k in a range"),
        _tr("<b>Zone smoothing:</b> circular-kernel majority filter removes speckle"),
        _tr("<b>Validation:</b> per-zone statistics, area-weighted variance reduction and boxplots"),
    ]:
        lay.addWidget(_para(f"✓  {text}"))

    lay.addWidget(_h2(_tr("🌱 Credits")))
    lay.addWidget(_make_divider())
    lay.addWidget(
        _para(
            _tr(
                "This module is essentially an integrated fork of the "
                '<a href="https://github.com/Derleimelo/Precision-Zones-Plugin">'
                "<b>Precision Zones</b></a> QGIS plugin, by "
                '<a href="https://www.linkedin.com/in/derlei-dias-melo-022717229/">'
                "<b>Derlei Dias Melo</b></a>, Isabella Cunha and Lucas Amaral "
                "(FEAGRI — UNICAMP)."
            )
        )
    )

    lay.addWidget(_h2(_tr("📖 Citation")))
    lay.addWidget(_make_divider())
    lay.addWidget(
        _para(_tr("Any published work using this module <b>must cite</b> the original paper:"))
    )
    cite_frame = QFrame()
    cite_frame.setStyleSheet("QFrame{background:#f0f8ff;border-radius:4px;padding:4px;}")
    cite_lay = QVBoxLayout(cite_frame)
    cite_lay.setContentsMargins(12, 6, 12, 6)
    cite_lay.setSpacing(4)
    cite_lay.addWidget(
        _para(
            "Melo, D. D., Cunha, I. A., &amp; Amaral, L. R. (2025). "
            "<i>Precision Zones: An Open-Source QGIS Plugin for Management-Zone "
            "Segmentation in Precision Agriculture.</i> "
            "AgriEngineering, 7(12), 420. DOI: "
            '<a href="https://doi.org/10.3390/agriengineering7120420">'
            "10.3390/agriengineering7120420</a>"
        )
    )
    lay.addWidget(cite_frame)

    # --- dependency status panel -------------------------------------
    lay.addWidget(_h2(_tr("🔧 Dependencies")))
    lay.addWidget(_make_divider())

    chips_row = QHBoxLayout()
    chips_row.setSpacing(8)
    dep_chips = {}
    for name in _DEP_NAMES:
        chip = QLabel(name)
        chip.setToolTip(name)
        dep_chips[name] = chip
        chips_row.addWidget(chip)
    chips_row.addStretch()
    lay.addLayout(chips_row)

    def _chip_style(state):
        colors = {
            "ok": ("#1b5e20", "#e8f5e9", "#a5d6a7"),
            "missing": ("#b71c1c", "#fdecea", "#f5c6c2"),
            "neutral": ("#616161", "#f0f0f0", "#e0e0e0"),
        }
        fg, bg, br = colors.get(state, colors["neutral"])
        return (
            f"QLabel {{ color:{fg}; background:{bg}; border:1px solid {br}; "
            f"border-radius:10px; padding:2px 10px; font-size:11px; font-weight:bold; }}"
        )

    def _set_chip_states(states):
        for name, chip in dep_chips.items():
            st = states.get(name, "neutral")
            mark = {"ok": "✓ ", "missing": "✗ ", "neutral": ""}.get(st, "")
            chip.setText(mark + name)
            chip.setStyleSheet(_chip_style(st))

    _set_chip_states({})

    dialog.mz_deps_hint = _hint(
        _tr("scikit-learn installs automatically on first run; pandas and scipy ship with QGIS.")
    )
    lay.addWidget(dialog.mz_deps_hint)

    row = QHBoxLayout()
    dialog.mz_btn_deps_install = _primary(QPushButton(_tr("Install dependencies")))
    dialog.mz_btn_deps_recheck = _secondary(QPushButton(_tr("Recheck")))
    dialog.mz_btn_deps_manual = _secondary(QPushButton(_tr("Manual install…")))
    row.addWidget(dialog.mz_btn_deps_install)
    row.addWidget(dialog.mz_btn_deps_recheck)
    row.addWidget(dialog.mz_btn_deps_manual)
    row.addStretch()
    lay.addLayout(row)

    def _set_dep_status(imports):
        """imports: {display_name: bool}."""
        _set_chip_states({n: ("ok" if ok else "missing") for n, ok in imports.items()})
        py_ok = all(imports.values()) if imports else False
        dialog.mz_btn_deps_install.setVisible(not py_ok)

    def _set_deps_installing(busy):
        dialog.mz_btn_deps_install.setEnabled(not busy)
        dialog.mz_btn_deps_install.setText(
            _tr("Installing…") if busy else _tr("Install dependencies")
        )

    dialog.mz_set_dep_status = _set_dep_status
    dialog.mz_set_deps_installing = _set_deps_installing

    def _show_manual_install():
        dlg = QDialog(dialog)
        dlg.setWindowTitle(_tr("Manual installation"))
        dlg.resize(520, 240)
        v = QVBoxLayout(dlg)
        v.addWidget(
            QLabel(
                _tr(
                    "If automatic install fails, run this in the OSGeo4W Shell "
                    "(Windows) or your QGIS Python environment:"
                )
            )
        )
        cmd = QPlainTextEdit("python -m pip install scikit-learn")
        cmd.setReadOnly(True)
        cmd.setFixedHeight(52)
        v.addWidget(cmd)
        copy = _secondary(QPushButton(_tr("Copy command")))
        copy.clicked.connect(
            lambda: QGuiApplication.clipboard().setText(cmd.toPlainText())
        )
        v.addWidget(copy)
        v.addStretch()
        btn_row = QHBoxLayout()
        btn_row.addStretch()
        close = _secondary(QPushButton(_tr("Close")))
        close.clicked.connect(dlg.accept)
        btn_row.addWidget(close)
        v.addLayout(btn_row)
        dlg.exec()

    dialog.mz_btn_deps_manual.clicked.connect(_show_manual_install)

    lay.addStretch(1)


# ---------------------------------------------------------------------- data
def _build_data_tab(dialog, parent):
    lay = _scroll_tab(parent)

    p = _panel(lay)
    p.addWidget(_field_label(_tr("FIELD BOUNDARY")))
    dialog.mz_vector_combo = _prepare_field(QgsMapLayerComboBox())
    dialog.mz_vector_combo.setFilters(QgsMapLayerProxyModel.PolygonLayer)
    dialog.mz_vector_combo.setToolTip(
        _tr(
            "Polygon layer outlining the field. Any CRS — a geographic boundary "
            "is auto-reprojected to its UTM zone."
        )
    )
    p.addWidget(dialog.mz_vector_combo)
    p.addWidget(_hint(_tr("Polygon outline of the field (any CRS).")))

    p = _panel(lay)
    p.addWidget(_field_label(_tr("INPUT RASTERS")))
    dialog.mz_raster_list = QListWidget()
    dialog.mz_raster_list.setSelectionMode(
        QAbstractItemView.SelectionMode.ExtendedSelection
    )
    dialog.mz_raster_list.setMinimumHeight(140)
    dialog.mz_raster_list.setStyleSheet(
        "QListWidget { background: #ffffff; border: 1px solid #d0d0d0;"
        " border-radius: 6px; font-size: 12px; }"
        "QListWidget::item:selected { background: #e8f5e9; color: #1a1a1a; }"
    )
    dialog.mz_raster_list.setToolTip(
        _tr("Pick one or more rasters to combine. Hold Ctrl or Shift to multi-select.")
    )
    p.addWidget(dialog.mz_raster_list)
    p.addWidget(_hint(_tr("Select one or more — Ctrl/Shift for multiple.")))

    p = _panel(lay)
    p.addWidget(_field_label(_tr("RESOLUTION (M)")))
    dialog.mz_resolution_input = _prepare_field(QLineEdit())
    dialog.mz_resolution_input.setPlaceholderText(_tr("e.g. 10"))
    dialog.mz_resolution_input.setToolTip(
        _tr("Output pixel size in meters. Match your highest-resolution raster.")
    )
    p.addWidget(dialog.mz_resolution_input)
    p.addWidget(
        _hint(_tr("Output pixel size in meters; use your finest raster as reference."))
    )

    dialog.mz_btn_resample = _primary(
        QPushButton(_tr("Run resampling and extract values"))
    )
    lay.addWidget(dialog.mz_btn_resample)
    lay.addStretch(1)

    def _refresh_rasters():
        """Rebuild the raster list from the project, preserving selection."""
        selected = {i.text() for i in dialog.mz_raster_list.selectedItems()}
        dialog.mz_raster_list.clear()
        for layer in QgsProject.instance().mapLayers().values():
            if isinstance(layer, QgsRasterLayer):
                dialog.mz_raster_list.addItem(layer.name())
        for i in range(dialog.mz_raster_list.count()):
            item = dialog.mz_raster_list.item(i)
            if item.text() in selected:
                item.setSelected(True)

    dialog.mz_refresh_rasters = _refresh_rasters


# ----------------------------------------------------------------------- pca
def _build_pca_tab(dialog, parent):
    lay = _scroll_tab(parent)

    p = _panel(lay)
    p.addWidget(_field_label(_tr("PRINCIPAL COMPONENT ANALYSIS")))
    dialog.mz_btn_run_pca = _primary(QPushButton(_tr("Run PCA")))
    p.addWidget(dialog.mz_btn_run_pca)

    dialog.mz_pca_table = QTableWidget()
    dialog.mz_pca_table.setColumnCount(4)
    dialog.mz_pca_table.setHorizontalHeaderLabels(
        [_tr("Component"), _tr("Eigenvalue (λ)"), _tr("Variance (%)"), _tr("Cumulative (%)")]
    )
    dialog.mz_pca_table.setMinimumHeight(180)
    p.addWidget(dialog.mz_pca_table)

    p = _panel(lay)
    p.addWidget(_field_label(_tr("EXPORT")))
    dialog.mz_btn_export_folder = _secondary(QPushButton(_tr("Choose folder to save")))
    p.addWidget(dialog.mz_btn_export_folder)
    dialog.mz_export_path_lbl = _hint(_tr("No folder selected"))
    p.addWidget(dialog.mz_export_path_lbl)
    dialog.mz_btn_export_report = _secondary(QPushButton(_tr("Export full report (CSV)")))
    p.addWidget(dialog.mz_btn_export_report)

    p.addWidget(_make_divider())
    grp = QGroupBox(_tr("Export PCs as raster"))
    grp.setStyleSheet(
        "QGroupBox { font-size: 12px; color: #616161; border: 1px solid #e0e0e0;"
        " border-radius: 6px; margin-top: 8px; padding-top: 6px; }"
        "QGroupBox::title { subcontrol-origin: margin; left: 8px; padding: 0 4px; }"
    )
    gl = QHBoxLayout(grp)
    gl.addWidget(_field_label(_tr("CHOOSE PC:")))
    dialog.mz_pc_export_combo = QComboBox()
    dialog.mz_pc_export_combo.setEnabled(False)
    dialog.mz_pc_export_combo.setToolTip(
        _tr("Principal component to write as a single-band raster.")
    )
    gl.addWidget(dialog.mz_pc_export_combo)
    dialog.mz_btn_export_pc = _secondary(QPushButton(_tr("Export selected PC (GeoTIFF)")))
    gl.addWidget(dialog.mz_btn_export_pc)
    dialog.mz_btn_export_all_pcs = _secondary(QPushButton(_tr("Export all PCs (multi-band)")))
    gl.addWidget(dialog.mz_btn_export_all_pcs)
    p.addWidget(grp)
    lay.addStretch(1)


# --------------------------------------------------------------------- zones
def _build_zones_tab(dialog, parent):
    lay = _scroll_tab(parent)

    p = _panel(lay)
    p.addWidget(_field_label(_tr("DATA SOURCE FOR CLUSTERING")))
    dialog.mz_rad_pca = QRadioButton(_tr("PCA (selected components)"))
    dialog.mz_rad_orig = QRadioButton(_tr("Original variables (z-score)"))
    dialog.mz_rad_pca.setChecked(True)
    p.addWidget(dialog.mz_rad_pca)
    p.addWidget(dialog.mz_rad_orig)

    pc_row = QHBoxLayout()
    dialog.mz_pc_selector_lbl = QLabel(_tr("Number of PCs to use:"))
    dialog.mz_pc_selector_lbl.setStyleSheet(
        "color: #616161; font-size: 12px; background: transparent;"
    )
    pc_row.addWidget(dialog.mz_pc_selector_lbl)
    dialog.mz_pc_selector = QComboBox()
    dialog.mz_pc_selector.setToolTip(
        _tr("How many principal components feed the clustering.")
    )
    pc_row.addWidget(dialog.mz_pc_selector)
    pc_row.addStretch()
    p.addLayout(pc_row)

    def _toggle_pc_selector(pca_active):
        dialog.mz_pc_selector.setEnabled(bool(pca_active))
        dialog.mz_pc_selector_lbl.setEnabled(bool(pca_active))

    dialog.mz_rad_pca.toggled.connect(_toggle_pc_selector)
    _toggle_pc_selector(True)

    p = _panel(lay)
    p.addWidget(_field_label(_tr("CLUSTER EVALUATION (ELBOW + SILHOUETTE)")))
    range_row = QHBoxLayout()
    range_row.setSpacing(8)
    range_row.addWidget(QLabel(_tr("Min clusters:")))
    dialog.mz_kmin_spin = QSpinBox()
    dialog.mz_kmin_spin.setRange(2, 20)
    dialog.mz_kmin_spin.setValue(2)
    dialog.mz_kmin_spin.setToolTip(_tr("Smallest number of clusters (k) to evaluate."))
    range_row.addWidget(dialog.mz_kmin_spin)
    range_row.addWidget(QLabel(_tr("Max clusters:")))
    dialog.mz_kmax_spin = QSpinBox()
    dialog.mz_kmax_spin.setRange(2, 20)
    dialog.mz_kmax_spin.setValue(10)
    dialog.mz_kmax_spin.setToolTip(_tr("Largest number of clusters (k) to evaluate."))
    range_row.addWidget(dialog.mz_kmax_spin)
    range_row.addStretch()
    p.addLayout(range_row)
    p.addWidget(_hint(_tr("Evaluates every k in this range with Elbow + Silhouette.")))

    dialog.mz_btn_run_elbow = _primary(
        QPushButton(_tr("Run zones analysis (KMeans + Elbow + Silhouette)"))
    )
    p.addWidget(dialog.mz_btn_run_elbow)

    dialog.mz_indices_table = QTableWidget()
    dialog.mz_indices_table.setColumnCount(3)
    dialog.mz_indices_table.setHorizontalHeaderLabels(
        [_tr("Clusters"), _tr("Inertia"), _tr("Silhouette")]
    )
    dialog.mz_indices_table.setMinimumHeight(120)
    p.addWidget(dialog.mz_indices_table)

    dialog.mz_elbow_canvas = FigureCanvas(Figure(figsize=(4, 2)))
    dialog.mz_elbow_canvas.setMinimumHeight(220)
    p.addWidget(dialog.mz_elbow_canvas)
    dialog.mz_elbow_axes = dialog.mz_elbow_canvas.figure.add_subplot(111)

    export_row = QHBoxLayout()
    dialog.mz_btn_export_elbow_png = _secondary(
        QPushButton(_tr("Export plot (Elbow + Silhouette) [PNG]"))
    )
    export_row.addWidget(dialog.mz_btn_export_elbow_png)
    dialog.mz_btn_export_elbow_csv = _secondary(
        QPushButton(_tr("Export results (Elbow + Silhouette) [CSV]"))
    )
    export_row.addWidget(dialog.mz_btn_export_elbow_csv)
    export_row.addStretch()
    p.addLayout(export_row)

    p = _panel(lay)
    p.addWidget(_field_label(_tr("GENERATE ZONES")))
    final_row = QHBoxLayout()
    final_row.addWidget(QLabel(_tr("Number of zones to generate (KMeans):")))
    dialog.mz_final_k_spin = QSpinBox()
    dialog.mz_final_k_spin.setRange(2, 20)
    dialog.mz_final_k_spin.setValue(3)
    dialog.mz_final_k_spin.setToolTip(
        _tr("Final k — the number of management zones in the output raster.")
    )
    final_row.addWidget(dialog.mz_final_k_spin)
    final_row.addStretch()
    p.addLayout(final_row)
    p.addWidget(_hint(_tr("Pick k from the Elbow/Silhouette results above.")))
    dialog.mz_btn_generate_zones = _primary(
        QPushButton(_tr("Generate management zones (as raster)"))
    )
    p.addWidget(dialog.mz_btn_generate_zones)
    lay.addStretch(1)

    def _populate_pc_combos(n_components):
        """Fill mz_pc_export_combo (PCA tab) and mz_pc_selector after PCA."""
        try:
            dialog.mz_pc_export_combo.clear()
            for i in range(n_components):
                dialog.mz_pc_export_combo.addItem(f"PC{i + 1}", i)  # data = 0-based
            dialog.mz_pc_export_combo.setEnabled(dialog.mz_pc_export_combo.count() > 0)
            if dialog.mz_pc_export_combo.count() > 0:
                dialog.mz_pc_export_combo.setCurrentIndex(0)

            dialog.mz_pc_selector.clear()
            for i in range(1, n_components + 1):
                dialog.mz_pc_selector.addItem(str(i))
            _toggle_pc_selector(dialog.mz_rad_pca.isChecked())
            if dialog.mz_pc_selector.count() > 0:
                dialog.mz_pc_selector.setCurrentIndex(0)
        except Exception:
            pass

    dialog.mz_populate_pc_combos = _populate_pc_combos


# -------------------------------------------------------------------- filter
def _build_filter_tab(dialog, parent):
    lay = _scroll_tab(parent)

    p = _panel(lay)
    p.addWidget(_field_label(_tr("ZONES RASTER TO SMOOTH")))
    dialog.mz_filter_raster_combo = _prepare_field(QgsMapLayerComboBox())
    dialog.mz_filter_raster_combo.setFilters(QgsMapLayerProxyModel.RasterLayer)
    dialog.mz_filter_raster_combo.setToolTip(
        _tr("The management-zones raster to smooth (e.g. one just generated).")
    )
    p.addWidget(dialog.mz_filter_raster_combo)

    p.addWidget(_field_label(_tr("WINDOW SIZE")))
    dialog.mz_window_spin = QSpinBox()
    dialog.mz_window_spin.setRange(3, 99)
    dialog.mz_window_spin.setSingleStep(2)
    dialog.mz_window_spin.setValue(5)
    dialog.mz_window_spin.setToolTip(
        _tr("Filter radius in pixels; larger = smoother, fewer speckles.")
    )
    p.addWidget(dialog.mz_window_spin)
    p.addWidget(_hint(_tr("Window size: 3 = 7x7 pixels, 5 = 11x11 pixels, etc.")))

    dialog.mz_btn_run_filter = _primary(QPushButton(_tr("Run Mode Filter")))
    lay.addWidget(dialog.mz_btn_run_filter)
    lay.addStretch(1)


# ------------------------------------------------------------------ analysis
def _build_analysis_tab(dialog, parent):
    lay = _scroll_tab(parent)

    p = _panel(lay)
    p.addWidget(_field_label(_tr("ZONES RASTER (ALREADY IN QGIS)")))
    dialog.mz_analysis_raster_combo = _prepare_field(QgsMapLayerComboBox())
    dialog.mz_analysis_raster_combo.setFilters(QgsMapLayerProxyModel.RasterLayer)
    dialog.mz_analysis_raster_combo.setToolTip(
        _tr("Zones raster to summarize per zone.")
    )
    p.addWidget(dialog.mz_analysis_raster_combo)

    dialog.mz_vr_lbl = QLabel("VR: -")
    dialog.mz_vr_lbl.setStyleSheet(
        "font-weight: bold; color: #37474F; background: transparent;"
    )
    p.addWidget(dialog.mz_vr_lbl)

    dialog.mz_result_table = QTableWidget()
    dialog.mz_result_table.setColumnCount(5)
    dialog.mz_result_table.setHorizontalHeaderLabels(
        [_tr("Zone"), _tr("Mean"), _tr("Variance"), "n", _tr("Area (ha)")]
    )
    dialog.mz_result_table.setMinimumHeight(140)
    p.addWidget(dialog.mz_result_table)

    p = _panel(lay)
    p.addWidget(_field_label(_tr("EXTERNAL DATA (OPTIONAL)")))
    dialog.mz_btn_load_csv = _secondary(QPushButton(_tr("Load points CSV")))
    dialog.mz_btn_load_csv.setToolTip(
        _tr("CSV with coordinate columns and the attribute to analyze.")
    )
    p.addWidget(dialog.mz_btn_load_csv)
    p.addWidget(_hint(_tr("Map the CSV columns below after loading.")))

    p.addWidget(_field_label(_tr("X COLUMN (LONGITUDE)")))
    dialog.mz_col_x_combo = QComboBox()
    dialog.mz_col_x_combo.setToolTip(
        _tr("CSV column holding the X / longitude coordinate.")
    )
    p.addWidget(dialog.mz_col_x_combo)
    p.addWidget(_field_label(_tr("Y COLUMN (LATITUDE)")))
    dialog.mz_col_y_combo = QComboBox()
    dialog.mz_col_y_combo.setToolTip(
        _tr("CSV column holding the Y / latitude coordinate.")
    )
    p.addWidget(dialog.mz_col_y_combo)
    p.addWidget(_field_label(_tr("ATTRIBUTE COLUMN")))
    dialog.mz_col_attr_combo = QComboBox()
    dialog.mz_col_attr_combo.setToolTip(
        _tr("CSV column with the numeric value to summarize per zone.")
    )
    p.addWidget(dialog.mz_col_attr_combo)

    dialog.mz_btn_run_analysis = _primary(QPushButton(_tr("Run Variance Reduction")))
    lay.addWidget(dialog.mz_btn_run_analysis)
    dialog.mz_btn_export_boxplots = _secondary(QPushButton(_tr("Export boxplots (PNG)")))
    lay.addWidget(dialog.mz_btn_export_boxplots)
    lay.addStretch(1)


# ---------------------------------------------------------------------- page
def setup_mzones_page(dialog, page):
    """
    Populate the Management Zones page with a six-tab layout.

    Exposes on dialog:
      mz_vector_combo, mz_raster_list, mz_resolution_input, mz_btn_resample,
      mz_btn_run_pca, mz_pca_table, mz_btn_export_folder, mz_export_path_lbl,
      mz_btn_export_report, mz_pc_export_combo, mz_btn_export_pc,
      mz_btn_export_all_pcs,
      mz_rad_pca, mz_rad_orig, mz_pc_selector, mz_kmin_spin, mz_kmax_spin,
      mz_btn_run_elbow, mz_indices_table, mz_elbow_canvas, mz_elbow_axes,
      mz_btn_export_elbow_png, mz_btn_export_elbow_csv, mz_final_k_spin,
      mz_btn_generate_zones,
      mz_filter_raster_combo, mz_window_spin, mz_btn_run_filter,
      mz_analysis_raster_combo, mz_vr_lbl, mz_result_table, mz_btn_load_csv,
      mz_col_x_combo, mz_col_y_combo, mz_col_attr_combo, mz_btn_run_analysis,
      mz_btn_export_boxplots,
      mz_btn_deps_install, mz_btn_deps_recheck, mz_btn_deps_manual,
      mz_set_dep_status, mz_set_deps_installing,
      mz_stack, mz_set_tab, mz_btn_back, mz_btn_next, mz_step_lbl,
      mz_refresh_rasters, mz_populate_pc_combos
    """
    page.setObjectName("mzonesPage")
    page.setStyleSheet("""
        QWidget#mzonesPage { background-color: #ffffff; }
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
        QRadioButton { color: #212121; font-size: 12px; background: transparent; }
        QTableWidget {
            background-color: #ffffff;
            color: #212121;
            border: 1px solid #d0d0d0;
            border-radius: 6px;
            gridline-color: #eeeeee;
            font-size: 12px;
        }
        QHeaderView::section {
            background-color: #f8f9fa;
            color: #616161;
            border: none;
            border-bottom: 1px solid #e0e0e0;
            padding: 4px 6px;
            font-size: 11px;
        }
    """)

    outer = QVBoxLayout(page)
    outer.setContentsMargins(0, 0, 0, 0)
    outer.setSpacing(0)

    tab_bar = QFrame()
    tab_bar.setObjectName("mzonesTabBar")
    tab_bar.setFixedHeight(40)
    tab_bar.setStyleSheet("""
        QFrame#mzonesTabBar {
            background-color: #f8f9fa;
            border-bottom: 1px solid #e0e0e0;
        }
    """)
    tab_bar_lay = QHBoxLayout(tab_bar)
    tab_bar_lay.setContentsMargins(6, 0, 6, 0)
    tab_bar_lay.setSpacing(8)

    tab_labels = [
        _tr("Intro"),
        _tr("Data"),
        _tr("PCA"),
        _tr("Zones"),
        _tr("Filter"),
        _tr("Analysis"),
    ]
    tab_buttons = []
    for label in tab_labels:
        btn = QPushButton(label)
        btn.setFixedHeight(40)
        btn.setCursor(Qt.CursorShape.PointingHandCursor)
        tab_bar_lay.addWidget(btn)
        tab_buttons.append(btn)
    tab_bar_lay.addStretch(1)
    outer.addWidget(tab_bar)

    stack = QStackedWidget()
    stack.setStyleSheet("QStackedWidget { background: transparent; border: none; }")

    builders = (
        _build_intro_tab,
        _build_data_tab,
        _build_pca_tab,
        _build_zones_tab,
        _build_filter_tab,
        _build_analysis_tab,
    )
    for build in builders:
        tab_page = QWidget()
        build(dialog, tab_page)
        stack.addWidget(tab_page)

    outer.addWidget(stack, 1)
    dialog.mz_stack = stack

    nav_bar = QFrame()
    nav_bar.setObjectName("mzonesNavBar")
    nav_bar.setFixedHeight(46)
    nav_bar.setStyleSheet("""
        QFrame#mzonesNavBar {
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

    dialog.mz_btn_back = btn_back
    dialog.mz_btn_next = btn_next
    dialog.mz_step_lbl = step_lbl

    n_tabs = len(tab_buttons)

    def _set_tab(index):
        stack.setCurrentIndex(index)
        btn_back.setEnabled(index > 0)
        btn_next.setEnabled(index < n_tabs - 1)
        step_lbl.setText(_tr("Step %d of %d") % (index + 1, n_tabs))
        for i, btn in enumerate(tab_buttons):
            btn.setStyleSheet(_TAB_ACTIVE if i == index else _TAB_INACTIVE)
        if index == 1:  # Data tab: sync the multi-select list with the project
            dialog.mz_refresh_rasters()

    dialog.mz_set_tab = _set_tab

    for i, btn in enumerate(tab_buttons):
        btn.clicked.connect(lambda _=False, idx=i: _set_tab(idx))
    btn_next.clicked.connect(
        lambda: _set_tab(stack.currentIndex() + 1)
        if stack.currentIndex() < n_tabs - 1
        else None
    )
    btn_back.clicked.connect(
        lambda: _set_tab(stack.currentIndex() - 1) if stack.currentIndex() > 0 else None
    )

    _set_tab(0)
