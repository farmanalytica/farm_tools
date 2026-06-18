# -*- coding: utf-8 -*-
"""
ClimaPlots page for the RAVI dialog.

Builds the climate-analysis page as five tabs (About | Coordinates | Trends |
Thermo-pluviometric | Climate Indices), mirroring the hand-built tab idiom of
``view/optical.py``. Signal connections are wired externally by
``farm_tools.py`` and ``climaplots_ctrl.py``.
"""

import datetime

from qgis.PyQt.QtCore import QCoreApplication, Qt
from qgis.PyQt.QtGui import QDoubleValidator
from qgis.PyQt.QtWidgets import (
    QComboBox,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QSpinBox,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from .radar import (
    _TAB_ACTIVE,
    _TAB_INACTIVE,
)
from . import plotly_render
from .styles import STYLE_BTN_PRIMARY, STYLE_BTN_SECONDARY
from .webcompat import QWebView


def _tr(text):
    return QCoreApplication.translate("RAVI", text)


_MIN_YEAR = 1981
_MAX_YEAR = datetime.date.today().year - 1

_VARIABLES = [
    "Max Temperature",
    "Min Temperature",
    "Precipitation",
    "Relative Humidity",
    "Irradiation",
    "Wind Speed",
    "Reference ET0",
    "Growing Degree Days",
]
_INDICES = [
    "Annual Summer Days",
    "Annual Frost Days",
    "Annual Tropical Nights",
    "Annual Icing Days",
    "Monthly Maximum Temperature",
    "Monthly Minimum Temperature of Maximum Temperatures",
    "Monthly Maximum Temperature of Minimum Temperatures",
    "Monthly Minimum Temperature",
    "Daily Temperature Range",
    "Monthly Maximum 1-day Precipitation",
    "Monthly Maximum 5-day Precipitation",
    "Annual Count of Days when Precipitation Exceeds 10mm",
    "Annual Count of Days when Precipitation Exceeds 20mm",
    "Simple Precipitation Intensity Index",
    "Number of Consecutive Dry Days in a Month",
    "Number of Consecutive Wet Days in a Month",
    "The Standardized Precipitation Index (SPI)",
]

# Short, one-line explanations shown under the dropdown when an item is picked.
VARIABLE_DESC = {
    "Max Temperature": "Daily maximum air temperature at 2 m (°C).",
    "Min Temperature": "Daily minimum air temperature at 2 m (°C).",
    "Precipitation": "Daily total precipitation (mm).",
    "Relative Humidity": "Mean relative humidity at 2 m (%).",
    "Irradiation": "All-sky surface shortwave irradiation (kWh/m²/day).",
    "Wind Speed": "Mean wind speed at 2 m (m/s).",
    "Reference ET0": "Reference evapotranspiration, Hargreaves method (mm).",
    "Growing Degree Days": "Heat accumulation above a 10 °C base (°C·day).",
}
INDEX_DESC = {
    "Annual Summer Days": "Annual count of days with Tmax > 25 °C.",
    "Annual Frost Days": "Annual count of days with Tmin < 0 °C.",
    "Annual Tropical Nights": "Annual count of nights with Tmin > 20 °C.",
    "Annual Icing Days": "Annual count of days with Tmax < 0 °C.",
    "Monthly Maximum Temperature": "Monthly highest daily maximum temperature (TXx).",
    "Monthly Minimum Temperature of Maximum Temperatures": "Monthly lowest daily maximum temperature (TXn).",
    "Monthly Maximum Temperature of Minimum Temperatures": "Monthly highest daily minimum temperature (TNx).",
    "Monthly Minimum Temperature": "Monthly lowest daily minimum temperature (TNn).",
    "Daily Temperature Range": "Mean difference between daily max and min (DTR).",
    "Monthly Maximum 1-day Precipitation": "Highest 1-day precipitation each month (Rx1day).",
    "Monthly Maximum 5-day Precipitation": "Highest 5-day precipitation total each month (Rx5day).",
    "Annual Count of Days when Precipitation Exceeds 10mm": "Annual count of days with ≥ 10 mm (R10mm).",
    "Annual Count of Days when Precipitation Exceeds 20mm": "Annual count of days with ≥ 20 mm (R20mm).",
    "Simple Precipitation Intensity Index": "Mean precipitation on wet days (SDII).",
    "Number of Consecutive Dry Days in a Month": "Longest dry spell each month (CDD).",
    "Number of Consecutive Wet Days in a Month": "Longest wet spell each month (CWD).",
    "The Standardized Precipitation Index (SPI)": "90-day standardized precipitation anomaly (SPI).",
}


def variable_description(name):
    return VARIABLE_DESC.get(name, "")


def index_description(name):
    return INDEX_DESC.get(name, "")


# Labels for the checkable "pick point" toggles (idle / capturing).
PICK_TEXT_OFF = "📍  Pick a point on the map"
PICK_TEXT_ON = "📍  Click the map…  (click here to cancel)"
PICK_B_OFF = "📍  Pick comparison point B"
PICK_B_ON = "📍  Click the map for B…  (click here to cancel)"

_FIELD_LABEL_STYLE = (
    "color: #9e9e9e; font-size: 11px; font-weight: bold; letter-spacing: 1px;"
    "background: transparent;"
)


def _button(text, tooltip="", style=STYLE_BTN_SECONDARY, height=28):
    """Create a styled button with a consistent height and cursor."""
    btn = QPushButton(text)
    btn.setStyleSheet(style)
    btn.setCursor(Qt.CursorShape.PointingHandCursor)
    if tooltip:
        btn.setToolTip(tooltip)
    btn.setFixedHeight(height)
    return btn


def _combo(items, tooltip="", min_width=220):
    """Create a dropdown with a consistent size and cursor."""
    cb = QComboBox()
    cb.addItems(items)
    if tooltip:
        cb.setToolTip(tooltip)
    cb.setMinimumWidth(min_width)
    cb.setMinimumHeight(28)
    cb.setCursor(Qt.CursorShape.PointingHandCursor)
    return cb


class _ResizingWebView(QWebView):
    """Web view that re-fits its plotly chart to the widget size.

    The page carries a ``window.onresize`` handler + plotly ``responsive``
    config, but under QtWebEngine (QGIS 4 / Qt6) the chart's CSS ``height:100%``
    does not resolve against the embedded viewport, so plotly falls back to its
    default ~450 px and the plot looks pinned to a fixed height regardless of
    the plugin size. Instead of relying on the container, push the widget's
    exact pixel size into the figure with ``Plotly.relayout`` whenever the
    widget resizes — and once more on ``loadFinished``, since the page loads
    asynchronously and the first ``resizeEvent`` fires before ``Plotly`` exists.
    The JS is a no-op until a chart is loaded (``run_js`` swallows errors).
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # don't let the view impose a minimum height on the dialog
        self.setMinimumSize(0, 0)
        self.loadFinished.connect(lambda _ok=False: self._fit_chart())

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._fit_chart()

    def _fit_chart(self):
        size = self.size()
        plotly_render.run_js(
            self,
            "if(window.Plotly){Plotly.relayout('chart',{width:%d,height:%d});}"
            % (size.width(), size.height()),
        )


def _make_webview():
    view = _ResizingWebView()
    view.setFocusPolicy(Qt.FocusPolicy.NoFocus)
    view.setContextMenuPolicy(Qt.ContextMenuPolicy.NoContextMenu)
    view.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
    return view


def _field_label(text):
    lbl = QLabel(text)
    lbl.setStyleSheet(_FIELD_LABEL_STYLE)
    return lbl


def setup_climaplots_page(dialog, page):
    """
    Populate the ClimaPlots page with a five-tab layout.

    Exposes on dialog (cp_* prefix): cp_stack, cp_set_tab,
    cp_btn_get_started, cp_source_combo_a/_b, cp_lon_a/cp_lat_a/cp_lon_b/
    cp_lat_b, cp_btn_pick_a/_b, cp_btn_copy_a_to_b, cp_btn_clear_marker,
    cp_btn_hybrid_layer, cp_start_year/cp_end_year, cp_btn_run, cp_var_combo/
    cp_var_desc, cp_index_combo/cp_index_desc, cp_web_trends/_thermo/_indices,
    cp_btn_browser_*/cp_btn_csv_*/cp_btn_png_*, cp_btn_csv_raw,
    cp_btn_export_all.
    """
    page.setObjectName("climaplotsPage")
    page.setStyleSheet("""
        QWidget#climaplotsPage { background-color: #ffffff; }
        QLabel { background: transparent; border: none; }
        QComboBox {
            background-color: #ffffff;
            color: #212121;
            border: 1px solid #d0d0d0;
            border-radius: 6px;
            padding: 3px 8px;
            font-size: 12px;
        }
        QComboBox:focus { border: 1.5px solid #1b6b39; }
        QComboBox QAbstractItemView {
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
        QLineEdit:focus { border-color: #1b6b39; }
        QSpinBox {
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
    tab_bar.setObjectName("climaplotsTabBar")
    tab_bar.setFixedHeight(40)
    tab_bar.setStyleSheet("""
        QFrame#climaplotsTabBar {
            background-color: #f8f9fa;
            border-bottom: 1px solid #e0e0e0;
        }
    """)
    tab_bar_lay = QHBoxLayout(tab_bar)
    tab_bar_lay.setContentsMargins(6, 0, 6, 0)
    tab_bar_lay.setSpacing(8)

    tab_buttons = []
    for label in (
        _tr("Intro"),
        _tr("Coordinates"),
        _tr("Trends"),
        _tr("Thermo-pluviometric"),
        _tr("Climate Indices"),
    ):
        btn = QPushButton(label)
        btn.setFixedHeight(40)
        btn.setCursor(Qt.CursorShape.PointingHandCursor)
        tab_bar_lay.addWidget(btn)
        tab_buttons.append(btn)
    tab_bar_lay.addStretch(1)
    outer.addWidget(tab_bar)

    stack = QStackedWidget()
    stack.setStyleSheet("QStackedWidget { background: transparent; border: none; }")

    about_page = QWidget()
    _build_about_tab(dialog, about_page)
    stack.addWidget(about_page)

    coords_page = QWidget()
    _build_coords_tab(dialog, coords_page)
    stack.addWidget(coords_page)

    trends_page = QWidget()
    _build_trends_tab(dialog, trends_page)
    stack.addWidget(trends_page)

    thermo_page = QWidget()
    _build_thermo_tab(dialog, thermo_page)
    stack.addWidget(thermo_page)

    indices_page = QWidget()
    _build_indices_tab(dialog, indices_page)
    stack.addWidget(indices_page)

    outer.addWidget(stack, 1)
    dialog.cp_stack = stack

    def _set_tab(index):
        stack.setCurrentIndex(index)
        for i, btn in enumerate(tab_buttons):
            btn.setStyleSheet(_TAB_ACTIVE if i == index else _TAB_INACTIVE)

    dialog.cp_set_tab = _set_tab

    for i, btn in enumerate(tab_buttons):
        btn.clicked.connect(lambda _checked=False, index=i: _set_tab(index))
    dialog.cp_btn_get_started.clicked.connect(lambda: _set_tab(1))

    _set_tab(0)


# --------------------------------------------------------------------- about
def _about_label(html, style=""):
    lbl = QLabel(html)
    lbl.setWordWrap(True)
    lbl.setOpenExternalLinks(True)
    lbl.setTextFormat(Qt.TextFormat.RichText)
    if style:
        lbl.setStyleSheet(style)
    return lbl


def _build_about_tab(dialog, page):
    """Native-widget intro explaining the ClimaPlots module (no WebView)."""
    page.setObjectName("cpAboutTab")
    page.setStyleSheet("QWidget#cpAboutTab { background-color: #ffffff; }")

    outer = QVBoxLayout(page)
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
        return _about_label(
            text, "font-size:15px;font-weight:bold;color:#1b6b39;margin-bottom:4px;"
        )

    def _h2(text):
        return _about_label(
            text,
            "font-size:12px;font-weight:bold;color:#2a5d84;"
            "padding-bottom:3px;margin-top:12px;margin-bottom:2px;",
        )

    def _para(html):
        return _about_label(html, "font-size:12px;color:#333;")

    def _divider():
        line = QFrame()
        line.setFrameShape(QFrame.Shape.HLine)
        line.setStyleSheet("color:#e6f2fa;")
        return line

    lay.addWidget(_h1(_tr("🌦️ ClimaPlots")))
    lay.addSpacing(2)
    lay.addWidget(
        _para(
            _tr(
                "ClimaPlots fetches decades of daily climate data for any point on "
                "the map and turns it into interactive charts — no coding required. "
                "Choose between two data sources: <b>NASA POWER</b> (from 1981) and "
                "<b>Open-Meteo (ERA5)</b> (from 1940)."
            )
        )
    )

    lay.addWidget(_h2(_tr("📊 What it produces")))
    lay.addWidget(_divider())
    lay.addWidget(
        _para(
            _tr(
                "<b>Annual trends</b> for temperature, precipitation, relative "
                "humidity, irradiation, wind speed, reference ET₀ and growing degree "
                "days, each annotated with <b>Mann–Kendall</b> trend and "
                "<b>Pettitt</b> homogeneity tests."
            )
        )
    )
    lay.addWidget(
        _para(
            _tr(
                "<b>Thermo-pluviometric diagram</b> — the mean monthly precipitation "
                "and temperature regime of the location."
            )
        )
    )
    lay.addWidget(
        _para(
            _tr(
                "<b>Climate indices</b> — ETCCDI temperature and precipitation "
                "indices plus the Standardized Precipitation Index (SPI)."
            )
        )
    )

    lay.addWidget(_h2(_tr("🔀 Compare two locations or two sources")))
    lay.addWidget(_divider())
    lay.addWidget(
        _para(
            _tr(
                "Add an optional <b>comparison point B</b> to overlay a second series "
                "on the Trends chart, with trend statistics reported for both points. "
                "B can use its own data source, so the <i>same</i> location can be "
                "compared across NASA POWER and Open-Meteo — use <b>Same location as "
                "A</b> to copy point A's coordinates without re-clicking the map."
            )
        )
    )

    lay.addWidget(_h2(_tr("🚀 Quick start")))
    lay.addWidget(_divider())
    qs_frame = QFrame()
    qs_frame.setStyleSheet("QFrame{background:#f0f8ff;border-radius:4px;padding:4px;}")
    qs_lay = QVBoxLayout(qs_frame)
    qs_lay.setContentsMargins(12, 6, 12, 6)
    qs_lay.setSpacing(4)
    for i, text in enumerate(
        [
            _tr("Open the <b>Coordinates</b> tab and pick a <b>data source</b>."),
            _tr(
                "Click <b>Pick a point on the map</b> and click a location on the "
                "canvas (or type the longitude/latitude manually)."
            ),
            _tr(
                "Optionally set a <b>comparison point B</b> — pick it on the map, or "
                "press <b>Same location as A</b>."
            ),
            _tr("Press <b>Run analysis</b> and wait while the data is downloaded."),
            _tr(
                "Browse the <b>Trends</b>, <b>Thermo-pluviometric</b> and "
                "<b>Climate Indices</b> tabs. Use <b>Open in browser</b> for a "
                "full-screen chart, or <b>Save chart data</b> to export a CSV."
            ),
        ],
        1,
    ):
        qs_lay.addWidget(_para(f"{i}. {text}"))
    lay.addWidget(qs_frame)
    lay.addWidget(
        _para(
            _tr(
                "Behind a corporate network? Set a proxy via <b>Proxy settings</b> in "
                "the authentication page."
            )
        )
    )

    lay.addWidget(_h2(_tr("📖 Citation")))
    lay.addWidget(_divider())
    lay.addWidget(_para(_tr("Publications that use this tool must cite:")))
    cite_frame = QFrame()
    cite_frame.setStyleSheet(
        "QFrame{background:#e8f5e9;border-left:4px solid #1b6b39;border-radius:3px;}"
    )
    cite_lay = QVBoxLayout(cite_frame)
    cite_lay.setContentsMargins(12, 8, 12, 8)
    cite_lay.addWidget(
        _about_label(
            '<a href="https://doi.org/10.1590/1678-4499.20250223" '
            'style="color:#1b6b39;font-weight:bold;text-decoration:none;">'
            "https://doi.org/10.1590/1678-4499.20250223</a>",
            "font-size:12px;background:transparent;",
        )
    )
    lay.addWidget(cite_frame)

    lay.addStretch(1)
    scroll.setWidget(w)
    outer.addWidget(scroll, 1)

    btn_row = QHBoxLayout()
    btn_row.setContentsMargins(0, 10, 0, 8)
    btn_row.addStretch(1)
    dialog.cp_btn_get_started = QPushButton(_tr("Get Started"))
    dialog.cp_btn_get_started.setStyleSheet(STYLE_BTN_PRIMARY)
    dialog.cp_btn_get_started.setFixedHeight(36)
    dialog.cp_btn_get_started.setMinimumWidth(180)
    dialog.cp_btn_get_started.setCursor(Qt.CursorShape.PointingHandCursor)
    btn_row.addWidget(dialog.cp_btn_get_started)
    btn_row.addStretch(1)
    outer.addLayout(btn_row)


# --------------------------------------------------------------- coordinates
def _build_coords_tab(dialog, page):
    layout = QVBoxLayout(page)
    layout.setContentsMargins(14, 10, 14, 10)
    layout.setSpacing(6)

    # Data source selector (item data values are the source keys).
    layout.addWidget(_field_label(_tr("DATA SOURCE")))
    dialog.cp_source_combo_a = QComboBox()
    dialog.cp_source_combo_a.addItem("NASA POWER", "power")
    dialog.cp_source_combo_a.addItem("Open-Meteo (ERA5)", "openmeteo")
    dialog.cp_source_combo_a.setToolTip(_tr("Climate data provider"))
    dialog.cp_source_combo_a.setCursor(Qt.CursorShape.PointingHandCursor)
    layout.addWidget(dialog.cp_source_combo_a)

    layout.addSpacing(4)

    layout.addWidget(_field_label(_tr("LOCATION")))
    grid = QGridLayout()
    grid.setContentsMargins(0, 0, 0, 0)
    grid.setHorizontalSpacing(6)
    grid.setVerticalSpacing(3)
    dialog.cp_lon_a = QLineEdit()
    dialog.cp_lon_a.setPlaceholderText("e.g. -47.06")
    dialog.cp_lon_a.setToolTip(_tr("Longitude in decimal degrees (WGS84), −180 to 180"))
    dialog.cp_lon_a.setValidator(QDoubleValidator(-180.0, 180.0, 6))
    dialog.cp_lat_a = QLineEdit()
    dialog.cp_lat_a.setPlaceholderText("e.g. -22.90")
    dialog.cp_lat_a.setToolTip(_tr("Latitude in decimal degrees (WGS84), −90 to 90"))
    dialog.cp_lat_a.setValidator(QDoubleValidator(-90.0, 90.0, 6))
    grid.addWidget(QLabel(_tr("Longitude")), 0, 0)
    grid.addWidget(QLabel(_tr("Latitude")), 0, 1)
    grid.addWidget(dialog.cp_lon_a, 1, 0)
    grid.addWidget(dialog.cp_lat_a, 1, 1)

    dialog.cp_btn_pick_a = QPushButton(_tr(PICK_TEXT_OFF))
    dialog.cp_btn_pick_a.setCheckable(True)
    dialog.cp_btn_pick_a.setStyleSheet(STYLE_BTN_SECONDARY)
    dialog.cp_btn_pick_a.setCursor(Qt.CursorShape.PointingHandCursor)
    dialog.cp_btn_pick_a.setMinimumHeight(30)
    dialog.cp_btn_pick_a.setToolTip(
        _tr("Capture a coordinate by clicking on the map canvas")
    )
    grid.addWidget(dialog.cp_btn_pick_a, 2, 0, 1, 2)

    # Year range (the controller re-syncs the minimum per data source).
    dialog.cp_start_year = QSpinBox()
    dialog.cp_start_year.setRange(_MIN_YEAR, _MAX_YEAR)
    dialog.cp_start_year.setValue(_MIN_YEAR)
    dialog.cp_start_year.setToolTip(_tr("First year to download"))
    dialog.cp_end_year = QSpinBox()
    dialog.cp_end_year.setRange(_MIN_YEAR, _MAX_YEAR)
    dialog.cp_end_year.setValue(_MAX_YEAR)
    dialog.cp_end_year.setToolTip(_tr("Last year to download"))
    years = QHBoxLayout()
    years.setSpacing(6)
    years.addStretch(1)
    years.addWidget(QLabel(_tr("Years")))
    years.addWidget(dialog.cp_start_year)
    years.addWidget(QLabel(_tr("to")))
    years.addWidget(dialog.cp_end_year)
    years.addStretch(1)
    grid.addLayout(years, 3, 0, 1, 2)
    layout.addLayout(grid)

    layout.addSpacing(6)
    separator = QFrame()
    separator.setFrameShape(QFrame.Shape.HLine)
    separator.setStyleSheet("color: #e0e0e0;")
    layout.addWidget(separator)
    layout.addSpacing(4)

    # Optional comparison point B (overlaid on the Trends chart).
    layout.addWidget(_field_label(_tr("COMPARISON POINT B (OPTIONAL)")))
    grid_b = QGridLayout()
    grid_b.setContentsMargins(0, 0, 0, 0)
    grid_b.setHorizontalSpacing(6)
    grid_b.setVerticalSpacing(3)
    dialog.cp_lon_b = QLineEdit()
    dialog.cp_lon_b.setPlaceholderText("e.g. -44.00")
    dialog.cp_lon_b.setValidator(QDoubleValidator(-180.0, 180.0, 6))
    dialog.cp_lat_b = QLineEdit()
    dialog.cp_lat_b.setPlaceholderText("e.g. -20.00")
    dialog.cp_lat_b.setValidator(QDoubleValidator(-90.0, 90.0, 6))
    grid_b.addWidget(QLabel(_tr("Longitude")), 0, 0)
    grid_b.addWidget(QLabel(_tr("Latitude")), 0, 1)
    grid_b.addWidget(dialog.cp_lon_b, 1, 0)
    grid_b.addWidget(dialog.cp_lat_b, 1, 1)

    dialog.cp_btn_pick_b = QPushButton(_tr(PICK_B_OFF))
    dialog.cp_btn_pick_b.setCheckable(True)
    dialog.cp_btn_pick_b.setStyleSheet(STYLE_BTN_SECONDARY)
    dialog.cp_btn_pick_b.setCursor(Qt.CursorShape.PointingHandCursor)
    dialog.cp_btn_pick_b.setMinimumHeight(30)
    dialog.cp_btn_pick_b.setToolTip(_tr("Leave empty for a single-point analysis"))
    grid_b.addWidget(dialog.cp_btn_pick_b, 2, 0, 1, 2)

    # Replicate point A into B, so the same location can be compared across
    # sources without re-clicking the map.
    dialog.cp_btn_copy_a_to_b = _button(
        _tr("⧉  Same location as A"),
        _tr("Copy point A's coordinates here (e.g. to compare data sources)"),
        height=30,
    )
    grid_b.addWidget(dialog.cp_btn_copy_a_to_b, 3, 0, 1, 2)

    # B may use its own source, so the same point can be compared across sources.
    dialog.cp_source_combo_b = QComboBox()
    dialog.cp_source_combo_b.addItem(_tr("(same source as A)"), None)
    dialog.cp_source_combo_b.addItem("NASA POWER", "power")
    dialog.cp_source_combo_b.addItem("Open-Meteo (ERA5)", "openmeteo")
    dialog.cp_source_combo_b.setToolTip(_tr("Data source for the comparison point"))
    dialog.cp_source_combo_b.setCursor(Qt.CursorShape.PointingHandCursor)
    src_b = QHBoxLayout()
    src_b.setSpacing(6)
    src_b.addWidget(QLabel(_tr("Source")))
    src_b.addWidget(dialog.cp_source_combo_b, 1)
    grid_b.addLayout(src_b, 4, 0, 1, 2)
    layout.addLayout(grid_b)

    layout.addSpacing(6)

    aux = QHBoxLayout()
    aux.setSpacing(6)
    dialog.cp_btn_hybrid_layer = _button(
        _tr("Add Google Hybrid Layer"),
        _tr("Add a Google satellite basemap to help locate your point"),
        height=30,
    )
    dialog.cp_btn_clear_marker = _button(
        _tr("Clear marker"),
        _tr("Remove the point markers from the map"),
        height=30,
    )
    aux.addWidget(dialog.cp_btn_hybrid_layer)
    aux.addWidget(dialog.cp_btn_clear_marker)
    layout.addLayout(aux)

    layout.addStretch(1)

    # Run analysis anchored at the bottom of the tab (full width).
    dialog.cp_btn_run = _button(
        _tr("Run analysis"),
        _tr("Download climate data for this point and build the charts"),
        style=STYLE_BTN_PRIMARY,
        height=36,
    )
    layout.addWidget(dialog.cp_btn_run)


# ---------------------------------------------------------------------- plots
def _plot_tab(page):
    """Common skeleton: a top toolbar row + an expanding web view below."""
    layout = QVBoxLayout(page)
    layout.setContentsMargins(8, 6, 8, 6)
    layout.setSpacing(6)
    row = QHBoxLayout()
    row.setSpacing(6)
    layout.addLayout(row)
    desc = QLabel()
    desc.setWordWrap(True)
    desc.setStyleSheet(
        "color:#757575;font-size:11px;font-style:italic;background:transparent;"
    )
    layout.addWidget(desc)
    web = _make_webview()
    layout.addWidget(web, 1)
    return row, web, desc


def _toolbar_label(text):
    lbl = QLabel(text)
    lbl.setStyleSheet(
        "color: #616161; font-size: 12px; font-weight: bold; background: transparent;"
    )
    return lbl


def _build_trends_tab(dialog, page):
    row, web, dialog.cp_var_desc = _plot_tab(page)
    dialog.cp_var_combo = _combo(_VARIABLES, _tr("Choose the climate variable to plot"))
    dialog.cp_btn_csv_raw = _button(
        _tr("Save daily data"), _tr("Export the full daily series as CSV")
    )
    dialog.cp_btn_browser_trends = _button(
        _tr("Open in browser"), _tr("Open this chart full-screen in your web browser")
    )
    dialog.cp_btn_csv_trends = _button(
        _tr("Save chart data"), _tr("Export the plotted annual series as CSV")
    )
    dialog.cp_btn_png_trends = _button(
        _tr("Image"), _tr("Save the chart as a PNG image")
    )
    dialog.cp_btn_export_all = _button(
        _tr("Export all"), _tr("Export every table to one Excel file")
    )
    row.addWidget(_toolbar_label(_tr("Variable:")))
    row.addWidget(dialog.cp_var_combo)
    row.addStretch(1)
    row.addWidget(dialog.cp_btn_csv_raw)
    row.addWidget(dialog.cp_btn_browser_trends)
    row.addWidget(dialog.cp_btn_csv_trends)
    row.addWidget(dialog.cp_btn_png_trends)
    row.addWidget(dialog.cp_btn_export_all)
    dialog.cp_web_trends = web
    dialog.cp_var_desc.setText(variable_description(_VARIABLES[0]))


def _build_thermo_tab(dialog, page):
    row, web, thermo_desc = _plot_tab(page)
    thermo_desc.setText(
        _tr(
            "Mean monthly precipitation (bars) and mean temperatures (lines) "
            "across the year."
        )
    )
    dialog.cp_btn_browser_thermo = _button(
        _tr("Open in browser"), _tr("Open this chart full-screen in your web browser")
    )
    dialog.cp_btn_csv_thermo = _button(
        _tr("Save chart data"), _tr("Export the monthly climate normals as CSV")
    )
    dialog.cp_btn_png_thermo = _button(
        _tr("Image"), _tr("Save the chart as a PNG image")
    )
    row.addWidget(_toolbar_label(_tr("Mean monthly precipitation and temperature")))
    row.addStretch(1)
    row.addWidget(dialog.cp_btn_browser_thermo)
    row.addWidget(dialog.cp_btn_csv_thermo)
    row.addWidget(dialog.cp_btn_png_thermo)
    dialog.cp_web_thermo = web


def _build_indices_tab(dialog, page):
    row, web, dialog.cp_index_desc = _plot_tab(page)
    dialog.cp_index_combo = _combo(
        _INDICES, _tr("Choose the ETCCDI climate index to plot"), min_width=300
    )
    dialog.cp_index_combo.setCurrentIndex(0)
    dialog.cp_btn_browser_indices = _button(
        _tr("Open in browser"), _tr("Open this chart full-screen in your web browser")
    )
    dialog.cp_btn_csv_indices = _button(
        _tr("Save chart data"), _tr("Export the selected index series as CSV")
    )
    dialog.cp_btn_png_indices = _button(
        _tr("Image"), _tr("Save the chart as a PNG image")
    )
    row.addWidget(_toolbar_label(_tr("Index:")))
    row.addWidget(dialog.cp_index_combo, 1)
    row.addWidget(dialog.cp_btn_browser_indices)
    row.addWidget(dialog.cp_btn_csv_indices)
    row.addWidget(dialog.cp_btn_png_indices)
    dialog.cp_web_indices = web
    dialog.cp_index_desc.setText(index_description(_INDICES[0]))
