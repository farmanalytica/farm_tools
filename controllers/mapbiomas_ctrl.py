# -*- coding: utf-8 -*-
"""
Controller for the MapBiomas page.

Wires the UI in ``view/mapbiomas.py`` to ``services/mapbiomas_service.py``.
MapBiomas is browsed *inside the module* (not loaded as QGIS layers), keeping the
FARM web-app feel:

  • **Coverage** — every year is rendered to a PNG; a year slider swaps the image
    shown in the Coverage tab, beside the class legend.
  • **Transition** — the Pasture→Crop PNG is shown next to a plotly bar chart of
    the converted area per year.

The AOI is extracted on the main thread and the slow Earth Engine work runs in a
``QThread`` worker (``finished``/``failed``/``progress``).
"""

import os
import shutil
import tempfile

from qgis.PyQt.QtCore import QCoreApplication, Qt, QTimer
from qgis.PyQt.QtGui import QColor, QPixmap
from qgis.PyQt.QtWidgets import QGraphicsOpacityEffect
from qgis.core import (
    Qgis,
    QgsCoordinateReferenceSystem,
    QgsCoordinateTransform,
    QgsLayerTreeLayer,
    QgsMessageLog,
    QgsPalettedRasterRenderer,
    QgsProject,
    QgsRasterLayer,
)

from ..managers.settings_manager import SettingsManager
from ..services.aoi_service import AOIService
from ..services.mapbiomas_service import (
    MAPBIOMAS_CLASS_LABELS,
    MAPBIOMAS_PALETTE,
    MAPBIOMAS_TRANSITION_FIRST_YEAR,
    MAPBIOMAS_TRANSITION_LAST_YEAR,
    MAPBIOMAS_TRANSITION_PALETTE,
    MAPBIOMAS_TRANSITION_PRESETS,
)
from ..tools.aoi_draw_tool import start_draw_aoi
from ..view import plotly_render
from ..workers.mapbiomas_worker import MapBiomasWorker


def _tr(text):
    return QCoreApplication.translate("RAVI", text)


_CANVAS_SCALE_FACTOR = 1.5

# Plotly chart config (toolbar trimmed) — mirrors the ClimaPlots config.
_PLOT_CONFIG = {
    "displaylogo": False,
    "responsive": True,
    "modeBarButtonsToRemove": [
        "toImage", "sendDataToCloud", "select2d", "lasso2d",
        "hoverClosestCartesian", "hoverCompareCartesian", "toggleSpikelines",
    ],
}


class MapBiomasCtrl:
    """Handles user interactions on the MapBiomas page."""

    def __init__(self, dialog, interface=None, gee_service=None):
        self.dialog = dialog
        self.interface = interface
        self.gee_service = gee_service

        self.aoi = None
        self._worker = None
        self._draw_tool = None
        self._tmp_dir = None
        self._active_progress = None  # the feature bar driven by _on_progress

        self._cov_pix = {}          # year -> QPixmap
        self._tx_pix = None         # QPixmap
        self._tx_fig = None         # plotly figure (for "open in browser")
        self._tx_tmp_path = None    # temp html for the chart web view
        self._tx_label = ""         # active transition label (chart title)
        self._tx_per_year = []      # full per-year stats (for live range redraw)
        self._tx_source = None      # active transition source classes
        self._tx_target = None      # active transition target classes

        # Re-rendering the transition MAP for a year window is a server-side
        # thumbnail (slow, network-bound), so it runs in its own worker — kept
        # separate from self._worker so it never trips the load/download busy
        # guards. Only the latest requested range matters: while one render is in
        # flight, a newer range is stashed and rendered when it finishes.
        self._tx_map_worker = None
        self._tx_map_pending_range = None

        # Authoritative chart redraw, debounced: a slider drag fires many ticks,
        # but a full Plotly reload is heavy, so coalesce into one redraw shortly
        # after the slider settles. An instant client-side restyle (no reload)
        # is attempted on every tick for live feedback; this timer guarantees the
        # chart is correct even if the restyle is a no-op.
        self._tx_redraw_timer = QTimer(self.dialog)
        self._tx_redraw_timer.setSingleShot(True)
        self._tx_redraw_timer.setInterval(200)
        self._tx_redraw_timer.timeout.connect(self._on_tx_range_settled)

        # Keep the displayed image in sync with the slider once loaded.
        self.dialog.mb_cov_slider.valueChanged.connect(self._on_slider_changed)

    # ------------------------------------------------------------------
    # Worker lifecycle
    # ------------------------------------------------------------------

    def _release_worker(self):
        if self._worker is not None:
            self._worker.deleteLater()
            self._worker = None

    def _tmp(self):
        if self._tmp_dir is None or not os.path.isdir(self._tmp_dir):
            self._tmp_dir = tempfile.mkdtemp(prefix="farm_mapbiomas_")
        return self._tmp_dir

    # ------------------------------------------------------------------
    # AOI helpers
    # ------------------------------------------------------------------

    def handle_draw_aoi(self):
        """Toggle rectangular AOI drawing on the canvas."""
        canvas = self.interface.mapCanvas()
        if self._draw_tool is not None and canvas.mapTool() is self._draw_tool:
            canvas.unsetMapTool(self._draw_tool)
            self._draw_tool = None
            return
        self._draw_tool = start_draw_aoi(
            self.interface,
            self.dialog.mb_layer_combo,
            self.dialog.mb_btn_draw_aoi,
        )

    def handle_layer_changed(self, layer=None):
        """Zoom the map canvas to the newly selected AOI layer."""
        if layer is None:
            layer = self.dialog.mb_layer_combo.currentLayer()
        if not layer or not layer.isValid() or not self.interface:
            return
        canvas = self.interface.mapCanvas()
        transform = QgsCoordinateTransform(
            layer.crs(),
            canvas.mapSettings().destinationCrs(),
            QgsProject.instance(),
        )
        extent = transform.transformBoundingBox(layer.extent())
        extent.scale(_CANVAS_SCALE_FACTOR)
        canvas.setExtent(extent)
        canvas.refresh()

    # ------------------------------------------------------------------
    # Run guards + dispatch
    # ------------------------------------------------------------------

    def _resolve_aoi(self):
        """Validate auth + layer and return an ee.FeatureCollection, or None."""
        if self._worker is not None and self._worker.isRunning():
            return None

        if self.gee_service and not self.gee_service.is_authenticated:
            self.dialog.pop_message(
                _tr(
                    "Authentication is required to load MapBiomas data. "
                    "Open the Auth page and validate your Google Cloud project ID."
                ),
                "warning",
            )
            return None

        layer = self.dialog.mb_layer_combo.currentLayer()
        if not layer:
            self.dialog.pop_message(_tr("Select an AOI layer."), "warning")
            return None

        try:
            aoi, _bbox = AOIService.get_ee_feature_colection_from_layer(
                layer, use_selected_features=False
            )
        except Exception as exc:
            self.dialog.pop_message(str(exc), "warning")
            return None
        return aoi

    def handle_load_coverage(self):
        """Render every MapBiomas year and enable the year slider."""
        aoi = self._resolve_aoi()
        if aoi is None:
            return
        self.aoi = aoi
        self._start_worker(aoi, "coverage")

    def handle_preset_changed(self):
        """Reveal the custom source/target pickers only for the Custom preset."""
        is_custom = self.dialog.mb_tx_preset_combo.currentData() == "custom"
        self.dialog.mb_tx_custom_panel.setVisible(is_custom)

    @staticmethod
    def _checked_classes(list_widget):
        ids = []
        for row in range(list_widget.count()):
            item = list_widget.item(row)
            if item.checkState() == Qt.CheckState.Checked:
                ids.append(item.data(Qt.ItemDataRole.UserRole))
        return tuple(ids)

    def _resolve_transition(self):
        """Return ``(label, source_classes, target_classes)`` from the UI, or None.

        Reads the preset dropdown — or, for "Custom…", the checked source/target
        class lists. Pops a warning and returns None when the custom selection
        is incomplete. Sets ``self._tx_label`` as a side effect.
        """
        key = self.dialog.mb_tx_preset_combo.currentData()
        if key == "custom":
            source = self._checked_classes(self.dialog.mb_tx_src_list)
            target = self._checked_classes(self.dialog.mb_tx_tgt_list)
            if not source or not target:
                self.dialog.pop_message(
                    _tr("Pick at least one source class and one target class."),
                    "warning",
                )
                return None
            self._tx_label = _tr("Custom transition")
            return self._tx_label, source, target
        label, source, target = MAPBIOMAS_TRANSITION_PRESETS[key]
        self._tx_label = _tr(label)
        return self._tx_label, source, target

    def handle_load_transition(self):
        """Render the selected source→target transition and chart its yearly area."""
        aoi = self._resolve_aoi()
        if aoi is None:
            return
        resolved = self._resolve_transition()
        if resolved is None:
            return
        _label, source, target = resolved

        self.aoi = aoi
        self._tx_source = source
        self._tx_target = target
        self._set_busy(True)
        self._begin_progress(self.dialog.mb_tx_progress)
        self._worker = MapBiomasWorker(
            aoi, "transition", output_dir=self._tmp(),
            source_classes=source, target_classes=target,
        )
        self._worker.finished.connect(self._on_done)
        self._worker.failed.connect(self._on_failed)
        self._worker.progress.connect(self._on_progress)
        self._worker.start()

    def handle_download_transition_qgis(self):
        """Download the transition (first-year band) as a paletted QGIS layer."""
        aoi = self._resolve_aoi()
        if aoi is None:
            return
        resolved = self._resolve_transition()
        if resolved is None:
            return
        _label, source, target = resolved

        self.aoi = aoi
        lo, hi = self._tx_range()
        output_folder = SettingsManager.load_download_folder() or self._tmp()
        self._set_busy(True)
        self._begin_progress(
            self.dialog.mb_tx_progress,
            indeterminate=True,
            fmt=_tr("Downloading transition {0}–{1}…").format(lo, hi),
        )
        self._worker = MapBiomasWorker(
            aoi, "download_transition", output_folder=output_folder,
            source_classes=source, target_classes=target,
            year_min=lo, year_max=hi,
        )
        self._worker.finished.connect(self._on_done)
        self._worker.failed.connect(self._on_failed)
        self._worker.progress.connect(self._on_progress)
        self._worker.start()

    def handle_download_qgis(self):
        """Download the coverage slider's current year as a QGIS raster."""
        aoi = self._resolve_aoi()
        if aoi is None:
            return
        self._download_year_to_qgis(aoi, self.dialog.mb_cov_slider.value())

    def handle_download_year(self):
        """Download the Inputs-tab year picker's selection as a QGIS raster."""
        aoi = self._resolve_aoi()
        if aoi is None:
            return
        self._download_year_to_qgis(aoi, self.dialog.mb_dl_year_combo.currentData())

    def _download_year_to_qgis(self, aoi, year):
        self.aoi = aoi
        output_folder = SettingsManager.load_download_folder() or self._tmp()
        self._set_busy(True)
        self._begin_progress(
            self.dialog.mb_dl_progress,
            indeterminate=True,
            fmt=_tr("Downloading {0}…").format(year),
        )
        self._worker = MapBiomasWorker(
            aoi, "download", year=year, output_folder=output_folder
        )
        self._worker.finished.connect(self._on_done)
        self._worker.failed.connect(self._on_failed)
        self._worker.progress.connect(self._on_progress)
        self._worker.start()

    def _start_worker(self, aoi, mode):
        self._set_busy(True)
        bar = (
            self.dialog.mb_cov_progress
            if mode == "coverage"
            else self.dialog.mb_tx_progress
        )
        self._begin_progress(bar)
        self._worker = MapBiomasWorker(aoi, mode, output_dir=self._tmp())
        self._worker.finished.connect(self._on_done)
        self._worker.failed.connect(self._on_failed)
        self._worker.progress.connect(self._on_progress)
        self._worker.start()

    # ------------------------------------------------------------------
    # Busy / progress
    # ------------------------------------------------------------------

    def _all_progress_bars(self):
        return (
            self.dialog.mb_cov_progress,
            self.dialog.mb_dl_progress,
            self.dialog.mb_tx_progress,
        )

    def _begin_progress(self, bar, indeterminate=False, fmt=None):
        """Show *bar* as the active feedback (hiding the others).

        ``indeterminate`` shows a busy bar (range 0,0) for fixed-length single
        downloads; otherwise a 0–100 bar driven by ``_on_progress``.
        """
        self._active_progress = bar
        for candidate in self._all_progress_bars():
            candidate.setVisible(candidate is bar)
        if indeterminate:
            bar.setRange(0, 0)
        else:
            bar.setRange(0, 100)
            bar.setValue(0)
        bar.setFormat(fmt or _tr("Starting…"))

    def _set_busy(self, busy):
        self.dialog.mb_btn_load_coverage.setEnabled(not busy)
        self.dialog.mb_btn_load_transition.setEnabled(not busy)
        self.dialog.mb_btn_download_qgis.setEnabled(not busy)
        self.dialog.mb_btn_download_year.setEnabled(not busy)
        if not busy:
            for bar in self._all_progress_bars():
                bar.setVisible(False)
            self._active_progress = None

    def _on_progress(self, message, done, total):
        if total <= 0 or self._active_progress is None:
            return
        self._active_progress.setValue(int(done / total * 100))
        self._active_progress.setFormat("{0}  ({1}/{2})".format(message, done, total))

    # ------------------------------------------------------------------
    # Worker results
    # ------------------------------------------------------------------

    def _on_done(self, result):
        self._set_busy(False)
        self._release_worker()
        mode = result.get("mode")
        if mode == "coverage":
            self._show_coverage(result.get("images") or {})
        elif mode == "download":
            self._load_qgis_raster(result.get("path"), result.get("year"))
        elif mode == "download_transition":
            self._load_transition_qgis_raster(result.get("path"))
        else:
            self._show_transition(result.get("image"), result.get("stats") or {})

    def _on_failed(self, message):
        self._set_busy(False)
        self._release_worker()
        self.dialog.pop_message(message, "warning")

    # ------------------------------------------------------------------
    # Coverage display
    # ------------------------------------------------------------------

    def _show_coverage(self, images):
        if not images:
            self.dialog.pop_message(
                _tr("No MapBiomas coverage returned (Brazil only)."), "warning"
            )
            return

        self._cov_pix = {}
        for year, path in images.items():
            pix = QPixmap(path)
            if not pix.isNull():
                self._cov_pix[year] = pix
        if not self._cov_pix:
            self.dialog.pop_message(
                _tr("Failed to read MapBiomas coverage images."), "warning"
            )
            return

        years = sorted(self._cov_pix)
        slider = self.dialog.mb_cov_slider
        slider.blockSignals(True)
        slider.setMinimum(years[0])
        slider.setMaximum(years[-1])
        slider.setValue(years[-1])
        slider.setEnabled(True)
        slider.blockSignals(False)

        self._show_cov_year(years[-1])
        self.dialog.mb_set_tab(1)

    def _on_slider_changed(self, year):
        self._show_cov_year(year)

    def _show_cov_year(self, year):
        pix = self._cov_pix.get(year)
        if pix is None:
            # Snap to the nearest available year if the exact one is missing.
            available = sorted(self._cov_pix)
            if not available:
                return
            year = min(available, key=lambda y: abs(y - year))
            pix = self._cov_pix[year]
        self.dialog.mb_cov_year_lbl.setText(str(year))
        self._set_image(self.dialog.mb_cov_image, pix)

    # ------------------------------------------------------------------
    # QGIS layer (single-year GeoTIFF)
    # ------------------------------------------------------------------

    def _load_qgis_raster(self, path, year):
        """Load the downloaded classification GeoTIFF as a paletted QGIS layer."""
        if not path or not os.path.exists(path):
            self.dialog.pop_message(
                _tr("Failed to download MapBiomas raster."), "warning"
            )
            return
        layer = QgsRasterLayer(path, "MapBiomas {0}".format(year))
        if not layer.isValid():
            self.dialog.pop_message(
                _tr("Failed to load MapBiomas raster into QGIS."), "warning"
            )
            return
        layer.setCrs(QgsCoordinateReferenceSystem("EPSG:4326"))

        classes = []
        for class_id, class_label in MAPBIOMAS_CLASS_LABELS.items():
            hex_color = (
                MAPBIOMAS_PALETTE[class_id]
                if class_id < len(MAPBIOMAS_PALETTE)
                else "808080"
            )
            classes.append(
                QgsPalettedRasterRenderer.Class(
                    class_id, QColor("#" + hex_color), class_label
                )
            )
        self._apply_paletted(layer, classes)
        self._add_layer_to_qgis(layer)
        if self.interface:
            self.interface.messageBar().pushMessage(
                "FARM tools",
                _tr("MapBiomas coverage {0} loaded into QGIS.").format(year),
            )

    def _load_transition_qgis_raster(self, path):
        """Load the transition GeoTIFF as a layer classed by transition year.

        Pixel values are the first-transition year (1986–2024); a paletted
        renderer maps each year to the year-graded transition palette, like the
        original MapBiomas transition layer.
        """
        if not path or not os.path.exists(path):
            self.dialog.pop_message(
                _tr("Failed to download transition raster."), "warning"
            )
            return
        name = self._tx_label or _tr("MapBiomas transition")
        layer = QgsRasterLayer(path, name)
        if not layer.isValid():
            self.dialog.pop_message(
                _tr("Failed to load transition raster into QGIS."), "warning"
            )
            return
        layer.setCrs(QgsCoordinateReferenceSystem("EPSG:4326"))

        # Only the years inside the slider window are exported (out-of-range
        # pixels are masked in the GeoTIFF), so class the layer to that window
        # only — no empty legend entries for filtered-out years. Colors stay
        # pinned to the full-range gradient so each year matches the map/chart.
        all_years = list(range(
            MAPBIOMAS_TRANSITION_FIRST_YEAR, MAPBIOMAS_TRANSITION_LAST_YEAR + 1
        ))
        all_colors = self._bar_colors(len(all_years))
        lo, hi = self._tx_range()
        classes = [
            QgsPalettedRasterRenderer.Class(year, QColor(all_colors[i]), str(year))
            for i, year in enumerate(all_years)
            if lo <= year <= hi
        ]
        self._apply_paletted(layer, classes)
        self._add_layer_to_qgis(layer)
        if self.interface:
            self.interface.messageBar().pushMessage(
                "FARM tools",
                _tr("Transition layer loaded into QGIS: {0}").format(name),
            )

    # ------------------------------------------------------------------
    # Shared QGIS layer helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _apply_paletted(layer, classes):
        """Apply a categorical paletted renderer, logging (not raising) on error."""
        try:
            renderer = QgsPalettedRasterRenderer(layer.dataProvider(), 1, classes)
            layer.setRenderer(renderer)
        except Exception as exc:  # keep the layer's default renderer as a fallback
            QgsMessageLog.logMessage(
                "MapBiomas paletted renderer failed: {0}".format(exc),
                "FARM tools", Qgis.Warning,
            )

    def _add_layer_to_qgis(self, layer):
        """Add *layer* to the project/tree and zoom the canvas to its extent.

        The downloaded raster is in EPSG:4326; zooming (with reprojection to the
        canvas CRS) guarantees it is visible instead of sitting off-screen.
        """
        QgsProject.instance().addMapLayer(layer, False)
        QgsProject.instance().layerTreeRoot().insertChildNode(
            0, QgsLayerTreeLayer(layer)
        )
        layer.triggerRepaint()
        if not self.interface:
            return
        canvas = self.interface.mapCanvas()
        try:
            extent = layer.extent()
            if layer.crs() != canvas.mapSettings().destinationCrs():
                transform = QgsCoordinateTransform(
                    layer.crs(),
                    canvas.mapSettings().destinationCrs(),
                    QgsProject.instance(),
                )
                extent = transform.transformBoundingBox(extent)
            if not extent.isEmpty():
                canvas.setExtent(extent)
        except Exception as exc:
            QgsMessageLog.logMessage(
                "MapBiomas zoom-to-layer failed: {0}".format(exc),
                "FARM tools", Qgis.Warning,
            )
        canvas.refresh()

    # ------------------------------------------------------------------
    # Transition display
    # ------------------------------------------------------------------

    def _show_transition(self, image_path, stats):
        if image_path and os.path.exists(image_path):
            self._tx_pix = QPixmap(image_path)
            if not self._tx_pix.isNull():
                self._set_image(self.dialog.mb_tx_image, self._tx_pix)

        self._render_stats(stats)
        self.dialog.mb_set_tab(2)

    def _render_stats(self, stats):
        self._tx_per_year = stats.get("per_year") or []
        total = stats.get("total_hectares", 0.0)

        if not self._tx_per_year or total <= 0:
            self.dialog.mb_stats_summary.setText(
                _tr("No transition found in this area for: {0}").format(
                    self._tx_label or _tr("selected transition")
                )
            )
            self._tx_fig = None
            self._tx_tmp_path = plotly_render.clear_webview(
                self.dialog.mb_web_transition, self._tx_tmp_path
            )
            return

        # Reset the year-range filter to the full span for the new result.
        slider = self.dialog.mb_tx_range
        slider.blockSignals(True)
        slider.set_low(MAPBIOMAS_TRANSITION_FIRST_YEAR)
        slider.set_high(MAPBIOMAS_TRANSITION_LAST_YEAR)
        slider.blockSignals(False)
        self._draw_tx_chart()

    def _tx_range(self):
        """Current (low, high) transition years from the range slider."""
        lo = int(round(self.dialog.mb_tx_range.low()))
        hi = int(round(self.dialog.mb_tx_range.high()))
        return lo, hi

    def _tx_view_state(self):
        """Per-bar colors + in-range total for the current slider range.

        Returns ``(lo, hi, years, hectares, colors, in_total)``. In-range bars
        keep their gradient color; out-of-range bars fade to grey.
        """
        lo, hi = self._tx_range()
        years = [d["year"] for d in self._tx_per_year]
        hectares = [d["hectares"] for d in self._tx_per_year]
        base_colors = self._bar_colors(len(years))
        colors = [
            base_colors[i] if lo <= y <= hi else "#e3e7e4"
            for i, y in enumerate(years)
        ]
        in_total = sum(
            d["hectares"] for d in self._tx_per_year if lo <= d["year"] <= hi
        )
        return lo, hi, years, hectares, colors, in_total

    def _update_tx_summary(self, lo, hi, in_total):
        self.dialog.mb_stats_summary.setText(
            "{0} — {1}".format(
                self._tx_label,
                _tr("{0:.1f} ha in {1}–{2}").format(in_total, lo, hi),
            )
        )

    def handle_tx_range_changed(self, _value=None):
        """Year-range slider moved — give instant feedback, then redraw.

        Three layers of feedback, fastest first:
          1. The year label updates immediately (cheap).
          2. A client-side ``Plotly.restyle`` recolors the existing chart with no
             reload — instant when it lands.
          3. A debounced full redraw (``_tx_redraw_timer``) guarantees the chart
             is correct even if the restyle is a no-op, and a transient
             "updating…" cue tells the user a redraw is pending.
        """
        lo, hi = self._tx_range()
        self.dialog.mb_tx_range_lbl.setText(_tr("Years: {0}–{1}").format(lo, hi))
        if not self._tx_per_year:
            return
        _lo, _hi, _years, _ha, colors, in_total = self._tx_view_state()
        # Immediate waiting cue (the full redraw lands a beat later).
        self.dialog.mb_stats_summary.setText(
            "{0} — {1}".format(
                self._tx_label, _tr("updating {0}–{1}…").format(lo, hi)
            )
        )
        # Instant client-side recolor attempt (no reload).
        plotly_render.restyle_bar_colors(self.dialog.mb_web_transition, colors)
        if self._tx_fig is not None:
            self._tx_fig.data[0].marker.color = colors
        # Authoritative redraw, debounced so a drag doesn't reload every tick.
        self._tx_redraw_timer.start()

    def _on_tx_range_settled(self):
        """Slider settled (debounced): authoritative chart redraw + map re-render."""
        self._draw_tx_chart()
        self._request_tx_map_render()

    def _request_tx_map_render(self):
        """Re-render the transition map for the current window, off the UI thread.

        Coalesces drags: if a render is already running, the new range is stashed
        and rendered once the current one finishes (see ``_on_tx_map_done``), so
        only the latest window is ever drawn.
        """
        if not self._tx_per_year or self.aoi is None or self._tx_source is None:
            return
        lo, hi = self._tx_range()
        self._tx_map_pending_range = (lo, hi)
        if self._tx_map_worker is not None and self._tx_map_worker.isRunning():
            return
        self._start_tx_map_worker(lo, hi)

    def _start_tx_map_worker(self, lo, hi):
        # Waiting cue: dim the map image and note it in the summary while the
        # server-side thumbnail re-renders.
        self._set_tx_map_busy(True)
        self.dialog.mb_stats_summary.setText(
            "{0} — {1}".format(
                self._tx_label, _tr("rendering map {0}–{1}…").format(lo, hi)
            )
        )
        self._tx_map_worker = MapBiomasWorker(
            self.aoi, "transition_map", output_dir=self._tmp(),
            source_classes=self._tx_source, target_classes=self._tx_target,
            year_min=lo, year_max=hi,
        )
        self._tx_map_worker.finished.connect(self._on_tx_map_done)
        self._tx_map_worker.failed.connect(self._on_tx_map_failed)
        self._tx_map_worker.start()

    def _on_tx_map_done(self, result):
        path = result.get("image")
        if path and os.path.exists(path):
            pix = QPixmap(path)
            if not pix.isNull():
                self._tx_pix = pix
                self._set_image(self.dialog.mb_tx_image, pix)
        self._tx_map_worker = None
        self._set_tx_map_busy(False)

        # Restore the real in-range total now the cue is no longer needed.
        lo, hi, _y, _h, _c, in_total = self._tx_view_state()
        self._update_tx_summary(lo, hi, in_total)

        # Range moved while rendering? Render the latest window now.
        if self._tx_map_pending_range and self._tx_map_pending_range != (lo, hi):
            nlo, nhi = self._tx_map_pending_range
            self._start_tx_map_worker(nlo, nhi)

    def _on_tx_map_failed(self, _message):
        self._tx_map_worker = None
        self._set_tx_map_busy(False)

    def _set_tx_map_busy(self, busy):
        """Dim the transition map image while it re-renders (visual wait cue)."""
        effect = self.dialog.mb_tx_image.graphicsEffect()
        if effect is None:
            effect = QGraphicsOpacityEffect(self.dialog.mb_tx_image)
            self.dialog.mb_tx_image.setGraphicsEffect(effect)
        effect.setOpacity(0.35 if busy else 1.0)

    def _draw_tx_chart(self):
        """(Re)build the per-year bar chart, emphasizing the in-range years."""
        if not self._tx_per_year:
            return

        try:
            import plotly.graph_objects as go
        except ImportError:
            self.dialog.pop_message(
                _tr("Charting dependencies are still being provisioned. "
                    "Restart QGIS once setup completes."),
                "warning",
            )
            return

        lo, hi, years, hectares, colors, in_total = self._tx_view_state()
        self.dialog.mb_tx_range_lbl.setText(_tr("Years: {0}–{1}").format(lo, hi))

        fig = go.Figure(
            go.Bar(x=years, y=hectares, marker_color=colors,
                   hovertemplate="%{x}: %{y:.1f} ha<extra></extra>")
        )
        fig.update_layout(
            title=self._tx_label or _tr("Transition per year"),
            xaxis_title=_tr("Year"),
            yaxis_title=_tr("Converted area (ha)"),
            margin=dict(l=60, r=20, t=50, b=40),
            plot_bgcolor="#ffffff",
            paper_bgcolor="#ffffff",
        )

        self._tx_fig = fig
        self._tx_tmp_path = plotly_render.show_in_webview(
            self.dialog.mb_web_transition, fig, _PLOT_CONFIG, self._tx_tmp_path
        )
        self._update_tx_summary(lo, hi, in_total)

    @staticmethod
    def _bar_colors(count):
        """Interpolate the transition palette to one color per bar."""
        palette = MAPBIOMAS_TRANSITION_PALETTE
        if count <= 1:
            return ["#" + palette[0]]
        colors = []
        for i in range(count):
            idx = round(i / (count - 1) * (len(palette) - 1))
            colors.append("#" + palette[idx])
        return colors

    def handle_open_in_browser(self):
        if self._tx_fig is not None:
            plotly_render.open_in_browser(
                self._tx_fig, dict(_PLOT_CONFIG, modeBarButtonsToRemove=[])
            )

    # ------------------------------------------------------------------
    # Image helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _set_image(label, pix):
        """Show *pix* scaled to fit *label*, keeping aspect ratio."""
        width = max(label.width() - 8, 240)
        height = max(label.height() - 8, 240)
        label.setStyleSheet("background:#ffffff; border:none;")
        label.setPixmap(
            pix.scaled(
                width, height,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
        )

    # ------------------------------------------------------------------
    # Cleanup
    # ------------------------------------------------------------------

    def cleanup(self):
        """Release the draw tool, temp files, and any running worker."""
        self._tx_redraw_timer.stop()
        if self._draw_tool is not None and self.interface:
            try:
                self.interface.mapCanvas().unsetMapTool(self._draw_tool)
            except Exception:
                pass
            self._draw_tool = None
        if self._tx_tmp_path and os.path.exists(self._tx_tmp_path):
            try:
                os.remove(self._tx_tmp_path)
            except OSError:
                pass
        self._tx_tmp_path = None
        if self._tmp_dir and os.path.isdir(self._tmp_dir):
            shutil.rmtree(self._tmp_dir, ignore_errors=True)
        self._tmp_dir = None
        if self._worker is not None:
            try:
                self._worker.finished.disconnect()
                self._worker.failed.disconnect()
                self._worker.progress.disconnect()
            except Exception:
                pass
            self._worker.cancel()
            if self._worker.isRunning():
                self._worker.wait(100)
            self._worker.deleteLater()
            self._worker = None
        if self._tx_map_worker is not None:
            try:
                self._tx_map_worker.finished.disconnect()
                self._tx_map_worker.failed.disconnect()
            except Exception:
                pass
            if self._tx_map_worker.isRunning():
                self._tx_map_worker.wait(100)
            self._tx_map_worker.deleteLater()
            self._tx_map_worker = None
