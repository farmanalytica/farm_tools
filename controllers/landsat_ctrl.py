# -*- coding: utf-8 -*-
"""
Controller for the Landsat Super-Resolution page.

Clicking Run on the Inputs tab lists the available acquisition dates over the
AOI/date-range; the Results tab then previews or downloads, for the selected
date, a pan-sharpened super-resolution RGB (15 m, TOA), a vegetation index
(30 m, SR) or a multispectral RGB composite (30 m, SR). A batch action pulls the
super-res image of every available date.
"""

import os
import tempfile

from qgis.PyQt.QtCore import QCoreApplication, QUrl
from qgis.PyQt.QtGui import QDesktopServices
from qgis.PyQt.QtWidgets import QFileDialog, QProgressDialog
from qgis.core import (
    QgsContrastEnhancement,
    QgsCoordinateTransform,
    QgsMultiBandColorRenderer,
    QgsProject,
    QgsRasterLayer,
)

from ..managers.settings_manager import SettingsManager
from ..services.aoi_service import AOIService
from ..services.landsat_service import (
    LANDSAT_INDEX_ORDER,
    MISSION_COLORS,
    MISSIONS,
    SATELLITES,
)
from ..tools.aoi_draw_tool import start_draw_aoi
from ..renderers.raster_renderer_utils import RasterRendererUtils
from ..view.sar_plot import render_multiseries_chart_html
from ..workers.landsat_batch_worker import LandsatBatchWorker
from ..workers.landsat_preview_worker import LandsatPreviewWorker
from ..workers.landsat_timeseries_worker import LandsatTimeseriesWorker
from ..workers.landsat_worker import LandsatWorker


def _tr(text):
    return QCoreApplication.translate("RAVI", text)


class LandsatCtrl:
    """Coordinate the Landsat super-resolution page."""

    _CANVAS_SCALE_FACTOR = 1.5

    # Per-mission trace colours come from the satellite registry so a new source
    # is coloured by adding one ``SATELLITES`` entry.
    _MISSION_COLORS = MISSION_COLORS

    def __init__(self, dialog, interface=None, gee_service=None):
        self.dialog = dialog
        self.interface = interface
        self.gee_service = gee_service

        self.aoi = None
        self.shapely_geom = None
        self._aoi_area_m2 = None          # ellipsoidal AOI area, for the % filter
        self.dated_missions = []          # list of (date, mission)
        self._date_start = None
        self._date_end = None
        self._draw_tool = None
        self._run_worker: LandsatWorker | None = None
        self._run_btn_text: str | None = None
        self._preview_worker: LandsatPreviewWorker | None = None
        self._preview_btn_texts: dict | None = None
        self._batch_worker: LandsatBatchWorker | None = None
        self._batch_dialog: QProgressDialog | None = None
        self._ts_worker: LandsatTimeseriesWorker | None = None
        self._ts_df = None
        self._ts_index_name = "NDVI"
        self._plot_path: str | None = None

    # -- AOI ---------------------------------------------------------------
    def _show_auth_required_message(self):
        self.dialog.pop_message(
            _tr(
                "Authentication is required to download Landsat data. "
                "Please go to the Auth page and validate your Google Cloud project ID."
            ),
            "warning",
        )

    def handle_draw_aoi(self):
        """Toggle rectangular AOI drawing on the canvas."""
        if self.interface is None:
            return
        canvas = self.interface.mapCanvas()
        if self._draw_tool is not None and canvas.mapTool() is self._draw_tool:
            canvas.unsetMapTool(self._draw_tool)
            self._draw_tool = None
            return
        self._draw_tool = start_draw_aoi(
            self.interface, self.dialog.ls_layer_combo, self.dialog.ls_btn_draw_aoi
        )

    def handle_layer_changed(self, layer=None):
        """Zoom to the selected AOI layer."""
        if layer is None:
            layer = self.dialog.ls_layer_combo.currentLayer()
        if not layer or not layer.isValid() or self.interface is None:
            return
        canvas = self.interface.mapCanvas()
        transform = QgsCoordinateTransform(
            layer.crs(),
            canvas.mapSettings().destinationCrs(),
            QgsProject.instance(),
        )
        extent = transform.transformBoundingBox(layer.extent())
        extent.scale(self._CANVAS_SCALE_FACTOR)
        canvas.setExtent(extent)
        canvas.refresh()

    # -- Run (date discovery) ---------------------------------------------
    def handle_landsat_run(self):
        if self._run_worker is not None and self._run_worker.isRunning():
            return
        if self.gee_service and not self.gee_service.is_authenticated:
            self._show_auth_required_message()
            return

        layer = self.dialog.ls_layer_combo.currentLayer()
        if not layer:
            self.dialog.pop_message(_tr("Select an AOI layer."), "warning")
            return

        start_qdate = self.dialog.ls_date_start.date()
        end_qdate = self.dialog.ls_date_end.date()
        if start_qdate >= end_qdate:
            self.dialog.pop_message(_tr("End date must be after start date."), "warning")
            return

        try:
            aoi, _bbox = AOIService.get_ee_feature_colection_from_layer(
                layer, use_selected_features=False
            )
            self.shapely_geom = AOIService.get_shapely_geometry_from_layer(
                layer, use_selected_features=False
            )
            self._aoi_area_m2 = AOIService.get_area_m2_from_layer(
                layer, use_selected_features=False
            )
        except Exception as e:
            self.dialog.pop_message(str(e), "warning")
            return

        missions = self._selected_missions()
        if not missions:
            self.dialog.pop_message(_tr("Select at least one satellite."), "warning")
            return

        self.aoi = aoi
        self._date_start = start_qdate.toString("yyyy-MM-dd")
        self._date_end = end_qdate.toString("yyyy-MM-dd")
        params = {
            "date_start": self._date_start,
            "date_end": self._date_end,
            "use_cloud_mask": self.dialog.ls_chk_cloud_mask.isChecked(),
            "tier": 1,
            "min_valid_pct": self._min_valid_pct(),
            "aoi_area_m2": self._aoi_area_m2,
            "missions": missions,
        }

        self._set_run_busy(True)
        # Jump to Results immediately so the user sees progress (date list
        # loading + the time-series spinner) while both workers run.
        self.dialog.ls_date_combo.clear()
        self.dialog.ls_date_combo.addItem(_tr("Loading dates…"))
        self.dialog.ls_date_combo.setEnabled(False)
        self.dialog.ls_set_tab(2)

        self._run_worker = LandsatWorker(aoi, params)
        self._run_worker.finished.connect(self._on_run_done)
        self._run_worker.failed.connect(self._on_run_failed)
        self._run_worker.start()

        # Build the index time series in parallel — Run produces both the date
        # list and the chart.
        self._start_timeseries()

    def _set_run_busy(self, busy: bool):
        btn = self.dialog.ls_btn_run
        if busy:
            self._run_btn_text = self._run_btn_text or btn.text()
            btn.setText(_tr("Running..."))
        else:
            btn.setText(self._run_btn_text or btn.text())
        btn.setEnabled(not busy)

    def _release_run_worker(self):
        worker, self._run_worker = self._run_worker, None
        if worker is not None:
            worker.deleteLater()

    def _on_run_done(self, dated_missions):
        self._set_run_busy(False)
        self._release_run_worker()
        self.dated_missions = list(dated_missions or [])

        combo = self.dialog.ls_date_combo
        combo.blockSignals(True)
        combo.clear()
        combo.setEnabled(True)

        if not self.dated_missions:
            combo.blockSignals(False)
            self.dialog.pop_message(
                _tr("No Landsat images found for this AOI and date range."),
                "warning",
            )
            self.dialog.ls_set_tab(1)
            return

        for date, mission in self.dated_missions:
            combo.addItem(f"{date} — {mission}", (date, mission))
        # Default to the most recent acquisition (ISO dates sort lexically).
        latest = max(range(combo.count()), key=lambda i: combo.itemData(i)[0])
        combo.setCurrentIndex(latest)
        combo.blockSignals(False)
        self.handle_date_changed()
        self.dialog.ls_set_tab(2)

    def _on_run_failed(self, message):
        self._set_run_busy(False)
        self._release_run_worker()
        self.dialog.ls_date_combo.clear()
        self.dialog.ls_date_combo.setEnabled(True)
        self.dialog.ls_set_tab(1)
        self.dialog.pop_message(message, "warning")

    # -- shared helpers ----------------------------------------------------
    def _has_dates(self) -> bool:
        if not self.dated_missions or self.aoi is None:
            self.dialog.pop_message(_tr("Run the Landsat analysis first."), "warning")
            return False
        return True

    def _selected_date_mission(self):
        """(date, mission) for the currently selected date combo entry."""
        data = self.dialog.ls_date_combo.currentData()
        if isinstance(data, (tuple, list)) and len(data) == 2:
            return data[0], data[1]
        return None, None

    def handle_date_changed(self, _index=None):
        """React to the selected acquisition date: gate the super-res actions to
        panchromatic sensors and relabel the index / multispectral sections with
        the sensor's true native resolution (Sentinel-2 is 10 m, Landsat/HLS
        30 m), so the captions stop claiming a fixed 30 m."""
        _date, mission = self._selected_date_mission()
        spec = SATELLITES.get(mission)

        # Super-res = pan-sharpening, Landsat-only (needs a panchromatic band).
        enabled = bool(spec and spec.has_superres)
        for btn in (self.dialog.ls_btn_sr_preview, self.dialog.ls_btn_sr_download):
            btn.setEnabled(enabled)
            btn.setToolTip(
                "" if enabled
                else _tr("Super-resolution needs a panchromatic band (Landsat only).")
            )
        cap_sr = getattr(self.dialog, "ls_cap_sr", None)
        if cap_sr is not None:
            cap_sr.setText(
                _tr("SUPER-RESOLUTION RGB (15 m)") if enabled
                else _tr("SUPER-RESOLUTION RGB — Landsat only (disabled)")
            )

        # Native-resolution labels for the index + multispectral sections.
        px = spec.pixel_size if spec else 30
        cap_vi = getattr(self.dialog, "ls_cap_vi", None)
        if cap_vi is not None:
            cap_vi.setText(_tr("VEGETATION INDEX (%d m)") % px)
        cap_ms = getattr(self.dialog, "ls_cap_ms", None)
        if cap_ms is not None:
            cap_ms.setText(_tr("MULTISPECTRAL RGB (%d m)") % px)

        # Single-date index picker limited to what this sensor can compute
        # (MODIS = red/nir indices only).
        allowed_vi = (
            self._ordered_indices(spec.index_keys) if spec else list(LANDSAT_INDEX_ORDER)
        )
        self._refill_index_combo(getattr(self.dialog, "ls_vi_index_combo", None), allowed_vi)

        # Multispectral RGB needs ≥3 visible bands; MODIS (red/nir) has too few.
        ms_ok = bool(spec and spec.multispectral)
        for btn in (self.dialog.ls_btn_ms_preview, self.dialog.ls_btn_ms_download):
            btn.setEnabled(ms_ok)
            btn.setToolTip(
                "" if ms_ok
                else _tr("This sensor has too few bands for an RGB composite.")
            )

    def _buffer_meters(self) -> float:
        slider = getattr(self.dialog, "ls_buffer_slider", None)
        if slider is None:
            return 0
        value = slider.value()
        return 0 if -3 <= value <= 3 else value  # match the UI dead-zone

    def _cloud_mask(self) -> bool:
        return self.dialog.ls_chk_cloud_mask.isChecked()

    def _min_valid_pct(self) -> float:
        """Min valid-pixel coverage % from the Inputs slider (0 = no filter)."""
        slider = getattr(self.dialog, "ls_min_valid_slider", None)
        return slider.value() if slider is not None else 0

    def _selected_missions(self) -> list:
        """Missions whose Inputs-tab checkbox is ticked, in registry order.
        Limiting these cuts one Earth-Engine query per dropped sensor on Run.
        Falls back to all missions when no checkboxes exist (headless/tests)."""
        checks = getattr(self.dialog, "ls_sensor_checks", None)
        if not checks:
            return list(MISSIONS)
        return [m for m, chk in checks.items() if chk.isChecked()]

    # -- index-picker filtering (sensor capability) -----------------------
    @staticmethod
    def _ordered_indices(allowed_names) -> list:
        """``allowed_names`` rendered in the canonical display order."""
        allowed = set(allowed_names)
        return [name for name in LANDSAT_INDEX_ORDER if name in allowed]

    def _refill_index_combo(self, combo, allowed):
        """Repopulate an index combo with ``allowed`` (ordered) display names,
        keeping the current pick if it survives, else falling back to the first
        valid one (NDVI when present)."""
        if combo is None:
            return
        previous = combo.currentData() or combo.currentText()
        combo.blockSignals(True)
        combo.clear()
        for name in allowed:
            combo.addItem(name, name)
        index = combo.findData(previous)
        if index < 0:
            index = combo.findData("NDVI")
        if index < 0 and combo.count():
            index = 0
        if index >= 0:
            combo.setCurrentIndex(index)
        combo.blockSignals(False)

    def _allowed_ts_indices(self) -> list:
        """Indices every selected sensor can compute — the time-series chart
        overlays all of them on one index, so it must be common to all. MODIS
        (red/nir only) is the usual limiter."""
        specs = [SATELLITES[m] for m in self._selected_missions() if m in SATELLITES]
        if not specs:
            return list(LANDSAT_INDEX_ORDER)
        common = set(LANDSAT_INDEX_ORDER)
        for spec in specs:
            common &= set(spec.index_keys)
        return self._ordered_indices(common)

    def handle_sensors_changed(self, _checked=None):
        """Sensor checkbox toggled: restrict the time-series index picker to the
        indices common to the still-selected sensors."""
        self._refill_index_combo(
            getattr(self.dialog, "ls_index_combo", None),
            self._allowed_ts_indices(),
        )

    # -- single-date preview / download -----------------------------------
    def handle_sr_preview(self):
        self._run_single("superres", to_folder=False)

    def handle_sr_download(self):
        self._run_single("superres", to_folder=True)

    def handle_index_preview(self):
        self._run_single("index", to_folder=False)

    def handle_index_download(self):
        self._run_single("index", to_folder=True)

    def handle_ms_preview(self):
        self._run_single("multispectral", to_folder=False)

    def handle_ms_download(self):
        self._run_single("multispectral", to_folder=True)

    def _run_single(self, kind: str, to_folder: bool):
        if not self._has_dates():
            return
        if self._preview_worker is not None and self._preview_worker.isRunning():
            return

        date, mission = self._selected_date_mission()
        if not date:
            self.dialog.pop_message(_tr("Select a date first."), "warning")
            return

        # The single-date index image uses the Results-tab index picker (so a
        # different index can be downloaded without re-running); other kinds
        # ignore index_name and fall back to the Inputs-tab value.
        if kind == "index":
            index_name = self.dialog.ls_vi_index_combo.currentData() or "NDVI"
        else:
            index_name = self.dialog.ls_index_combo.currentData() or "NDVI"
        mode = self.dialog.ls_ms_mode_combo.currentData() or "RGB: Real Color"
        folder = (
            SettingsManager.load_download_folder()
            if to_folder
            else tempfile.gettempdir()
        )

        self._set_single_busy(kind, True)
        self._preview_worker = LandsatPreviewWorker(
            kind,
            self.aoi,
            date,
            mission,
            index_name,
            mode,
            self._cloud_mask(),
            1,
            self._buffer_meters(),
            folder,
            self._min_valid_pct(),
            self._aoi_area_m2,
        )
        self._preview_worker.finished.connect(
            lambda path, k: self._on_single_done(path, k, to_folder)
        )
        self._preview_worker.failed.connect(self._on_single_failed)
        self._preview_worker.start()

    def _single_buttons(self, kind: str):
        if kind == "superres":
            return (self.dialog.ls_btn_sr_preview, self.dialog.ls_btn_sr_download)
        if kind == "index":
            return (self.dialog.ls_btn_index_preview, self.dialog.ls_btn_index_download)
        return (self.dialog.ls_btn_ms_preview, self.dialog.ls_btn_ms_download)

    def _set_single_busy(self, kind: str, busy: bool):
        btns = self._single_buttons(kind)
        if busy:
            self._preview_btn_texts = {b: b.text() for b in btns}
            for b in btns:
                b.setText(_tr("Loading..."))
        elif self._preview_btn_texts:
            for b in btns:
                if b in self._preview_btn_texts:
                    b.setText(self._preview_btn_texts[b])
        for b in btns:
            b.setEnabled(not busy)

    def _on_single_done(self, path: str, kind: str, to_folder: bool):
        self._set_single_busy(kind, False)
        worker, self._preview_worker = self._preview_worker, None
        if worker is not None:
            worker.deleteLater()

        date, mission = self._selected_date_mission()
        mission = mission or "Landsat"
        if kind == "index":
            index_name = self.dialog.ls_vi_index_combo.currentData() or "NDVI"
            ramp = self.dialog.ls_index_ramp_combo.currentText()
            RasterRendererUtils.load_pseudocolor_raster(
                path, f"{mission} {index_name} {date}", 1, ramp
            )
        elif kind == "superres":
            self._add_rgb_raster(path, f"{mission} Super-Res {date}", (1, 2, 3))
        else:
            self._add_rgb_raster(path, f"{mission} RGB {date}", (1, 2, 3))

        if self.interface is not None:
            action = _tr("downloaded and loaded") if to_folder else _tr("loaded")
            self.interface.messageBar().pushMessage(
                "FARM tools", _tr("Landsat image %s into QGIS.") % action
            )

    def _on_single_failed(self, message: str):
        worker, self._preview_worker = self._preview_worker, None
        if worker is not None:
            worker.deleteLater()
        for kind in ("superres", "index", "multispectral"):
            self._set_single_busy(kind, False)
        self.dialog.pop_message(message, "warning")

    # -- batch (super-res, all dates) -------------------------------------
    def handle_batch_download(self):
        if not self._has_dates():
            return
        if self._batch_worker is not None and self._batch_worker.isRunning():
            return

        aoi = self.aoi
        buffer_m = self._buffer_meters()
        use_cloud_mask = self._cloud_mask()
        folder = SettingsManager.load_download_folder()

        # Batch produces the super-res (pan-sharpened) image, so only sensors
        # with a panchromatic band qualify. Drop the rest and tell the user.
        pairs = [
            (date, mission) for date, mission in self.dated_missions
            if SATELLITES.get(mission) and SATELLITES[mission].has_superres
        ]
        skipped = len(self.dated_missions) - len(pairs)
        if not pairs:
            self.dialog.pop_message(
                _tr("Batch super-resolution needs a panchromatic sensor "
                    "(Landsat); none of the available dates qualify."),
                "warning",
            )
            return
        if skipped:
            self.dialog.pop_message(
                _tr("Skipping %d non-Landsat date(s): super-resolution needs a "
                    "panchromatic band.") % skipped,
                "info",
            )

        self._batch_dialog = QProgressDialog(
            _tr("Preparing batch download..."),
            _tr("Cancel"),
            0,
            len(pairs),
            self.dialog,
        )
        self._batch_dialog.setWindowTitle(_tr("Batch Download Progress"))
        self._batch_dialog.setModal(True)
        self._batch_dialog.show()

        self._batch_worker = LandsatBatchWorker(
            aoi, pairs, use_cloud_mask, 1, buffer_m, folder,
            self._min_valid_pct(), self._aoi_area_m2,
        )
        self._batch_worker.progress.connect(self._on_batch_progress)
        self._batch_worker.finished.connect(self._on_batch_done)
        self._batch_worker.cancelled.connect(self._on_batch_cancelled)
        self._batch_worker.failed.connect(self._on_batch_failed)
        self._batch_dialog.canceled.connect(self._batch_worker.request_cancel)
        self._batch_worker.start()

    def _on_batch_progress(self, completed: int, total: int):
        if self._batch_dialog is None:
            return
        self._batch_dialog.setMaximum(total)
        self._batch_dialog.setValue(completed)
        self._batch_dialog.setLabelText(
            _tr("Downloaded %d of %d") % (completed, total)
        )

    def _on_batch_done(self, successful: int, total: int, paths: list):
        self._close_batch_dialog()
        self._load_downloaded_images(paths)
        failed = total - successful
        msg = _tr("Batch download complete: %d/%d successful") % (successful, total)
        if failed > 0:
            msg += _tr(" (%d failed)") % failed
        self.dialog.pop_message(msg, "warning" if failed > 0 else "info")
        self._batch_worker = None

    def _on_batch_cancelled(self, successful: int, total: int, paths: list):
        self._close_batch_dialog()
        self._load_downloaded_images(paths)
        self.dialog.pop_message(
            _tr("Batch download cancelled. %d/%d downloaded.") % (successful, total),
            "info",
        )
        self._batch_worker = None

    def _on_batch_failed(self, message: str):
        self._close_batch_dialog()
        self.dialog.pop_message(_tr("Batch download failed: %s") % message, "warning")
        self._batch_worker = None

    def _close_batch_dialog(self):
        if self._batch_dialog is not None:
            self._batch_dialog.close()
            self._batch_dialog = None

    def _load_downloaded_images(self, paths: list):
        for path in paths:
            try:
                name = os.path.splitext(os.path.basename(path))[0]
                self._add_rgb_raster(path, name, (1, 2, 3))
            except Exception:
                continue

    # -- index time series (agrigee_lite SITS) ----------------------------
    def _start_timeseries(self):
        """Kick off the time-series chart for the Inputs-tab index + reducer.
        Called by Run, so the chart and the date list are produced together."""
        if self.shapely_geom is None:
            return
        if self._ts_worker is not None and self._ts_worker.isRunning():
            return

        index_name = self.dialog.ls_index_combo.currentData() or "NDVI"
        reducer = self.dialog.ls_ts_reducer_combo.currentData() or "median"
        self._ts_index_name = index_name

        self.dialog.ls_web_view.setHtml(self._loading_html(index_name))
        self._ts_worker = LandsatTimeseriesWorker(
            self.shapely_geom,
            self._date_start,
            self._date_end,
            index_name,
            self._cloud_mask(),
            1,
            reducer,
            self._min_valid_pct(),
            self._aoi_area_m2,
            self._selected_missions(),
        )
        self._ts_worker.finished.connect(self._on_ts_done)
        self._ts_worker.failed.connect(self._on_ts_failed)
        self._ts_worker.start()

    @staticmethod
    def _loading_html(index_name: str) -> str:
        return (
            "<!DOCTYPE html><html><head><meta charset='utf-8'><style>"
            "html,body{height:100%;margin:0;font-family:Arial,sans-serif;background:#fff}"
            ".box{position:absolute;top:50%;left:50%;transform:translate(-50%,-50%);"
            "text-align:center;color:#616161}.spinner{width:34px;height:34px;margin:0 auto 12px;"
            "border:3px solid #e0e0e0;border-top-color:#1b6b39;border-radius:50%;"
            "animation:spin .9s linear infinite}@keyframes spin{to{transform:rotate(360deg)}}"
            "</style></head><body><div class='box'><div class='spinner'></div>"
            f"<div>Building {index_name} multi-satellite time series…</div>"
            "</div></body></html>"
        )

    def _ts_message_html(self, text: str) -> str:
        return (
            "<!DOCTYPE html><html><head><meta charset='utf-8'><style>"
            "html,body{height:100%;margin:0;font-family:Arial,sans-serif;background:#fff}"
            ".box{position:absolute;top:50%;left:50%;transform:translate(-50%,-50%);"
            "text-align:center;color:#9e9e9e;font-size:12px;padding:0 24px}"
            f"</style></head><body><div class='box'>{text}</div></body></html>"
        )

    def _on_ts_done(self, dataframe, index_name):
        worker, self._ts_worker = self._ts_worker, None
        if worker is not None:
            worker.deleteLater()

        self._ts_index_name = index_name
        self._ts_df = dataframe
        if dataframe is None or dataframe.empty:
            # Non-modal: the date-list worker already reports an empty result.
            self.dialog.ls_web_view.setHtml(
                self._ts_message_html(_tr("No time-series data for this AOI and date range."))
            )
            return
        self._render_timeseries(dataframe, index_name)

    def _on_ts_failed(self, message: str):
        worker, self._ts_worker = self._ts_worker, None
        if worker is not None:
            worker.deleteLater()
        # Non-modal: avoid stacking a dialog on top of the Run date-list flow.
        self.dialog.ls_web_view.setHtml(
            self._ts_message_html(_tr("Could not build the time series."))
        )

    def _render_timeseries(self, dataframe, index_name):
        """Plot the combined Landsat index series into the results web view via
        the shared plotly renderer (same as the optical page)."""
        try:
            html = render_multiseries_chart_html(
                dataframe,
                group_col="mission",
                title=_tr("%s Multi-Satellite Time Series") % index_name,
                ylabel=_tr("%s AOI average") % index_name,
                colors=self._MISSION_COLORS,
            )
        except Exception:
            self.dialog.ls_web_view.setHtml(
                self._ts_message_html(_tr("Could not render the chart."))
            )
            return
        fd, path = tempfile.mkstemp(suffix=".html", prefix="farm_tools_landsat_ts_")
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(html)
        self.dialog.ls_web_view.load(QUrl.fromLocalFile(path))

        if self._plot_path and os.path.exists(self._plot_path):
            try:
                os.remove(self._plot_path)
            except OSError:
                pass
        self._plot_path = path

    def handle_open_browser(self):
        """Open the current time series in the system browser."""
        if self._ts_df is None or self._ts_df.empty:
            self.dialog.pop_message(_tr("Plot a time series first."), "warning")
            return
        html = render_multiseries_chart_html(
            self._ts_df,
            group_col="mission",
            hide_toolbar=False,
            title=_tr("%s Multi-Satellite Time Series") % self._ts_index_name,
            ylabel=_tr("%s AOI average") % self._ts_index_name,
            colors=self._MISSION_COLORS,
        )
        with tempfile.NamedTemporaryFile(
            suffix=".html", delete=False, mode="w", encoding="utf-8"
        ) as f:
            f.write(html)
            path = f.name
        QDesktopServices.openUrl(QUrl.fromLocalFile(path))

    def handle_export_csv(self):
        """Save the current multi-satellite time series (dates, AOI average,
        mission) to a CSV chosen by the user."""
        if self._ts_df is None or self._ts_df.empty:
            self.dialog.pop_message(_tr("Plot a time series first."), "warning")
            return

        default_name = "MultiSatellite_%s_timeseries.csv" % self._ts_index_name
        file_path, _ = QFileDialog.getSaveFileName(
            self.dialog,
            _tr("Export Time Series as CSV"),
            default_name,
            _tr("CSV Files (*.csv);;All Files (*)"),
        )
        if not file_path:
            return

        try:
            self._ts_df.to_csv(file_path, index=False)
            self.dialog.pop_message(
                _tr("CSV exported successfully to %s") % file_path, "info"
            )
        except Exception as e:
            self.dialog.pop_message(_tr("Failed to export CSV: %s") % str(e), "warning")

    # -- rendering ---------------------------------------------------------
    def _add_rgb_raster(self, path: str, name: str, bands=(1, 2, 3)):
        """Load a 3-band GeoTIFF as an RGB composite with a 2–98% cumulative-cut
        stretch per band. Downloads are written in R, G, B band order."""
        layer = QgsRasterLayer(path, name)
        if not layer.isValid():
            return

        provider = layer.dataProvider()
        red, green, blue = bands
        renderer = QgsMultiBandColorRenderer(provider, red, green, blue)

        extent = layer.extent()
        for band, set_enhancement in (
            (red, renderer.setRedContrastEnhancement),
            (green, renderer.setGreenContrastEnhancement),
            (blue, renderer.setBlueContrastEnhancement),
        ):
            val_min, val_max = provider.cumulativeCut(band, 0.02, 0.98, extent, 250000)
            ce = QgsContrastEnhancement(provider.dataType(band))
            ce.setContrastEnhancementAlgorithm(
                QgsContrastEnhancement.StretchToMinimumMaximum
            )
            ce.setMinimumValue(val_min)
            ce.setMaximumValue(val_max)
            set_enhancement(ce)

        layer.setRenderer(renderer)
        RasterRendererUtils.add_layer_to_project(layer, at_top=True)
        layer.triggerRepaint()
