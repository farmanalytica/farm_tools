import os
import tempfile
import pandas as pd
from datetime import datetime

from qgis.PyQt.QtCore import Qt, QCoreApplication, QUrl
from qgis.PyQt.QtGui import QDesktopServices
from qgis.PyQt.QtWidgets import QFileDialog, QProgressDialog
from qgis.core import QgsProject, QgsCoordinateTransform

from ..services.aoi_service import AOIService
from ..services.sar_service import SARService
from ..renderers.sar_renderer import SARRenderer
from ..workers.sar_worker import (
    SARWorker,
    SARPreviewWorker,
    SARBatchDownloadWorker,
    SARCompositeWorker,
)
from ..managers.settings_manager import SettingsManager
from ..tools.aoi_draw_tool import start_draw_aoi
from ..view.sar_plot import render_chart_html

try:
    WAIT_CURSOR = Qt.CursorShape.WaitCursor
except AttributeError:
    WAIT_CURSOR = Qt.WaitCursor


def _tr(text):
    return QCoreApplication.translate("RAVI", text)


_LOADING_HTML = """<!DOCTYPE html><html><head><meta charset="utf-8"><style>
html,body{height:100%;margin:0;font-family:Arial,sans-serif;background:#fff}
.box{position:absolute;top:50%;left:50%;transform:translate(-50%,-50%);text-align:center;color:#616161}
.spinner{width:34px;height:34px;margin:0 auto 12px;border:3px solid #e0e0e0;
border-top-color:#1b6b39;border-radius:50%;animation:spin 0.9s linear infinite}
@keyframes spin{to{transform:rotate(360deg)}}
</style></head><body><div class="box"><div class="spinner"></div>
<div>Fetching SAR time series…</div></div></body></html>"""

_CANVAS_SCALE_FACTOR = 1.5


class SARCtrl:
    def __init__(self, dialog, interface=None, gee_service=None):
        self.dialog = dialog
        self.interface = interface
        self.gee_service = gee_service

        self.collection = None
        self.aoi = None
        self.dataframe = None

        self._sar_worker: SARWorker | None = None
        self._preview_worker: SARPreviewWorker | None = None
        self._batch_worker: SARBatchDownloadWorker | None = None
        self._composite_worker: SARCompositeWorker | None = None

        self._active_dates = None
        self._filter_dialog = None
        self._batch_dialog = None
        self._current_index = "VV/VH Ratio"
        self._plot_path: str | None = None
        self._draw_tool = None

        self._run_btn_text: str | None = None
        self._preview_btn_texts: tuple | None = None
        self._composite_btn_texts: tuple | None = None

    def _release_worker(self, attr: str):

        worker = getattr(self, attr, None)
        setattr(self, attr, None)

        if worker is not None:
            worker.deleteLater()

    def _show_auth_required_message(self):
        self.dialog.pop_message(
            _tr(
                "Authentication is required to download SAR data. "
                "Please go to the Auth page and validate your Google Cloud project ID."
            ),
            "warning",
        )

    def _requires_results(self) -> bool:
        """Show a warning and return True when no SAR results are available yet"""

        if self.collection is None or self.aoi is None:
            self.dialog.pop_message(_tr("Run SAR processing first."), "warning")
            return True
        return False

    def _get_active_filtered_dataframe(self):

        if self._active_dates is not None:
            return self.dataframe[self.dataframe["dates"].isin(self._active_dates)]
        return self.dataframe

    def _selected_composite_dates(self) -> list:
        dates = self.dataframe["dates"].tolist()
        if self._active_dates is not None:
            dates = [d for d in dates if d in self._active_dates]
        return dates

    def _index_meta(self) -> dict:
        return SARService.INDEX_REGISTRY[self._current_index]

    def _download_aoi(self):
        """AOI used for download/preview outputs, grown by the buffer slider.

        The buffer expands the requested region (and clip) so every fetched
        image shares the same margin. Returns the unbuffered AOI when the
        slider is at 0 or no AOI is set yet."""
        slider = getattr(self.dialog, "sar_buffer_slider", None)
        meters = slider.value() if slider is not None else 0
        if not meters or self.aoi is None:
            return self.aoi
        return self.aoi.map(lambda feature: feature.buffer(meters).bounds())

    def handle_draw_aoi(self):
        """Toggle rectangular AOI drawing on the canvas."""

        canvas = self.interface.mapCanvas()

        if self._draw_tool is not None and canvas.mapTool() is self._draw_tool:
            canvas.unsetMapTool(self._draw_tool)
            self._draw_tool = None
            return
        self._draw_tool = start_draw_aoi(
            self.interface, self.dialog.sar_layer_combo, self.dialog.sar_btn_draw_aoi
        )

    def handle_layer_changed(self, layer=None):
        """Zoom to the selected AOI layer."""

        if layer is None:
            layer = self.dialog.sar_layer_combo.currentLayer()

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

    def handle_sar_run(self):
        if self._sar_worker is not None and self._sar_worker.isRunning():
            return

        if self.gee_service and not self.gee_service.is_authenticated:
            self._show_auth_required_message()
            return

        layer = self.dialog.sar_layer_combo.currentLayer()
        if not layer:
            self.dialog.pop_message(_tr("Select an AOI layer."), "warning")
            return

        start_qdate = self.dialog.sar_date_start.date()
        end_qdate = self.dialog.sar_date_end.date()
        if start_qdate >= end_qdate:
            self.dialog.pop_message("End date must be after start date.", "warning")
            return

        try:
            aoi, _bbox = AOIService.get_ee_feature_colection_from_layer(
                layer, use_selected_features=False
            )
        except Exception as e:
            self.dialog.pop_message(str(e), "warning")
            return

        self.aoi = aoi
        params = {
            "start_date": start_qdate.toString("yyyy-MM-dd"),
            "end_date": end_qdate.toString("yyyy-MM-dd"),
            "polarization": self.dialog.sar_pol_combo.currentText(),
            "output_format": self.dialog.sar_format_combo.currentText(),
            "border_noise": self.dialog.sar_chk_border_noise.isChecked(),
            "terrain": self.dialog.sar_chk_terrain.isChecked(),
            "speckle": self.dialog.sar_chk_speckle.isChecked(),
            "index": self.dialog.sar_index_combo.currentText(),
        }

        self._set_run_busy(True)
        self.dialog.sar_web_view.setHtml(_LOADING_HTML)
        self.dialog.sar_set_tab(2)

        self._sar_worker = SARWorker(aoi, params)
        self._sar_worker.finished.connect(self._on_sar_done)
        self._sar_worker.failed.connect(self._on_sar_failed)
        self._sar_worker.start()

    def _set_run_busy(self, busy: bool):
        btn = self.dialog.sar_btn_next
        if busy:
            self._run_btn_text = self._run_btn_text or btn.text()
            btn.setText(_tr("Running…"))
        else:
            btn.setText(self._run_btn_text or btn.text())
        btn.setEnabled(not busy)

    def _on_sar_done(self, collection, data, index):
        self._set_run_busy(False)
        self._release_worker("_sar_worker")

        if not data:
            self.dialog.sar_web_view.setHtml("")
            self.dialog.sar_set_tab(1)
            self.dialog.pop_message(
                "No SAR images found for this date range.", "warning"
            )
            return

        self.collection = collection
        self.dataframe = pd.DataFrame(data)
        self._active_dates = None
        self._current_index = index

        self.dialog.sar_result_date_combo.clear()
        self.dialog.sar_result_date_combo.addItems(self.dataframe["dates"].tolist())
        self._render_timeseries()
        self.dialog.sar_set_tab(2)

    def _on_sar_failed(self, message):
        self._set_run_busy(False)
        self._release_worker("_sar_worker")
        self.dialog.sar_web_view.setHtml("")
        self.dialog.sar_set_tab(1)
        self.dialog.pop_message(message, "warning")

    def handle_preview_image(self):
        self._run_preview(to_folder=False)

    def handle_download_preview(self):
        self._run_preview(to_folder=True)

    def _run_preview(self, to_folder: bool):

        if self._preview_worker is not None and self._preview_worker.isRunning():
            return

        if self._requires_results():
            return

        selected_date = self.dialog.sar_result_date_combo.currentText()
        meta = self._index_meta()
        output_folder = (
            SettingsManager.load_download_folder()
            if to_folder
            else tempfile.gettempdir()
        )
        label = f"SAR_{selected_date}" if to_folder else f"SAR_Preview_{selected_date}"

        self._set_preview_busy(True)
        self._preview_worker = SARPreviewWorker(
            self.collection,
            self._download_aoi(),
            selected_date,
            output_folder,
            label,
            index_band=meta["band"],
            index_label=meta["band_label"],
        )
        self._preview_worker.finished.connect(
            lambda path, label: self._on_preview_done(path, label, to_folder)
        )
        self._preview_worker.failed.connect(self._on_preview_failed)
        self._preview_worker.start()

    def _set_preview_busy(self, busy: bool):
        btns = (self.dialog.sar_btn_preview, self.dialog.sar_btn_download_preview)

        if busy:
            self._preview_btn_texts = tuple(b.text() for b in btns)
            for b in btns:
                b.setText(_tr("Loading..."))
        elif self._preview_btn_texts:
            for b, txt in zip(btns, self._preview_btn_texts):
                b.setText(txt)
        for b in btns:
            b.setEnabled(not busy)

    def _on_preview_done(self, output_path: str, label: str, to_folder: bool):
        self._set_preview_busy(False)
        self._release_worker("_preview_worker")
        SARRenderer.load_sar_to_qgis(
            output_path,
            label,
            render_mode=self._render_mode(),
            color_ramp_name=self.dialog.sar_render_ramp_combo.currentText(),
        )

        if self.interface:
            filename = os.path.basename(output_path)
            action_msg = _tr("downloaded and loaded") if to_folder else _tr("loaded")
            self.interface.messageBar().pushMessage(
                "FARM tools", _tr("SAR image '%s' %s into QGIS.") % (filename, action_msg)
            )

    def _on_preview_failed(self, message: str):
        self._set_preview_busy(False)
        self._release_worker("_preview_worker")
        self.dialog.pop_message(message, "warning")


    def handle_composite_preview(self):
        self._run_composite(to_folder=False)

    def handle_composite_download(self):
        self._run_composite(to_folder=True)

    def _run_composite(self, to_folder):
        if self._composite_worker is not None and self._composite_worker.isRunning():
            return

        if self._requires_results():
            return

        dates = self._selected_composite_dates()
        if not dates:
            self.dialog.pop_message(
                _tr("No dates selected for the composite."), "warning"
            )
            return

        meta = self._index_meta()
        output_folder = (
            SettingsManager.load_download_folder()
            if to_folder
            else tempfile.gettempdir()
        )

        self._set_composite_busy(True)
        self._composite_worker = SARCompositeWorker(
            self.collection,
            self._download_aoi(),
            meta["band"],
            meta["band_label"],
            self.dialog.sar_composite_metric_combo.currentData(),
            dates,
            min(dates),
            output_folder,
            f"{meta['band_label']} {self.dialog.sar_composite_metric_combo.currentText()}",
        )
        self._composite_worker.finished.connect(
            lambda path, label: self._on_composite_done(path, label, to_folder)
        )
        self._composite_worker.failed.connect(self._on_composite_failed)
        self._composite_worker.start()

    def _set_composite_busy(self, busy: bool):
        btns = (
            self.dialog.sar_btn_composite_preview,
            self.dialog.sar_btn_composite_download,
        )

        if busy:
            self._composite_btn_texts = tuple(b.text() for b in btns)
            for b in btns:
                b.setText(_tr("Working..."))
        elif self._composite_btn_texts:
            for b, txt in zip(btns, self._composite_btn_texts):
                b.setText(txt)
        for b in btns:
            b.setEnabled(not busy)

    def _on_composite_done(self, output_path: str, label: str, to_folder: bool):
        self._set_composite_busy(False)
        self._release_worker("_composite_worker")
        ramp = self.dialog.sar_composite_ramp_combo.currentText()
        SARRenderer.load_composite_to_qgis(output_path, label, color_ramp_name=ramp)
        if self.interface:
            filename = os.path.basename(output_path)
            action_msg = _tr("downloaded and loaded") if to_folder else _tr("loaded")
            self.interface.messageBar().pushMessage(
                "FARM tools",
                _tr("Composite '%s' %s into QGIS.") % (filename, action_msg),
            )

    def _on_composite_failed(self, message):
        self._set_composite_busy(False)
        self._release_worker("_composite_worker")
        self.dialog.pop_message(message, "warning")

    def handle_batch_download(self):
        if self._requires_results():
            return

        dates = self._get_active_filtered_dataframe()["dates"].tolist()
        if not dates:
            self.dialog.pop_message(_tr("No dates selected to download."), "warning")
            return

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

        meta = self._index_meta()
        self._batch_worker = SARBatchDownloadWorker(
            self.collection,
            self._download_aoi(),
            dates,
            SettingsManager.load_download_folder(),
            index_band=meta["band"],
            index_label=meta["band_label"],
        )
        self._batch_worker.progress.connect(self._on_batch_progress)
        self._batch_worker.finished.connect(self._on_batch_done)
        self._batch_worker.failed.connect(self._on_batch_failed)
        self._batch_worker.cancelled.connect(self._on_batch_cancelled)
        self._batch_dialog.canceled.connect(self._batch_worker.request_cancel)
        self._batch_worker.start()

    def _on_batch_progress(self, current: int, total: int, date_str: str):
        self._batch_dialog.setMaximum(total)
        self._batch_dialog.setValue(current)
        self._batch_dialog.setLabelText(
            _tr("Downloading %d of %d: %s") % (current, total, date_str)
        )

    def _on_batch_done(self, successful: int, total: int, downloaded_paths: list):
        self._batch_dialog.close()
        self._load_downloaded_images(downloaded_paths)

        failed = total - successful
        msg = _tr("Batch download complete: %d/%d successful") % (successful, total)
        if failed > 0:
            msg += _tr(" (%d failed)") % failed
        self.dialog.pop_message(msg, "warning" if failed > 0 else "info")

    def _on_batch_failed(self, message):
        if self._batch_dialog:
            self._batch_dialog.close()
        self.dialog.pop_message(_tr("Batch download failed: %s") % message, "warning")

    def _on_batch_cancelled(self, successful: int, total: int, downloaded_paths: list):
        self._batch_dialog.close()
        self._load_downloaded_images(downloaded_paths)

        if successful > 0:
            msg = _tr(
                f"Batch download cancelled. {successful}/{total} images downloaded and loaded."
            )
            self.dialog.pop_message(msg, "info")
        else:
            self.dialog.pop_message(_tr("Batch download cancelled by user."), "info")

    def _render_mode(self) -> str:
        data = self.dialog.sar_render_combo.currentData()
        return data or self.dialog.sar_render_combo.currentText()

    def _load_downloaded_images(self, paths: list):
        render_mode = self._render_mode()
        color_ramp_name = self.dialog.sar_render_ramp_combo.currentText()
        for path in paths:
            try:
                date_str = (
                    os.path.basename(path)
                    .replace("Sentinel1_", "")
                    .replace(".tiff", "")
                )
                label = f"SAR_{date_str}"
                SARRenderer.load_sar_to_qgis(
                    path,
                    label,
                    render_mode=render_mode,
                    color_ramp_name=color_ramp_name,
                )
            except Exception:
                continue

    def handle_filter_dates(self):
        if self.dataframe is None:
            self.dialog.pop_message(_tr("Run SAR processing first."), "warning")
            return

        if self._filter_dialog is not None:
            self._filter_dialog.raise_()
            self._filter_dialog.activateWindow()
            return

        from ..view.sar_date_filter_dialog import SARDateFilterDialog

        dates = self.dataframe["dates"].tolist()
        self._filter_dialog = SARDateFilterDialog(
            dates, self._active_dates, parent=self.dialog
        )
        self._filter_dialog.filter_changed.connect(self._on_filter_changed)
        self._filter_dialog.finished.connect(self._on_filter_dialog_closed)
        self._filter_dialog.show()

    def _on_filter_changed(self, selected_dates):
        all_dates = self.dataframe["dates"].tolist()
        self._active_dates = (
            None if set(selected_dates) == set(all_dates) else selected_dates
        )
        self._render_timeseries()

    def _on_filter_dialog_closed(self):
        self._filter_dialog = None

    def handle_open_browser(self):
        if self.dataframe is None:
            self.dialog.pop_message(_tr("Run SAR processing first."), "warning")
            return

        meta = self._index_meta()
        html = render_chart_html(
            self._get_active_filtered_dataframe(),
            hide_toolbar=False,
            title=meta["title"],
            ylabel=meta["ylabel"],
        )
        with tempfile.NamedTemporaryFile(
            suffix=".html", delete=False, mode="w", encoding="utf-8"
        ) as f:
            f.write(html)
            path = f.name
        QDesktopServices.openUrl(QUrl.fromLocalFile(path))

    def handle_export_csv(self):
        if self.dataframe is None:
            self.dialog.pop_message(_tr("Run SAR processing first."), "warning")
            return

        date_str = datetime.now().strftime("%Y%m%d")
        default_filename = f"SAR_timeseries_{date_str}.csv"

        file_path, _ = QFileDialog.getSaveFileName(
            self.dialog,
            _tr("Export SAR Time Series as CSV"),
            default_filename,
            _tr("CSV Files (*.csv);;All Files (*)"),
        )

        if not file_path:
            return

        try:
            self._get_active_filtered_dataframe().to_csv(file_path, index=False)
            self.dialog.pop_message(
                _tr("CSV exported successfully to %s") % file_path, "info"
            )
        except Exception as e:
            self.dialog.pop_message(_tr("Failed to export CSV: %s") % str(e), "warning")

    def _render_timeseries(self):
        meta = self._index_meta()
        html = render_chart_html(
            self._get_active_filtered_dataframe(),
            title=meta["title"],
            ylabel=meta["ylabel"],
        )

        fd, path = tempfile.mkstemp(suffix=".html", prefix="farm_tools_sar_")
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(html)
        self.dialog.sar_web_view.load(QUrl.fromLocalFile(path))

        if self._plot_path and os.path.exists(self._plot_path):
            try:
                os.remove(self._plot_path)
            except OSError:
                pass
        self._plot_path = path
