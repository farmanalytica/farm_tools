# -*- coding: utf-8 -*-
"""
Controller for the Optical (Sentinel-2) page.

This milestone only proves the Earth Engine -> pandas path: clicking Run on the
Inputs tab fetches the vegetation-index time series and prints the resulting
DataFrame, including filter metadata, to the QGIS/Python console.
"""

import json
import os
import tempfile
from datetime import datetime, timedelta

import pandas as pd

from qgis.PyQt.QtCore import QCoreApplication, QTimer, QUrl
from qgis.PyQt.QtGui import QDesktopServices
from qgis.PyQt.QtWidgets import QFileDialog, QProgressDialog
from qgis.core import (
    QgsContrastEnhancement,
    QgsCoordinateTransform,
    QgsMultiBandColorRenderer,
    QgsProject,
    QgsRasterLayer,
)

from qgis.core import (
    QgsCoordinateReferenceSystem,
    QgsGeometry,
    QgsMapLayer,
    QgsWkbTypes,
)

from ..managers.settings_manager import SettingsManager
from ..services.aoi_service import AOIService, _remove_z_dimension
from ..services.optical_service import OpticalService
from ..tools.aoi_draw_tool import start_draw_aoi
from ..tools.point_capture_tool import PointCaptureTool
from ..tools.indexes import validate_custom, save_custom_indexes, load_custom_indexes
from ..view.optical_filter_dialog import DEFAULT_FILTER_SETTINGS
from ..view.optical_index_info import CUSTOM_INDEX_LABEL, INDEX_ORDER
from ..renderers.raster_renderer_utils import RasterRendererUtils
from ..view.sar_plot import (
    _MULTISERIES_PALETTE,
    render_chart_html,
    render_multiseries_chart_html,
)
from ..services.nasa_power_service import NasaPowerService
from ..workers.batch_download_worker import BatchDownloadWorker
from ..workers.climate_worker import ClimateWorker
from ..workers.optical_analysis_worker import OpticalAnalysisWorker
from ..workers.optical_composite_worker import OpticalCompositeWorker
from ..workers.optical_preview_worker import OpticalPreviewWorker
from ..workers.optical_worker import OpticalWorker


def _tr(text):
    return QCoreApplication.translate("RAVI", text)


_LOADING_HTML = """<!DOCTYPE html><html><head><meta charset="utf-8"><style>
html,body{height:100%;margin:0;font-family:Arial,sans-serif;background:#fff}
.box{position:absolute;top:50%;left:50%;transform:translate(-50%,-50%);
text-align:center;color:#616161}.spinner{width:34px;height:34px;margin:0 auto 12px;
border:3px solid #e0e0e0;border-top-color:#1b6b39;border-radius:50%;
animation:spin .9s linear infinite}@keyframes spin{to{transform:rotate(360deg)}}
</style></head><body><div class="box"><div class="spinner"></div>
<div>Fetching Sentinel-2 time series...</div></div></body></html>"""


class OpticalCtrl:
    """Coordinate the Optical Inputs tab run action."""

    _CANVAS_SCALE_FACTOR = 1.5

    def __init__(self, dialog, interface=None, gee_service=None):
        self.dialog = dialog
        self.interface = interface
        self.gee_service = gee_service

        self.aoi = None
        self.dataframe = None
        self._current_index = "NDVI"
        self._optical_worker: OpticalWorker | None = None
        self._run_btn_text: str | None = None
        self._draw_tool = None
        self._plot_path: str | None = None
        self._filter_settings = dict(DEFAULT_FILTER_SETTINGS)
        self._active_dates: list | None = None
        self._date_filter_dialog = None
        # Date-range slider under the plot. ``_date_range`` is an inclusive
        # (lo_iso, hi_iso) pair, or None when the full span is selected — it
        # ANDs with the thresholds and the manual date selection inside
        # _filtered_dataframe, so every consumer (plot, composite, batch
        # download, CSV, single-date dropdown) respects it automatically.
        self._date_range: tuple | None = None
        self._range_epoch: datetime | None = None
        self._range_full: tuple | None = None
        self._batch_worker: BatchDownloadWorker | None = None
        self._batch_dialog: QProgressDialog | None = None
        self._preview_worker: OpticalPreviewWorker | None = None
        self._preview_btn_texts: tuple | None = None
        self._composite_worker: OpticalCompositeWorker | None = None
        self._composite_btn_texts: tuple | None = None
        self._composite_index: str | None = None
        # SCL settings captured at run time, replayed for the composite so it
        # matches the masking behind the plotted series.
        self._run_apply_scl = True
        self._run_invalid_scl: list[int] = []
        # Run date range (the time series window), reused for the climate fetch.
        self._date_start: str | None = None
        self._date_end: str | None = None
        # NASA POWER climate overlay.
        self._climate_worker: ClimateWorker | None = None
        self._climate_btn_text: str | None = None
        self._climate_df = None

        # Point / per-feature analysis. The three views (AOI / Points /
        # Features) share the one results web view; _active_plot_view tracks
        # which is shown. Point and feature series are extracted over the full
        # run date range (independent of the AOI threshold/date filters).
        self._active_plot_view = "aoi"
        self._point_tool: PointCaptureTool | None = None
        self._point_series: dict = {}  # label -> rows [{date, value}]
        self._point_colors: dict = {}  # label -> css hex
        self._feature_series: dict = {}
        self._feature_colors: dict = {}
        self._analysis_worker: OpticalAnalysisWorker | None = None
        self._analysis_target: str | None = None
        self._job_queue: list = []
        self._feature_btn_text: str | None = None
        self._plot_view_paths: list = []

        # The "Adjust filter" dialog shows a live image count (cheap) and only
        # re-renders the plot when the user clicks OK.
        self.dialog.optical_filter_count_fn = self.count_matching
        self.dialog.on_optical_filter_applied = self.apply_filter_settings
        self.dialog.s2_filter_settings = dict(DEFAULT_FILTER_SETTINGS)
        self.update_index_combobox()

        # Re-render after the date-range slider settles (same debounce the
        # MapBiomas transition slider uses); the label updates on every tick.
        self._range_timer = QTimer(self.dialog)
        self._range_timer.setSingleShot(True)
        self._range_timer.setInterval(200)
        self._range_timer.timeout.connect(self._on_date_range_settled)

    def _release_worker(self):
        worker, self._optical_worker = self._optical_worker, None
        if worker is not None:
            worker.deleteLater()

    def _show_auth_required_message(self):
        self.dialog.pop_message(
            _tr(
                "Authentication is required to download optical data. "
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
            self.interface, self.dialog.s2_layer_combo, self.dialog.s2_btn_draw_aoi
        )

    def handle_layer_changed(self, layer=None):
        """Zoom to the selected optical AOI layer."""

        if layer is None:
            layer = self.dialog.s2_layer_combo.currentLayer()

        # Keep the Feature-ID dropdown in sync with the selected layer's
        # attributes, even when there is no canvas / interface to zoom.
        self._populate_feature_id_combo(layer)
        self._update_aoi_area_label(layer)

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

    def _update_aoi_area_label(self, layer):
        """Show the dissolved AOI's total area (hectares) below the layer picker."""

        if not layer or not layer.isValid():
            self.dialog.s2_aoi_area_lbl.setText("")
            return
        try:
            area_ha = AOIService.get_area_m2_from_layer(
                layer, use_selected_features=False
            ) / 10_000.0
        except Exception:
            self.dialog.s2_aoi_area_lbl.setText("")
            return
        self.dialog.s2_aoi_area_lbl.setText(
            _tr("Total area: {0:,.2f} ha").format(area_ha)
        )

    def handle_optical_run(self):
        """Fetch the optical time series and plot it on the results page."""

        if self._optical_worker is not None and self._optical_worker.isRunning():
            return

        if self.gee_service and not self.gee_service.is_authenticated:
            self._show_auth_required_message()
            return

        layer = self.dialog.s2_layer_combo.currentLayer()
        if not layer:
            self.dialog.pop_message(_tr("Select an AOI layer."), "warning")
            return

        start_qdate = self.dialog.s2_date_start.date()
        end_qdate = self.dialog.s2_date_end.date()
        if start_qdate >= end_qdate:
            self.dialog.pop_message(
                _tr("End date must be after start date."), "warning"
            )
            return

        index_name = self.dialog.s2_index_combo.currentData() or "NDVI"
        custom_expression = None
        all_customs = load_custom_indexes()

        if index_name in all_customs:
            custom_expression = all_customs[index_name]

        try:
            aoi, _bbox = AOIService.get_ee_feature_colection_from_layer(
                layer, use_selected_features=False
            )
        except Exception as e:
            self.dialog.pop_message(str(e), "warning")
            return

        self.aoi = aoi
        self._run_apply_scl = self.dialog.s2_chk_apply_scl.isChecked()
        self._run_invalid_scl = self._selected_invalid_scl_values()
        self._date_start = start_qdate.toString("yyyy-MM-dd")
        self._date_end = end_qdate.toString("yyyy-MM-dd")
        # A fresh run invalidates any climate overlay from the previous AOI/range.
        self._climate_df = None
        params = {
            "date_start": self._date_start,
            "date_end": self._date_end,
            "index_name": index_name,
            "apply_scl": self._run_apply_scl,
            "invalid_scl_values": self._run_invalid_scl,
            "custom_expression": custom_expression,
            "reducer": self.dialog.s2_ts_reducer_combo.currentData() or "mean",
        }

        self._current_index = index_name
        self._set_run_busy(True)
        self.dialog.s2_web_view.setHtml(_LOADING_HTML)
        self.dialog.s2_set_tab(2)

        self._optical_worker = OpticalWorker(aoi, params)
        self._optical_worker.finished.connect(self._on_optical_done)
        self._optical_worker.failed.connect(self._on_optical_failed)
        self._optical_worker.start()

    def _selected_invalid_scl_values(self) -> list[int]:
        checks = getattr(self.dialog, "s2_scl_checks", {})
        return [value for value, checkbox in checks.items() if checkbox.isChecked()]

    def _set_run_busy(self, busy: bool):
        btn = self.dialog.s2_btn_run
        if busy:
            self._run_btn_text = self._run_btn_text or btn.text()
            btn.setText(_tr("Running..."))
        else:
            btn.setText(self._run_btn_text or btn.text())
        btn.setEnabled(not busy)

    def _on_optical_done(self, data_rows, index_name):
        self._set_run_busy(False)
        self._release_worker()

        if not data_rows:
            self.dataframe = pd.DataFrame()
            self.dialog.s2_web_view.setHtml("")
            self._date_range = None
            self._range_epoch = None
            self._range_full = None
            self.dialog.s2_date_range_bar.setVisible(False)
            self.dialog.s2_set_tab(1)
            self.dialog.pop_message(
                _tr("No Sentinel-2 images found for this date range."), "warning"
            )
            return

        columns = [
            "date",
            "AOI_average",
            "cloud_pct",
            "valid_pixel_pct",
            "coverage_pct",
            "image_id",
        ]
        self.dataframe = pd.DataFrame(data_rows)
        self.dataframe = self.dataframe.reindex(columns=columns)
        self._current_index = index_name
        self._active_dates = None

        # A fresh run replaces the AOI/range, so any captured points or feature
        # series no longer apply; clear them and return to the AOI view.
        self._clear_point_state()
        self._feature_series = {}
        self._feature_colors = {}
        self._active_plot_view = "aoi"
        self._populate_feature_id_combo()

        self._configure_date_range_slider()
        self._refresh_result_dates()
        self._render_timeseries()
        self._update_view_buttons()
        self.dialog.s2_set_tab(2)

    def apply_filter_settings(self, settings: dict):
        """Apply new threshold filters (called on Adjust-filter OK).

        Applying thresholds changes which dates qualify, so it overrides any
        manual date selection (Filter dates) and rebuilds the single-image date
        dropdown from the newly filtered set.
        """
        self._filter_settings = dict(settings)
        self._active_dates = None
        if self.dataframe is not None and not self.dataframe.empty:
            self._refresh_result_dates()
            self._render_timeseries()

    def count_matching(self, settings: dict) -> int:
        """Count cached images passing the given thresholds (live, no render)."""
        if self.dataframe is None or self.dataframe.empty:
            return 0
        return int(self._filter_mask(self.dataframe, settings).sum())

    @staticmethod
    def _filter_mask(df, s):
        return (
            (df["cloud_pct"] <= s["cloud_scene_max"])
            & (df["valid_pixel_pct"] >= s["valid_pixel_min"])
            & (df["coverage_pct"] >= s["coverage_min"])
        )

    def _threshold_dates(self) -> list:
        """Dates passing the current thresholds (ignores manual date selection)."""
        df = self.dataframe[self._filter_mask(self.dataframe, self._filter_settings)]
        return df["date"].dropna().astype(str).tolist()

    def _filtered_dataframe(self) -> pd.DataFrame:
        """Cached series after thresholds, the manual date selection and the
        date-range slider."""
        df = self.dataframe[self._filter_mask(self.dataframe, self._filter_settings)]
        if self._active_dates is not None:
            df = df[df["date"].astype(str).isin(self._active_dates)]
        if self._date_range is not None:
            lo, hi = self._date_range
            dates = df["date"].astype(str)
            df = df[(dates >= lo) & (dates <= hi)]
        return df

    # -- date-range slider (below the plot) --------------------------------
    def _configure_date_range_slider(self):
        """Adopt the fresh run's date span (full range selected) and reveal
        the slider. Values are day offsets from the first acquisition; the
        label_fn maps them back to ISO dates on the handles."""
        self._date_range = None
        dates = self.dataframe["date"].dropna().astype(str).tolist()
        if not dates:
            self._range_epoch = None
            self._range_full = None
            self.dialog.s2_date_range_bar.setVisible(False)
            return
        lo_iso, hi_iso = min(dates), max(dates)
        self._range_epoch = datetime.strptime(lo_iso, "%Y-%m-%d")
        self._range_full = (lo_iso, hi_iso)
        span = (datetime.strptime(hi_iso, "%Y-%m-%d") - self._range_epoch).days
        slider = self.dialog.s2_date_range_slider
        slider.label_fn = self._range_offset_to_iso
        slider.set_span(0, span, 0, span)
        self._update_date_range_label()
        self.dialog.s2_date_range_bar.setVisible(True)

    def _range_offset_to_iso(self, offset) -> str:
        if self._range_epoch is None:
            return str(offset)
        day = self._range_epoch + timedelta(days=int(round(offset)))
        return day.strftime("%Y-%m-%d")

    def _slider_range_dates(self) -> tuple:
        slider = self.dialog.s2_date_range_slider
        return (
            self._range_offset_to_iso(slider.low()),
            self._range_offset_to_iso(slider.high()),
        )

    def _update_date_range_label(self):
        lo_iso, hi_iso = self._slider_range_dates()
        self.dialog.s2_date_range_lbl.setText(
            _tr("Dates: {0} – {1}").format(lo_iso, hi_iso)
        )

    def handle_date_range_changed(self, _value=None):
        """Slider tick: track the new range, refresh the label live and start
        the debounce that re-renders once the handle settles."""
        if self._range_epoch is None:
            return
        lo_iso, hi_iso = self._slider_range_dates()
        self._date_range = (
            None if (lo_iso, hi_iso) == self._range_full else (lo_iso, hi_iso)
        )
        self._update_date_range_label()
        self._range_timer.start()

    def _on_date_range_settled(self):
        if self.dataframe is None or self.dataframe.empty:
            return
        self._refresh_result_dates()
        self._render_timeseries()

    def _refresh_result_dates(self):
        """Repopulate the single-image date dropdown from the filtered series."""
        dates = self._filtered_dataframe()["date"].dropna().astype(str).tolist()
        self.dialog.s2_available_dates = dates
        combo = self.dialog.s2_result_date_combo
        previous = combo.currentText()
        combo.blockSignals(True)
        combo.clear()
        combo.addItems(dates)
        if previous in dates:
            combo.setCurrentText(previous)
        elif dates:
            # Default to the most recent acquisition (ISO dates sort lexically).
            combo.setCurrentText(max(dates))
        combo.blockSignals(False)

    # -- Filter dates (manual per-date include/exclude) -------------------
    def handle_filter_dates(self):
        if self.dataframe is None or self.dataframe.empty:
            self.dialog.pop_message(_tr("Run the RAVI analysis first."), "warning")
            return

        if self._date_filter_dialog is not None:
            self._date_filter_dialog.raise_()
            self._date_filter_dialog.activateWindow()
            return

        from ..view.sar_date_filter_dialog import SARDateFilterDialog

        self._date_filter_dialog = SARDateFilterDialog(
            self._threshold_dates(), self._active_dates, parent=self.dialog
        )
        self._date_filter_dialog.filter_changed.connect(self._on_dates_changed)
        self._date_filter_dialog.finished.connect(self._on_date_filter_closed)
        self._date_filter_dialog.show()

    def _on_dates_changed(self, selected_dates):
        all_dates = self._threshold_dates()
        self._active_dates = (
            None if set(selected_dates) == set(all_dates) else list(selected_dates)
        )
        self._refresh_result_dates()
        self._render_timeseries()

    def _on_date_filter_closed(self):
        self._date_filter_dialog = None

    # -- export actions (time-series toolbar) -----------------------------
    def _has_results(self) -> bool:
        if self.dataframe is None or self.dataframe.empty:
            self.dialog.pop_message(_tr("Run the RAVI analysis first."), "warning")
            return False
        return True

    def _plot_dataframe(self):
        return (
            self._filtered_dataframe()
            .rename(columns={"date": "dates"})
            .dropna(subset=["dates", "AOI_average"])
        )

    def handle_open_browser(self):
        """Open the plot currently toggled on (AOI / Points / Features) in the
        system browser."""
        if not self._has_results():
            return

        index_name = self._current_index
        if self._active_plot_view == "points" and self._point_series:
            html = self._multiseries_html(
                self._point_series,
                self._point_colors,
                _tr("%s — Points") % index_name,
                hide_toolbar=False,
            )
        elif self._active_plot_view == "features" and self._feature_series:
            html = self._multiseries_html(
                self._feature_series,
                self._feature_colors,
                _tr("%s — Features") % index_name,
                hide_toolbar=False,
            )
        else:
            html = render_chart_html(
                self._plot_dataframe(),
                hide_toolbar=False,
                title=_tr("%s Time Series") % index_name,
                ylabel=_tr("%s AOI average") % index_name,
                precip_bars=self._precip_bars(),
            )
        if html is None:
            return
        with tempfile.NamedTemporaryFile(
            suffix=".html", delete=False, mode="w", encoding="utf-8"
        ) as f:
            f.write(html)
            path = f.name
        QDesktopServices.openUrl(QUrl.fromLocalFile(path))

    def handle_export_csv(self):
        """Export the current (filtered) time series as CSV."""
        if not self._has_results():
            return

        date_str = datetime.now().strftime("%Y%m%d")
        default_filename = f"optical_{self._current_index}_timeseries_{date_str}.csv"
        file_path, _ = QFileDialog.getSaveFileName(
            self.dialog,
            _tr("Export RAVI Time Series as CSV"),
            default_filename,
            _tr("CSV Files (*.csv);;All Files (*)"),
        )
        if not file_path:
            return

        try:
            export_df = self._filtered_dataframe().sort_values("date")
            smooth_y = self._smoothed_series(export_df["AOI_average"].tolist())
            if smooth_y is not None:
                export_df = export_df.assign(AOI_average_smoothed=smooth_y)
            export_df = self._merge_series_columns(export_df)
            export_df.to_csv(file_path, index=False)
            self.dialog.pop_message(
                _tr("CSV exported successfully to %s") % file_path, "info"
            )
        except Exception as e:
            self.dialog.pop_message(_tr("Failed to export CSV: %s") % str(e), "warning")

    def _merge_series_columns(self, export_df):
        """Append captured point and per-feature series as extra columns (one
        per series), aligned on date, so they ride along in the CSV export."""
        if not self._point_series and not self._feature_series:
            return export_df
        merged = export_df.copy()
        merged["_merge_key"] = merged["date"].astype(str)
        for prefix, series in (
            ("point", self._point_series),
            ("feature", self._feature_series),
        ):
            for label, rows in series.items():
                col = pd.DataFrame(
                    [
                        {
                            "_merge_key": str(r["date"]),
                            f"{prefix}_{label}": r.get("value"),
                        }
                        for r in rows
                    ]
                )
                if col.empty:
                    continue
                col = col.drop_duplicates(subset="_merge_key")
                merged = merged.merge(col, on="_merge_key", how="left")
        return merged.drop(columns="_merge_key")

    def _buffer_meters(self) -> float:
        slider = getattr(self.dialog, "s2_buffer_slider", None)
        if slider is None:
            return 0
        value = slider.value()
        return 0 if -3 <= value <= 3 else value  # match the UI dead-zone

    def handle_batch_download(self):
        """Download the multispectral scene of every filtered date (raw S2
        bands, clipped to the AOI plus the buffer setting)."""
        if not self._has_results():
            return
        if self._batch_worker is not None and self._batch_worker.isRunning():
            return

        dates = self._filtered_dataframe()["date"].dropna().astype(str).tolist()
        if not dates:
            self.dialog.pop_message(_tr("No dates selected to download."), "warning")
            return

        aoi = self.aoi
        buffer_m = self._buffer_meters()
        folder = SettingsManager.load_download_folder()

        self._batch_dialog = QProgressDialog(
            _tr("Preparing batch download..."),
            _tr("Cancel"),
            0,
            len(dates),
            self.dialog,
        )
        self._batch_dialog.setWindowTitle(_tr("Batch Download Progress"))
        self._batch_dialog.setModal(True)
        self._batch_dialog.show()

        def _download_one(date):
            return OpticalService.download_multispectral_for_date(
                aoi, date, buffer_m=buffer_m, output_folder=folder
            )

        self._batch_worker = BatchDownloadWorker(dates, _download_one)
        self._batch_worker.progress.connect(self._on_batch_progress)
        self._batch_worker.finished.connect(self._on_batch_done)
        self._batch_worker.cancelled.connect(self._on_batch_cancelled)
        self._batch_worker.failed.connect(self._on_batch_failed)
        self._batch_dialog.canceled.connect(self._batch_worker.request_cancel)
        self._batch_worker.start()

    def _on_batch_progress(self, current: int, total: int, date_str: str):
        if self._batch_dialog is None:
            return
        self._batch_dialog.setMaximum(total)
        self._batch_dialog.setValue(current)
        self._batch_dialog.setLabelText(
            _tr("Downloading %d of %d: %s") % (current, total, date_str)
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

    # Band positions within the _MULTISPECTRAL_BANDS stack (1-based):
    # B1=1 B2=2 B3=3 B4=4 B5=5 B6=6 B7=7 B8=8 B8A=9 B9=10 B11=11 B12=12.
    _RGB_MODE_BANDS = {
        "RGB: Real Color": (4, 3, 2),  # B4 B3 B2
        "RGB: Red-NIR-Green": (4, 8, 3),  # B4 B8 B3
        "RGB: NIR-Red-Green": (8, 4, 3),  # B8 B4 B3
        "RGB: SWIR2-NIR-Green": (12, 8, 3),  # B12 B8 B3
        "RGB: SWIR1-NIR-SWIR2": (11, 8, 12),  # B11 B8 B12
    }

    def _load_downloaded_images(self, paths: list):
        for path in paths:
            try:
                name = os.path.splitext(os.path.basename(path))[0]
                self._add_rgb_raster(path, name)
            except Exception:
                continue

    def _add_rgb_raster(self, path: str, name: str, bands=(4, 3, 2)):
        """Load a multispectral GeoTIFF as an RGB composite (default true colour
        B4/B3/B2) with a 2–98% cumulative-cut stretch per band."""
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

    # -- single-date image (preview / download) ---------------------------
    def handle_rgb_preview(self):
        self._run_single("rgb", to_folder=False)

    def handle_rgb_download(self):
        self._run_single("rgb", to_folder=True)

    def handle_vi_preview(self):
        self._run_single("index", to_folder=False)

    def handle_vi_download(self):
        self._run_single("index", to_folder=True)

    def _run_single(self, kind: str, to_folder: bool):
        if not self._has_results():
            return
        if self._preview_worker is not None and self._preview_worker.isRunning():
            return

        date = self.dialog.s2_result_date_combo.currentText()
        if not date:
            self.dialog.pop_message(_tr("Select a date first."), "warning")
            return

        index_name = self.dialog.s2_vi_index_combo.currentData() or "NDVI"
        custom_expression = (
            self._resolve_custom_expression(index_name) if kind == "index" else None
        )

        folder = (
            SettingsManager.load_download_folder()
            if to_folder
            else tempfile.gettempdir()
        )

        self._set_single_busy(kind, True)
        self._preview_worker = OpticalPreviewWorker(
            kind,
            self.aoi,
            date,
            index_name,
            self._buffer_meters(),
            folder,
            custom_expression=custom_expression,
        )
        self._preview_worker.finished.connect(
            lambda path, k: self._on_single_done(path, k, to_folder)
        )
        self._preview_worker.failed.connect(self._on_single_failed)
        self._preview_worker.start()

    def _single_buttons(self, kind: str):
        if kind == "index":
            return (self.dialog.s2_btn_vi_preview, self.dialog.s2_btn_vi_download)
        return (self.dialog.s2_btn_rgb_preview, self.dialog.s2_btn_rgb_download)

    def _set_single_busy(self, kind: str, busy: bool):
        btns = self._single_buttons(kind)
        if busy:
            self._preview_btn_texts = tuple(b.text() for b in btns)
            for b in btns:
                b.setText(_tr("Loading..."))
        elif self._preview_btn_texts:
            for b, txt in zip(btns, self._preview_btn_texts):
                b.setText(txt)
        for b in btns:
            b.setEnabled(not busy)

    def _on_single_done(self, path: str, kind: str, to_folder: bool):
        self._set_single_busy(kind, False)
        worker, self._preview_worker = self._preview_worker, None
        if worker is not None:
            worker.deleteLater()

        date = self.dialog.s2_result_date_combo.currentText()
        if kind == "index":
            index_name = self.dialog.s2_vi_index_combo.currentData() or "NDVI"
            ramp = self.dialog.s2_vi_ramp_combo.currentText()
            RasterRendererUtils.load_pseudocolor_raster(
                path, f"S2 {index_name} {date}", 1, ramp
            )
        else:
            mode = self.dialog.s2_rgb_render_combo.currentData()
            bands = self._RGB_MODE_BANDS.get(mode, (4, 3, 2))
            self._add_rgb_raster(path, f"S2 RGB {date}", bands)

        if self.interface is not None:
            action = _tr("downloaded and loaded") if to_folder else _tr("loaded")
            self.interface.messageBar().pushMessage(
                "FARM tools", _tr("RAVI image %s into QGIS.") % action
            )

    def _on_single_failed(self, message: str):
        worker, self._preview_worker = self._preview_worker, None
        if worker is not None:
            worker.deleteLater()
        # Both pairs may show "Loading..."; restore whichever is disabled.
        for kind in ("rgb", "index"):
            self._set_single_busy(kind, False)
        self.dialog.pop_message(message, "warning")

    def handle_smoothing_changed(self, *args):
        """Re-render when smoothing is toggled or its window/poly changes.

        Savitzky-Golay smoothing is a view-only transform of the cached
        series, so it just re-renders the plot — no Earth Engine call, same
        path the threshold and date filters use.
        """
        if self.dataframe is not None and not self.dataframe.empty:
            self._render_timeseries()

    # -- synthetic composite (preview / download) -------------------------
    def handle_composite_preview(self):
        self._run_composite(to_folder=False)

    def handle_composite_download(self):
        self._run_composite(to_folder=True)

    def _run_composite(self, to_folder: bool):
        if not self._has_results():
            return
        if self._composite_worker is not None and self._composite_worker.isRunning():
            return

        # Composite only the dates still shown on the plot (thresholds + the
        # manual date filter), exactly what _filtered_dataframe yields.
        dates = self._filtered_dataframe()["date"].dropna().astype(str).tolist()
        if not dates:
            self.dialog.pop_message(
                _tr("No dates in the current selection to composite."), "warning"
            )
            return

        index_name = self.dialog.s2_composite_index_combo.currentData() or "NDVI"
        custom_expression = self._resolve_custom_expression(index_name)
        # Remember the index the composite was launched with, so naming the
        # loaded layer in the done-callback is independent of later combo edits.
        self._composite_index = index_name

        metric = self.dialog.s2_composite_metric_combo.currentData() or "Mean"
        folder = (
            SettingsManager.load_download_folder()
            if to_folder
            else tempfile.gettempdir()
        )

        self._set_composite_busy(True)
        self._composite_worker = OpticalCompositeWorker(
            self.aoi,
            dates,
            index_name,
            metric,
            self._run_apply_scl,
            self._run_invalid_scl,
            self._buffer_meters(),
            folder,
            custom_expression=custom_expression,
        )
        self._composite_worker.finished.connect(
            lambda path: self._on_composite_done(path, to_folder)
        )
        self._composite_worker.failed.connect(self._on_composite_failed)
        self._composite_worker.start()

    def _composite_buttons(self):
        return (
            self.dialog.s2_btn_composite_preview,
            self.dialog.s2_btn_composite_download,
        )

    def _set_composite_busy(self, busy: bool):
        btns = self._composite_buttons()
        if busy:
            self._composite_btn_texts = tuple(b.text() for b in btns)
            for b in btns:
                b.setText(_tr("Loading..."))
        elif self._composite_btn_texts:
            for b, txt in zip(btns, self._composite_btn_texts):
                b.setText(txt)
        for b in btns:
            b.setEnabled(not busy)

    def _on_composite_done(self, path: str, to_folder: bool):
        self._set_composite_busy(False)
        worker, self._composite_worker = self._composite_worker, None
        if worker is not None:
            worker.deleteLater()

        metric = self.dialog.s2_composite_metric_combo.currentData() or "Mean"
        ramp = self.dialog.s2_composite_ramp_combo.currentText()
        index_name = getattr(self, "_composite_index", None) or self._current_index
        RasterRendererUtils.load_pseudocolor_raster(
            path, f"S2 {index_name} {metric}", 1, ramp
        )

        if self.interface is not None:
            action = _tr("downloaded and loaded") if to_folder else _tr("loaded")
            self.interface.messageBar().pushMessage(
                "FARM tools", _tr("Composite %s into QGIS.") % action
            )

    def _on_composite_failed(self, message: str):
        self._set_composite_busy(False)
        worker, self._composite_worker = self._composite_worker, None
        if worker is not None:
            worker.deleteLater()
        self.dialog.pop_message(message, "warning")

    # -- climate overlay (NASA POWER) -------------------------------------
    def _precip_bars(self):
        """Accumulated monthly precipitation as a bar-overlay payload, or None.

        Returns None unless climate data is loaded.
        """
        if self._climate_df is None or self._climate_df.empty:
            return None
        months, values = NasaPowerService.monthly_precipitation(self._climate_df)
        if not months:
            return None
        # Place each bar at mid-month so it reads against the daily date axis.
        x = [(m + pd.Timedelta(days=14)).strftime("%Y-%m-%d") for m in months]
        return {
            "x": x,
            "y": values,
            "name": _tr("Monthly precipitation"),
            "ylabel": _tr("Accumulated precipitation (mm)"),
        }

    def handle_climate_overlay(self):
        """Fetch NASA POWER climate for the series range and overlay precip."""
        if not self._has_results():
            return
        if self._climate_worker is not None and self._climate_worker.isRunning():
            return
        if not (self._date_start and self._date_end):
            self.dialog.pop_message(_tr("Run the RAVI analysis first."), "warning")
            return

        self._set_climate_busy(True)
        proxy = SettingsManager.get_proxy()
        self._climate_worker = ClimateWorker(
            self.aoi, self._date_start, self._date_end, proxy=proxy
        )
        self._climate_worker.finished.connect(self._on_climate_done)
        self._climate_worker.failed.connect(self._on_climate_failed)
        self._climate_worker.start()

    def _set_climate_busy(self, busy: bool):
        btn = self.dialog.s2_btn_climate_overlay
        if busy:
            self._climate_btn_text = btn.text()
            btn.setText(_tr("Loading..."))
        elif self._climate_btn_text:
            btn.setText(self._climate_btn_text)
        btn.setEnabled(not busy)

    def _on_climate_done(self, df):
        self._set_climate_busy(False)
        worker, self._climate_worker = self._climate_worker, None
        if worker is not None:
            worker.deleteLater()

        if df is None or df.empty:
            self.dialog.pop_message(
                _tr("NASA POWER returned no climate data for this area/range."),
                "warning",
            )
            return
        self._climate_df = df
        self._render_timeseries()
        if self.interface is not None:
            self.interface.messageBar().pushMessage(
                "FARM tools", _tr("Climate overlay added to the time-series plot.")
            )

    def _on_climate_failed(self, message: str):
        self._set_climate_busy(False)
        worker, self._climate_worker = self._climate_worker, None
        if worker is not None:
            worker.deleteLater()
        self.dialog.pop_message(_tr("Climate fetch failed: %s") % message, "warning")

    def handle_climate_clear(self):
        """Drop the climate overlay and re-render the plain time series."""
        if self._climate_df is None:
            return
        self._climate_df = None
        if self.dataframe is not None and not self.dataframe.empty:
            self._render_timeseries()

    def handle_climate_export(self):
        """Export the fetched daily climate table (precip + temperature) as CSV."""
        if self._climate_df is None or self._climate_df.empty:
            self.dialog.pop_message(_tr("Fetch the climate overlay first."), "warning")
            return

        date_str = datetime.now().strftime("%Y%m%d")
        default_filename = f"climate_nasa_power_{date_str}.csv"
        file_path, _ = QFileDialog.getSaveFileName(
            self.dialog,
            _tr("Export Climate Data as CSV"),
            default_filename,
            _tr("CSV Files (*.csv);;All Files (*)"),
        )
        if not file_path:
            return
        try:
            self._climate_df.to_csv(file_path, index=False)
            self.dialog.pop_message(
                _tr("CSV exported successfully to %s") % file_path, "info"
            )
        except Exception as e:
            self.dialog.pop_message(_tr("Failed to export CSV: %s") % str(e), "warning")

    def _smoothed_series(self, y):
        """Savitzky-Golay smoothing of the AOI-average series, or None.

        Recomputed on every render so it tracks whatever the threshold and
        date filters leave behind. ``y`` is assumed already date-sorted; the
        returned list aligns with it. Returns None when smoothing is off or
        the filtered series is too short for a valid window.
        """
        chk = getattr(self.dialog, "s2_chk_smoothing", None)
        if chk is None or not chk.isChecked():
            return None
        n = len(y)
        if n < 3:
            return None
        window = int(self.dialog.s2_smooth_window.value())
        poly = int(self.dialog.s2_smooth_polyorder.value())
        # savgol needs an odd window no longer than the series, and a
        # polyorder strictly below the window. Clamp rather than fail so the
        # overlay still shows when the filtered series is short.
        window = min(window, n)
        if window % 2 == 0:
            window -= 1
        if window < 3:
            return None
        poly = min(poly, window - 1)
        try:
            from scipy.signal import savgol_filter

            smoothed = savgol_filter(y, window_length=window, polyorder=poly)
        except Exception:
            return None
        return [float(v) for v in smoothed]

    def _render_timeseries(self):
        """Plot the AOI-average time series into the optical results web view.

        Only paints when the AOI segment is the active view; while the user is
        on the Points or Features view, AOI-only changes (filter, smoothing,
        climate) update silently and show on the next switch back to AOI.
        """
        if self._active_plot_view != "aoi":
            return
        if self.dataframe is None or self.dataframe.empty:
            return
        index_name = self._current_index
        plot_df = self._filtered_dataframe().rename(columns={"date": "dates"})
        plot_df = plot_df.dropna(subset=["dates", "AOI_average"])
        plot_df = plot_df.sort_values("dates")

        smooth_y = self._smoothed_series(plot_df["AOI_average"].tolist())

        html = render_chart_html(
            plot_df,
            title=_tr("%s Time Series") % index_name,
            ylabel=_tr("%s AOI average") % index_name,
            smooth_y=smooth_y,
            smooth_label=_tr("Smoothed (Savitzky-Golay)"),
            precip_bars=self._precip_bars(),
        )

        fd, path = tempfile.mkstemp(suffix=".html", prefix="farm_tools_optical_")
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(html)
        self.dialog.s2_web_view.load(QUrl.fromLocalFile(path))

        if self._plot_path and os.path.exists(self._plot_path):
            try:
                os.remove(self._plot_path)
            except OSError:
                pass
        self._plot_path = path

    # -- point & per-feature analysis -------------------------------------
    def _populate_feature_id_combo(self, layer=None):
        """Fill the Feature-ID dropdown with the selected layer's attribute
        field names (the key used to label per-feature series)."""
        combo = getattr(self.dialog, "s2_feature_id_combo", None)
        if combo is None:
            return
        if layer is None:
            layer = self.dialog.s2_layer_combo.currentLayer()

        combo.blockSignals(True)
        previous = combo.currentText()
        combo.clear()
        if (
            layer
            and layer.type() == QgsMapLayer.VectorLayer
            and layer.geometryType() == QgsWkbTypes.PolygonGeometry
        ):
            names = [field.name() for field in layer.fields()]
            combo.addItems(names)
            if previous in names:
                combo.setCurrentText(previous)
        combo.blockSignals(False)

    def _analysis_params(self):
        """Shared params for the point/feature worker, or None if no run yet."""
        if not (self._date_start and self._date_end and self._current_index):
            return None
        return {
            "date_start": self._date_start,
            "date_end": self._date_end,
            "index_name": self._current_index,
            "apply_scl": self._run_apply_scl,
            "invalid_scl_values": self._run_invalid_scl,
            "custom_expression": self._resolve_custom_expression(self._current_index),
        }

    # -- points ------------------------------------------------------------
    def handle_toggle_point_capture(self):
        """Toggle the click-to-sample point tool on the canvas."""
        btn = self.dialog.s2_btn_capture_points
        if self.interface is None:
            btn.setChecked(False)
            return

        canvas = self.interface.mapCanvas()
        # Turning the tool off (it is the active map tool).
        if self._point_tool is not None and canvas.mapTool() is self._point_tool:
            canvas.unsetMapTool(self._point_tool)
            return

        if not self._has_results():
            btn.setChecked(False)
            return

        # Reuse the existing tool so its dots and colour order survive a
        # toggle off/on; only build a fresh one the first time.
        if self._point_tool is None:
            self._point_tool = PointCaptureTool(
                canvas, self._on_point_captured, _MULTISERIES_PALETTE
            )
            self._point_tool.on_deactivated = self._on_point_tool_deactivated
        canvas.setMapTool(self._point_tool)
        btn.setChecked(True)
        if self.interface is not None:
            self.interface.messageBar().pushMessage(
                "FARM tools",
                _tr("Click on the map to sample a point time series."),
            )

    def _on_point_tool_deactivated(self):
        self.dialog.s2_btn_capture_points.setChecked(False)

    def _on_point_captured(self, lon, lat, index, color_hex):
        label = _tr("P%d (%.5f, %.5f)") % (index + 1, lat, lon)
        self._point_colors[label] = color_hex
        job = {
            "label": label,
            "geojson": {"type": "Point", "coordinates": [lon, lat]},
            "reducer": "first",
            "color": color_hex,
        }
        self._start_analysis([job], "points")

    def handle_clear_points(self):
        """Remove captured point dots and their series from the plot."""
        self._clear_point_state()
        if self._active_plot_view == "points":
            self._set_plot_view("aoi")
        self._update_view_buttons()

    def _clear_point_state(self):
        if self._point_tool is not None:
            self._point_tool.clear()
        self._point_series = {}
        self._point_colors = {}

    # -- features ----------------------------------------------------------
    def handle_plot_features(self):
        """Extract one index series per polygon feature of the selected layer."""
        if not self._has_results():
            return
        if self._analysis_worker is not None and self._analysis_worker.isRunning():
            return

        layer = self.dialog.s2_layer_combo.currentLayer()
        if (
            not layer
            or layer.type() != QgsMapLayer.VectorLayer
            or layer.geometryType() != QgsWkbTypes.PolygonGeometry
        ):
            self.dialog.pop_message(
                _tr("Select a polygon AOI layer for per-feature analysis."),
                "warning",
            )
            return

        id_field = self.dialog.s2_feature_id_combo.currentText().strip()
        jobs = self._feature_jobs(layer, id_field)
        if not jobs:
            self.dialog.pop_message(
                _tr("The selected layer has no usable features."), "warning"
            )
            return

        # Replace any previous feature run.
        self._feature_series = {}
        self._feature_colors = {}
        self._set_feature_busy(True)
        self._start_analysis(jobs, "features")

    def _feature_jobs(self, layer, id_field):
        """Build one extraction job per feature, labelled by ``id_field``."""
        jobs = []
        taken = set()
        for i, feature in enumerate(layer.getFeatures()):
            geojson = self._layer_feature_geojson(layer, feature)
            if geojson is None:
                continue
            if id_field:
                raw = feature[id_field]
                base = (
                    str(raw)
                    if raw not in (None, "")
                    else _tr("feature %d") % feature.id()
                )
            else:
                base = _tr("feature %d") % feature.id()
            label = base
            n = 2
            while label in taken:
                label = f"{base} ({n})"
                n += 1
            taken.add(label)
            color = _MULTISERIES_PALETTE[i % len(_MULTISERIES_PALETTE)]
            self._feature_colors[label] = color
            jobs.append(
                {
                    "label": label,
                    "geojson": geojson,
                    "reducer": "mean",
                    "color": color,
                }
            )
        return jobs

    def _layer_feature_geojson(self, layer, feature):
        """A feature's geometry as a 2D, EPSG:4326 GeoJSON dict (or None)."""
        geom = QgsGeometry(feature.geometry())
        if geom.isEmpty():
            return None
        if not geom.isGeosValid():
            geom = geom.makeValid()
        if layer.crs().authid() != "EPSG:4326":
            transform = QgsCoordinateTransform(
                layer.crs(),
                QgsCoordinateReferenceSystem("EPSG:4326"),
                QgsProject.instance(),
            )
            geom.transform(transform)
        geojson_str = geom.asJson()
        if not geojson_str:
            return None
        geojson = json.loads(geojson_str)
        geojson["coordinates"] = _remove_z_dimension(geojson["coordinates"])
        return geojson

    def _set_feature_busy(self, busy: bool):
        btn = self.dialog.s2_btn_plot_features
        if busy:
            self._feature_btn_text = self._feature_btn_text or btn.text()
            btn.setText(_tr("Loading..."))
        elif self._feature_btn_text:
            btn.setText(self._feature_btn_text)
        btn.setEnabled(not busy)

    # -- analysis worker plumbing -----------------------------------------
    def _start_analysis(self, jobs, target):
        params = self._analysis_params()
        if params is None:
            self.dialog.pop_message(_tr("Run the RAVI analysis first."), "warning")
            return
        if self._analysis_worker is not None and self._analysis_worker.isRunning():
            # Queue further work of the same kind (rapid point clicks).
            if target == self._analysis_target:
                self._job_queue.extend(jobs)
            return
        self._analysis_target = target
        self._run_analysis_worker(jobs, params)

    def _run_analysis_worker(self, jobs, params):
        self._analysis_worker = OpticalAnalysisWorker(jobs, params)
        self._analysis_worker.series_ready.connect(self._on_series_ready)
        self._analysis_worker.finished.connect(self._on_analysis_finished)
        self._analysis_worker.failed.connect(self._on_analysis_failed)
        self._analysis_worker.start()

    def _on_series_ready(self, label, rows, color):
        if self._analysis_target == "points":
            self._point_series[label] = rows
            if color:
                self._point_colors[label] = color
        else:
            self._feature_series[label] = rows
            if color:
                self._feature_colors[label] = color
        # Points are interactive: reveal each click's line as it lands. Features
        # arrive as one batch, so they render once on finish (avoids redrawing
        # the growing chart per feature).
        if self._analysis_target == "points":
            self._set_plot_view("points")
            self._update_view_buttons()

    def _on_analysis_finished(self):
        if self._job_queue:
            jobs, self._job_queue = self._job_queue, []
            params = self._analysis_params()
            worker, self._analysis_worker = self._analysis_worker, None
            if worker is not None:
                worker.deleteLater()
            if params is not None:
                self._run_analysis_worker(jobs, params)
                return
        worker, self._analysis_worker = self._analysis_worker, None
        if worker is not None:
            worker.deleteLater()
        if self._analysis_target == "features":
            self._set_feature_busy(False)
            if self._feature_series:
                self._set_plot_view("features")
        self._update_view_buttons()

    def _on_analysis_failed(self, message):
        worker, self._analysis_worker = self._analysis_worker, None
        if worker is not None:
            worker.deleteLater()
        self._job_queue = []
        self._set_feature_busy(False)
        self.dialog.pop_message(message, "warning")

    # -- plot view switching ----------------------------------------------
    def handle_plot_view(self, view):
        """Segment-toggle handler (AOI / Points / Features)."""
        if view == "points" and not self._point_series:
            return
        if view == "features" and not self._feature_series:
            return
        self._set_plot_view(view)

    def _set_plot_view(self, view, render=True):
        self._active_plot_view = view
        buttons = (
            ("aoi", self.dialog.s2_plot_view_aoi),
            ("points", self.dialog.s2_plot_view_points),
            ("features", self.dialog.s2_plot_view_features),
        )
        for name, btn in buttons:
            btn.blockSignals(True)
            btn.setChecked(name == view)
            btn.blockSignals(False)
        if not render:
            return
        if view == "points":
            self._render_points()
        elif view == "features":
            self._render_features()
        else:
            self._render_timeseries()

    def _update_view_buttons(self):
        has_aoi = self.dataframe is not None and not self.dataframe.empty
        self.dialog.s2_plot_view_aoi.setEnabled(has_aoi)
        self.dialog.s2_plot_view_points.setEnabled(bool(self._point_series))
        self.dialog.s2_plot_view_features.setEnabled(bool(self._feature_series))
        # The AOI/Points/Features toggle only makes sense once there is point or
        # feature data to switch to; hide the whole bar otherwise.
        self.dialog.s2_plot_view_bar.setVisible(
            bool(self._point_series) or bool(self._feature_series)
        )
        for name, btn in (
            ("aoi", self.dialog.s2_plot_view_aoi),
            ("points", self.dialog.s2_plot_view_points),
            ("features", self.dialog.s2_plot_view_features),
        ):
            btn.blockSignals(True)
            btn.setChecked(name == self._active_plot_view)
            btn.blockSignals(False)

    def _render_points(self):
        self._render_multiseries(
            self._point_series,
            self._point_colors,
            _tr("%s — Points") % self._current_index,
        )

    def _render_features(self):
        self._render_multiseries(
            self._feature_series,
            self._feature_colors,
            _tr("%s — Features") % self._current_index,
        )

    def _render_multiseries(self, series, colors, title):
        """Render a multi-line chart (one line per point/feature) plus the AOI
        average as a grey reference line, into the shared web view."""
        html = self._multiseries_html(series, colors, title)
        if html is None:
            self.dialog.s2_web_view.setHtml("")
            return
        self._load_multiseries(html)

    def _multiseries_html(self, series, colors, title, hide_toolbar=True):
        """Build the multi-line chart HTML (one line per point/feature plus the
        AOI average reference line), or None if there is nothing to plot."""
        aoi_label = _tr("AOI average")
        records = []
        if self.dataframe is not None and not self.dataframe.empty:
            aoi_df = self.dataframe.dropna(subset=["date", "AOI_average"])
            aoi_df = aoi_df.sort_values("date")
            for date, value in zip(aoi_df["date"].astype(str), aoi_df["AOI_average"]):
                records.append(
                    {"dates": date, "AOI_average": float(value), "series": aoi_label}
                )
        for label, rows in series.items():
            for row in rows:
                if row.get("value") is None:
                    continue
                records.append(
                    {
                        "dates": str(row["date"]),
                        "AOI_average": float(row["value"]),
                        "series": label,
                    }
                )

        if not records:
            return None

        plot_df = pd.DataFrame(records)
        color_map = {aoi_label: "#444444"}
        color_map.update(colors)
        return render_multiseries_chart_html(
            plot_df,
            group_col="series",
            title=title,
            ylabel=_tr("%s value") % self._current_index,
            colors=color_map,
            hide_toolbar=hide_toolbar,
        )

    def _load_multiseries(self, html):
        fd, path = tempfile.mkstemp(suffix=".html", prefix="farm_tools_optical_ms_")
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(html)
        self.dialog.s2_web_view.load(QUrl.fromLocalFile(path))
        for old in self._plot_view_paths:
            if os.path.exists(old):
                try:
                    os.remove(old)
                except OSError:
                    pass
        self._plot_view_paths = [path]

    def _on_optical_failed(self, message):
        self._set_run_busy(False)
        self._release_worker()
        self.dialog.s2_web_view.setHtml("")
        self.dialog.s2_set_tab(1)
        self.dialog.pop_message(message, "warning")

    def handle_custom_index_save(self):

        name = self.dialog.s2_custom_name.text()
        expression = self.dialog.s2_custom_expression.text()

        try:
            validate_custom(name, expression)
            save_custom_indexes(name, expression)
            self.update_index_combobox()
            self.dialog.pop_message(_tr("Index sucessfully saved."), "info")
        except Exception as e:
            self.dialog.pop_message(_tr(str(e)), "warning")

    def update_index_combobox(self):
        """Rebuild every index dropdown (inputs time-series, single-date VI and
        composite) so built-in plus saved custom indices stay in sync after a
        save. Only the inputs combo carries the ``Custom…`` builder entry."""
        customs = load_custom_indexes()

        self._fill_index_combo(self.dialog.s2_index_combo, customs, with_builder=True)
        self._fill_index_combo(self.dialog.s2_vi_index_combo, customs)
        self._fill_index_combo(self.dialog.s2_composite_index_combo, customs)

    @staticmethod
    def _fill_index_combo(combo, customs, with_builder=False):
        combo.blockSignals(True)
        previous = combo.currentData()
        combo.clear()
        for name in INDEX_ORDER:
            combo.addItem(name, name)
        for name in customs.keys():
            combo.addItem(name + " - CUSTOM", name)
        if with_builder:
            combo.addItem(_tr(CUSTOM_INDEX_LABEL), CUSTOM_INDEX_LABEL)
        if previous is not None:
            idx = combo.findData(previous)
            if idx >= 0:
                combo.setCurrentIndex(idx)
        combo.blockSignals(False)

    def _resolve_custom_expression(self, index_name):
        """Saved expression for a custom index name, or None for built-ins."""
        return load_custom_indexes().get(index_name)
