# -*- coding: utf-8 -*-
"""
Client-side filter popup for the Optical (Sentinel-2) Results tab.

Under the new architecture the Sentinel-2 collection is fetched once with the
filter metadata of every image attached. This dialog lets the user adjust the
cloud / coverage / valid-pixel filters and re-filter the cached series *without*
a new Earth Engine call: it owns no GEE logic, it only gathers settings and
emits ``filter_changed`` so a controller can re-render the plot.

Each control is paired with a short explanation. Per-date include/exclude lives
in the time-series controls on the Results tab, not here.
"""

from qgis.PyQt.QtCore import Qt, QCoreApplication, pyqtSignal
from qgis.PyQt.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QScrollArea,
    QSlider,
    QVBoxLayout,
    QWidget,
)

from .styles import STYLE_BTN_PRIMARY, STYLE_BTN_SECONDARY, STYLE_CHECKBOX


def _tr(text):
    return QCoreApplication.translate("RAVI", text)


# Legacy default thresholds (from farm_tools_dialog_base.ui sliders):
#   cloud_scene_max  <- total_pixel_limit (40)  -> keep cloud_pct <= 40
#   valid_pixel_min  <- local_pixel_limit (80)  -> keep valid_pixel_pct >= 80
#   coverage_min     <- aio_cover         (90)  -> keep coverage_pct >= 90
DEFAULT_FILTER_SETTINGS = {
    "cloud_scene_max": 40,
    "valid_pixel_min": 80,
    "coverage_min": 90,
}


_DIALOG_STYLE = (
    "QDialog { background-color: #ffffff; color: #212121; }"
    "QLabel { background: transparent; border: none; }"
    + STYLE_CHECKBOX
)

_SLIDER_STYLE = """
QSlider::groove:horizontal { height: 4px; background: #d6d6d6; border-radius: 2px; }
QSlider::sub-page:horizontal { background: #1b6b39; border-radius: 2px; }
QSlider::add-page:horizontal { background: #d6d6d6; border-radius: 2px; }
QSlider::handle:horizontal {
    background: #1b6b39; width: 14px; height: 14px;
    margin: -6px 0; border-radius: 7px;
}
QSlider::handle:horizontal:hover { background: #15532d; }
"""

class OpticalFilterDialog(QDialog):
    """Popup that adjusts the optical time-series filter client-side.

    Filters are applied to the plot only when the user clicks OK. While the
    sliders move, ``count_fn`` (if given) is called with the current settings
    to show how many cached images would pass -- a cheap row count, not a plot
    re-render. ``filter_changed`` still fires on every change for any listener
    that wants it.
    """

    filter_changed = pyqtSignal(dict)

    def __init__(self, settings=None, count_fn=None, parent=None):
        super().__init__(parent)
        self.setWindowTitle(_tr("Adjust Filter"))
        self.setMinimumWidth(480)
        self.setMinimumHeight(460)
        self.resize(520, 560)
        self.setStyleSheet(_DIALOG_STYLE)

        self._initial = settings
        self._count_fn = count_fn
        self._building = True

        self._build_ui()
        if settings:
            self.set_settings(settings)
        self._building = False
        self._update_count()

    # -- construction -----------------------------------------------------
    def _build_ui(self):
        main = QVBoxLayout(self)
        main.setContentsMargins(12, 12, 12, 12)
        main.setSpacing(10)

        intro = QLabel(
            _tr(
                "Three independent filters narrow the cached image series. Each "
                "card notes which direction is stricter. The plot updates when "
                "you click OK — no new Earth Engine request is made."
            )
        )
        intro.setWordWrap(True)
        intro.setStyleSheet("color: #616161; font-size: 11px;")
        main.addWidget(intro)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        scroll.setStyleSheet(
            "QScrollArea { border: 1px solid #e0e0e0; border-radius: 4px; }"
        )
        content = QWidget()
        content.setStyleSheet("background: transparent;")
        body = QVBoxLayout(content)
        body.setContentsMargins(12, 12, 12, 12)
        body.setSpacing(14)

        body.addWidget(self._build_cloud_section())
        body.addWidget(self._build_valid_section())
        body.addWidget(self._build_coverage_section())
        body.addStretch(1)

        scroll.setWidget(content)
        main.addWidget(scroll, 1)

        self.count_label = QLabel("")
        self.count_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.count_label.setStyleSheet(
            "color: #1b6b39; font-size: 12px; font-weight: bold;"
        )
        main.addWidget(self.count_label)

        button_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok
            | QDialogButtonBox.StandardButton.Cancel
        )
        ok_btn = button_box.button(QDialogButtonBox.StandardButton.Ok)
        ok_btn.setStyleSheet(STYLE_BTN_PRIMARY)
        ok_btn.setFixedHeight(32)
        ok_btn.setMinimumWidth(96)
        cancel_btn = button_box.button(QDialogButtonBox.StandardButton.Cancel)
        cancel_btn.setStyleSheet(STYLE_BTN_SECONDARY)
        cancel_btn.setFixedHeight(32)
        cancel_btn.setMinimumWidth(96)
        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self._on_cancel)
        main.addWidget(button_box)

    def _section(self, title):
        frame = QFrame()
        frame.setStyleSheet(
            "QFrame { background: #fbfcfb; border: 1px solid #e4ebe6;"
            " border-radius: 8px; }"
            "QLabel { background: transparent; border: none; }"
        )
        lay = QVBoxLayout(frame)
        lay.setContentsMargins(14, 12, 14, 12)
        lay.setSpacing(8)
        cap = QLabel(title)
        cap.setStyleSheet(
            "color: #9e9e9e; font-size: 11px; font-weight: bold; letter-spacing: 1px;"
        )
        lay.addWidget(cap)
        return frame, lay

    def _explain(self, text):
        lbl = QLabel(text)
        lbl.setWordWrap(True)
        lbl.setStyleSheet("color: #757575; font-size: 11px;")
        return lbl

    def _pct_slider(self, value):
        slider = QSlider(Qt.Orientation.Horizontal)
        slider.setMinimum(0)
        slider.setMaximum(100)
        slider.setValue(value)
        slider.setStyleSheet(_SLIDER_STYLE)
        return slider

    def _slider_row(self, slider, value_lbl):
        row = QHBoxLayout()
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(8)
        row.addWidget(slider, 1)
        value_lbl.setMinimumWidth(42)
        value_lbl.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        value_lbl.setStyleSheet("color: #1b6b39; font-size: 11px; font-weight: bold;")
        row.addWidget(value_lbl)
        return row

    def _strict_hint(self, text):
        lbl = QLabel(text)
        lbl.setWordWrap(True)
        lbl.setStyleSheet("color: #b26a00; font-size: 10px; font-weight: bold;")
        return lbl

    def _build_slider_section(self, title, explain, hint, attr, default):
        """One self-contained filter card: title, explanation, slider, and a
        strictness hint. The slider/value widgets are exposed as ``<attr>_slider``
        / ``<attr>_value`` so get_settings / set_settings can reach them."""
        frame, lay = self._section(title)
        lay.addWidget(self._explain(explain))

        slider = self._pct_slider(default)
        value = QLabel(f"{default}%")
        lay.addLayout(self._slider_row(slider, value))
        lay.addWidget(self._strict_hint(hint))

        slider.valueChanged.connect(
            lambda v: (value.setText(f"{v}%"), self._emit())
        )
        setattr(self, attr + "_slider", slider)
        setattr(self, attr + "_value", value)
        return frame

    def _build_cloud_section(self):
        return self._build_slider_section(
            _tr("SCENE CLOUD COVER · MAX %"),
            _tr(
                "Tile-level cloud cover (CLOUDY_PIXEL_PERCENTAGE from image "
                "metadata). Sentinel-2 scenes are 100×100 km tiles, so this is "
                "whole-tile cloudiness — not the cloud inside your AOI. For local "
                "conditions, use the Valid pixels filter."
            ),
            _tr("↓  Lower = stricter — keeps only clearer scenes"),
            "cloud_scene",
            DEFAULT_FILTER_SETTINGS["cloud_scene_max"],
        )

    def _build_valid_section(self):
        return self._build_slider_section(
            _tr("VALID PIXELS IN AOI · MIN %"),
            _tr(
                "Share of the AOI covered by valid (unmasked) pixels, per the SCL "
                "classes chosen on the Inputs tab. Measured inside your AOI, so it "
                "reflects local cloud and shadow better than scene cloud cover."
            ),
            _tr("↑  Higher = stricter — demands cleaner pixels in the AOI"),
            "valid_pixel",
            DEFAULT_FILTER_SETTINGS["valid_pixel_min"],
        )

    def _build_coverage_section(self):
        return self._build_slider_section(
            _tr("AOI FOOTPRINT COVERAGE · MIN %"),
            _tr(
                "How much of the AOI the scene's footprint overlaps. High "
                "thresholds (e.g. 90%) ensure scenes that cover the whole AOI; "
                "large or irregular AOIs spanning several tiles may rarely reach "
                "high values."
            ),
            _tr("↑  Higher = stricter — requires fuller AOI coverage"),
            "coverage",
            DEFAULT_FILTER_SETTINGS["coverage_min"],
        )

    # -- behavior ---------------------------------------------------------
    def _emit(self):
        if self._building:
            return
        self._update_count()
        self.filter_changed.emit(self.get_settings())

    def _update_count(self):
        """Show how many cached images pass the current thresholds."""
        if self._count_fn is None:
            self.count_label.setText("")
            return
        n = self._count_fn(self.get_settings())
        self.count_label.setText(_tr("%d images match") % n)

    def _on_cancel(self):
        if self._initial is not None:
            self.filter_changed.emit(dict(self._initial))
        self.reject()

    # -- settings I/O -----------------------------------------------------
    def get_settings(self):
        """Return the current filter configuration as a plain dict."""
        return {
            "cloud_scene_max": self.cloud_scene_slider.value(),
            "valid_pixel_min": self.valid_pixel_slider.value(),
            "coverage_min": self.coverage_slider.value(),
        }

    def set_settings(self, settings):
        """Apply a previously captured settings dict to the widgets."""
        self._building = True
        self.cloud_scene_slider.setValue(
            settings.get("cloud_scene_max", DEFAULT_FILTER_SETTINGS["cloud_scene_max"])
        )
        self.valid_pixel_slider.setValue(
            settings.get("valid_pixel_min", DEFAULT_FILTER_SETTINGS["valid_pixel_min"])
        )
        self.coverage_slider.setValue(
            settings.get("coverage_min", DEFAULT_FILTER_SETTINGS["coverage_min"])
        )
        self._building = False
