# -*- coding: utf-8 -*-
"""
ClimaPlots controller for the FARM tools QGIS plugin.

Owns all UI interplay for the ClimaPlots page (pick-point toggling, worker
orchestration, plot rendering, exports) and delegates the pure fetch/compute/
figure logic to ``services/climaplots/``. Heavy extlibs imports (climdex,
pymannkendall, pyhomogeneity) stay lazy so the plugin loads before the extlibs
bundle is provisioned.
"""

import os
import traceback

from qgis.core import Qgis, QgsMessageLog
from qgis.PyQt.QtCore import QCoreApplication, QStandardPaths, Qt
from qgis.PyQt.QtWidgets import QApplication, QFileDialog, QMessageBox

from ..managers.settings_manager import SettingsManager
from ..services.climaplots import nasa_power_service, openmeteo_service
from ..tools.canvas_click_tool import CanvasClickTool
from ..view import plotly_render
from ..view.climaplots import (
    PICK_B_OFF,
    PICK_B_ON,
    PICK_TEXT_OFF,
    PICK_TEXT_ON,
    index_description,
    variable_description,
)
from ..view.styles import STYLE_BTN_DRAW_ACTIVE, STYLE_BTN_SECONDARY
from ..workers.climaplots_worker import ClimaPlotsAnalysisWorker


def _tr(text):
    return QCoreApplication.translate("RAVI", text)


# Plotly chart config (toolbar trimmed) shared by all three views.
_PLOT_CONFIG = {
    "displaylogo": False,
    "responsive": True,
    "modeBarButtonsToRemove": [
        "toImage", "sendDataToCloud", "zoom2d", "pan2d", "select2d",
        "lasso2d", "zoomIn2d", "zoomOut2d", "autoScale2d", "resetScale2d",
        "hoverClosestCartesian", "hoverCompareCartesian", "zoom3d", "pan3d",
        "orbitRotation", "tableRotation", "resetCameraLastSave",
        "resetCameraDefault3d", "hoverClosest3d", "zoomInGeo", "zoomOutGeo",
        "resetGeo", "hoverClosestGeo", "hoverClosestGl2d", "hoverClosestPie",
        "toggleHover", "toggleSpikelines", "resetViews",
    ],
}

_SOURCE_MIN_YEAR = {
    "power": nasa_power_service.MIN_YEAR,
    "openmeteo": openmeteo_service.MIN_YEAR,
}


def _loading_html():
    return (
        "<html><body style='font-family:sans-serif;color:#555;text-align:center;"
        "margin-top:40px'><h3>" + _tr("Fetching climate data...") + "</h3></body></html>"
    )


class ClimaPlotsCtrl:
    """Orchestrates ClimaPlots actions between the dialog, canvas, and services."""

    def __init__(self, dialog, interface):
        self.dialog = dialog
        self.interface = interface
        self.click_tool = CanvasClickTool(interface)
        self.click_tool.on_deactivated = self._on_capture_deactivated
        self.click_tool.point_picked.connect(self._on_point_picked)

        # State
        self.climate_data = None              # services.climaplots.types.ClimateData
        self._worker = None                   # ClimaPlotsAnalysisWorker
        self._figs = {1: None, 2: None, 3: None}       # for "open in browser"
        self._save_data = {1: None, 2: None, 3: None}  # DataFrames for CSV export
        self._tmp_paths = {1: None, 2: None, 3: None}  # temp html per web view
        self._coords_visited = False          # auto-enable pick on first visit
        self._switching_pick = False          # guards A<->B mutual exclusion

        self.dialog.stack.currentChanged.connect(self._on_page_changed)
        self.dialog.cp_stack.currentChanged.connect(self._on_tab_changed)
        self.dialog.finished.connect(self._on_dialog_finished)
        self.handle_sync_year_range()

    # ------------------------------------------------------------------
    # Pick-point capture
    # ------------------------------------------------------------------

    def handle_pick_a_toggled(self, enabled):
        """Enter/leave map-click capture mode for point A."""
        btn = self.dialog.cp_btn_pick_a
        btn.setText(_tr(PICK_TEXT_ON) if enabled else _tr(PICK_TEXT_OFF))
        btn.setStyleSheet(STYLE_BTN_DRAW_ACTIVE if enabled else STYLE_BTN_SECONDARY)
        if enabled:
            self._switching_pick = True
            if self.dialog.cp_btn_pick_b.isChecked():
                self.dialog.cp_btn_pick_b.setChecked(False)
            self._switching_pick = False
            self.click_tool.enable("A")
        elif not self._switching_pick:
            self.click_tool.disable()

    def handle_pick_b_toggled(self, enabled):
        """Enter/leave map-click capture mode for the comparison point B."""
        btn = self.dialog.cp_btn_pick_b
        btn.setText(_tr(PICK_B_ON) if enabled else _tr(PICK_B_OFF))
        btn.setStyleSheet(STYLE_BTN_DRAW_ACTIVE if enabled else STYLE_BTN_SECONDARY)
        if enabled:
            self._switching_pick = True
            if self.dialog.cp_btn_pick_a.isChecked():
                self.dialog.cp_btn_pick_a.setChecked(False)
            self._switching_pick = False
            self.click_tool.enable("B")
        elif not self._switching_pick:
            self.click_tool.disable()

    def _on_point_picked(self, longitude, latitude, slot="A"):
        """A point was clicked: fill the matching fields; capture mode stays on."""
        if slot == "B":
            self.dialog.cp_lon_b.setText(str(longitude))
            self.dialog.cp_lat_b.setText(str(latitude))
        else:
            self.dialog.cp_lon_a.setText(str(longitude))
            self.dialog.cp_lat_a.setText(str(latitude))

    def _on_capture_deactivated(self):
        """Another tool displaced the capture tool — sync the toggle buttons."""
        if self._switching_pick:
            return
        for btn in (self.dialog.cp_btn_pick_a, self.dialog.cp_btn_pick_b):
            if btn.isChecked():
                btn.setChecked(False)  # triggers the toggle handler (disable no-ops)

    def _release_pick(self):
        """Uncheck both pick buttons and release the capture tool."""
        for btn in (self.dialog.cp_btn_pick_a, self.dialog.cp_btn_pick_b):
            if btn.isChecked():
                btn.setChecked(False)
        self.click_tool.disable()

    def _on_page_changed(self, index):
        """Release the capture tool when the user leaves the ClimaPlots page."""
        if self.dialog.stack.widget(index) is self.dialog.climaplots_page:
            return
        self._release_pick()

    def _on_tab_changed(self, index):
        """Auto-enable pick A the first time the Coordinates tab is shown."""
        if index == 1 and not self._coords_visited:
            self._coords_visited = True
            self.dialog.cp_btn_pick_a.setChecked(True)  # triggers handle_pick_a_toggled

    def _on_dialog_finished(self, _result):
        """Release the capture tool when the dialog closes."""
        self._release_pick()

    def handle_clear_marker(self):
        self.click_tool.clear_marker()

    def cleanup(self):
        """Release the tool, remove markers, temp files, and any running worker."""
        self._release_pick()
        self.click_tool.clear_marker()
        for tab in (1, 2, 3):
            path = self._tmp_paths.get(tab)
            if path and os.path.exists(path):
                try:
                    os.remove(path)
                except OSError:
                    pass
            self._tmp_paths[tab] = None
        if self._worker is not None:
            try:
                self._worker.finished_ok.disconnect()
                self._worker.failed.disconnect()
                self._worker.progress.disconnect()
            except Exception:
                pass
            if self._worker.isRunning():
                self._worker.wait(100)
            self._worker.deleteLater()
            self._worker = None

    # ------------------------------------------------------------------
    # Coordinates helpers
    # ------------------------------------------------------------------

    def handle_copy_a_to_b(self):
        """Replicate point A's coordinates into the comparison point B fields."""
        self.dialog.cp_lon_b.setText(self.dialog.cp_lon_a.text().strip())
        self.dialog.cp_lat_b.setText(self.dialog.cp_lat_a.text().strip())

    def handle_sync_year_range(self):
        """Lower the year spinboxes' minimum to match the active data sources.

        One year range feeds both fetches, so the floor is the most restrictive
        of the sources in use (A always; B only when it has its own source).
        Open-Meteo (ERA5) reaches back to 1940; NASA POWER only to 1981.
        """
        source_a = self.dialog.cp_source_combo_a.currentData() or "power"
        mins = [_SOURCE_MIN_YEAR.get(source_a, nasa_power_service.MIN_YEAR)]
        source_b = self.dialog.cp_source_combo_b.currentData()
        if source_b is not None:
            mins.append(_SOURCE_MIN_YEAR.get(source_b, nasa_power_service.MIN_YEAR))
        floor = max(mins)
        for spin in (self.dialog.cp_start_year, self.dialog.cp_end_year):
            spin.setMinimum(floor)

    def handle_update_var_desc(self):
        self.dialog.cp_var_desc.setText(
            _tr(variable_description(self.dialog.cp_var_combo.currentText()))
        )

    def handle_update_index_desc(self):
        self.dialog.cp_index_desc.setText(
            _tr(index_description(self.dialog.cp_index_combo.currentText()))
        )

    # ------------------------------------------------------------------
    # Data flow
    # ------------------------------------------------------------------

    def _deps_ready(self):
        """True when the extlibs packages the analysis needs are importable."""
        try:
            import climdex  # noqa: F401
            import pymannkendall  # noqa: F401
            import pyhomogeneity  # noqa: F401
        except ImportError:
            return False
        return True

    def handle_run(self):
        """Start the background analysis for the entered coordinates."""
        if self._worker is not None and self._worker.isRunning():
            return  # re-entrancy guard

        if not self.dialog.cp_lon_a.text().strip() or not self.dialog.cp_lat_a.text().strip():
            self.dialog.pop_message(
                _tr("Click a point on the map (or enter Longitude/Latitude) first."),
                "warning",
            )
            return

        if not self._deps_ready():
            self.dialog.pop_message(
                _tr(
                    "ClimaPlots dependencies are still being provisioned. "
                    "Restart QGIS to finish the download, or install the "
                    "packages from requirements.txt manually."
                ),
                "warning",
            )
            return

        self._reset_results()
        QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
        for view in (
            self.dialog.cp_web_trends,
            self.dialog.cp_web_thermo,
            self.dialog.cp_web_indices,
        ):
            try:
                view.setHtml(_loading_html())
            except Exception:
                pass

        self._worker = ClimaPlotsAnalysisWorker(
            self.dialog.cp_lon_a.text(),
            self.dialog.cp_lat_a.text(),
            SettingsManager.get_proxy(),
            start_year=self.dialog.cp_start_year.value(),
            end_year=self.dialog.cp_end_year.value(),
            longitude_b=self.dialog.cp_lon_b.text().strip() or None,
            latitude_b=self.dialog.cp_lat_b.text().strip() or None,
            source=self.dialog.cp_source_combo_a.currentData() or "power",
            source_b=self.dialog.cp_source_combo_b.currentData(),
            parent=self.dialog,
        )
        self._worker.finished_ok.connect(self._on_analysis_done)
        self._worker.failed.connect(self._on_analysis_failed)
        self._worker.progress.connect(self._on_progress)
        self._worker.finished.connect(self._cleanup_worker)
        self._worker.start()

    def _on_progress(self, message):
        QgsMessageLog.logMessage(message, "FARM tools", Qgis.Info)

    def _on_analysis_done(self, data):
        """Render all three plots from the worker result (GUI thread)."""
        QApplication.restoreOverrideCursor()
        self.climate_data = data
        self.plots1()
        self.plots2()
        self.plots3()
        self.dialog.cp_set_tab(2)  # auto-switch to Trends

    def _on_analysis_failed(self, message):
        QApplication.restoreOverrideCursor()
        QgsMessageLog.logMessage(message, "FARM tools", Qgis.Critical)
        self.dialog.pop_message(
            _tr("Failed to fetch or process climate data.\nSee the QGIS log for details."),
            "warning",
        )
        for tab in (1, 2, 3):
            self._tmp_paths_clear(tab)

    def _cleanup_worker(self):
        if self._worker is not None:
            self._worker.deleteLater()
            self._worker = None

    def _reset_results(self):
        self.climate_data = None
        for tab in (1, 2, 3):
            self._figs[tab] = None
            self._save_data[tab] = None
            self._tmp_paths_clear(tab)
        # The map markers are intentionally kept across runs (use "Clear marker").

    # ------------------------------------------------------------------
    # Plot rendering
    # ------------------------------------------------------------------

    def plots1(self):
        from ..services.climaplots import plot_service  # lazy: pulls stats deps

        self._render(
            1, self.dialog.cp_web_trends,
            lambda d: plot_service.annual_trends(
                d.df, self.dialog.cp_var_combo.currentText(), d.longitude, d.latitude,
                df_b=d.df_b, longitude_b=d.longitude_b, latitude_b=d.latitude_b,
                source=d.source, source_b=d.source_b))

    def plots2(self):
        from ..services.climaplots import plot_service

        self._render(
            2, self.dialog.cp_web_thermo,
            lambda d: plot_service.thermopluviometric(d.df, d.longitude, d.latitude))

    def plots3(self):
        from ..services.climaplots import plot_service

        self._render(
            3, self.dialog.cp_web_indices,
            lambda d: plot_service.index_plot(
                d.indices, self.dialog.cp_index_combo.currentText(),
                d.longitude, d.latitude))

    def _render(self, tab, web_view, builder):
        """Build a figure with ``builder(climate_data)`` and show it in ``web_view``."""
        from ..services.climaplots import plot_service

        if self.climate_data is None:
            return
        try:
            result = builder(self.climate_data)
        except plot_service.PlotDataError as e:
            QMessageBox.warning(self.dialog, _tr("Data not available"), str(e))
            return
        except Exception as e:  # noqa: BLE001
            QgsMessageLog.logMessage(
                f"ClimaPlots plot {tab} failed: {e}", "FARM tools", Qgis.Warning
            )
            return
        self._figs[tab] = result.figure
        self._save_data[tab] = result.data
        self._tmp_paths[tab] = plotly_render.show_in_webview(
            web_view, result.figure, _PLOT_CONFIG, self._tmp_paths.get(tab)
        )

    def handle_open_in_browser(self, tab):
        fig = self._figs.get(tab)
        if fig is not None:
            plotly_render.open_in_browser(fig, dict(_PLOT_CONFIG, modeBarButtonsToRemove=[]))

    def _web_view(self, tab):
        return {
            1: self.dialog.cp_web_trends,
            2: self.dialog.cp_web_thermo,
            3: self.dialog.cp_web_indices,
        }[tab]

    def _tmp_paths_clear(self, tab):
        self._tmp_paths[tab] = plotly_render.clear_webview(
            self._web_view(tab), self._tmp_paths.get(tab)
        )

    # ------------------------------------------------------------------
    # Exports
    # ------------------------------------------------------------------

    def handle_save_png(self, tab):
        """Grab the rendered chart from its web view and save as PNG."""
        if self._figs.get(tab) is None:
            return
        name = {1: "annual_trends", 2: "thermo_pluviometric", 3: "climate_index"}[tab]
        path, _ = QFileDialog.getSaveFileName(
            self.dialog, _tr("Save image"),
            self._default_output_path(name + ".png"), "PNG (*.png)")
        if path:
            self._web_view(tab).grab().save(path)
            self._push_message(_tr("Image saved: {0}").format(path), Qgis.Success, 4)

    def handle_save_csv_trends(self):
        self._save_csv(
            self._save_data[1],
            "Annual_trends_{0}.csv".format(self.dialog.cp_var_combo.currentText()),
        )

    def handle_save_csv_thermo(self):
        self._save_csv(self._save_data[2], "Thermopluviometric.csv")

    def handle_save_csv_indices(self):
        self._save_csv(
            self._save_data[3],
            "{0}.csv".format(self.dialog.cp_index_combo.currentText()),
        )

    def handle_save_csv_raw(self):
        df = self.climate_data.df if self.climate_data else None
        self._save_csv(df, "Raw_data.csv")

    def _save_csv(self, df, default_name):
        """Common CSV export: file dialog + write + messageBar feedback."""
        if df is None:
            self._push_message(
                _tr("Nothing to save yet. Run an analysis first."), Qgis.Warning, 4
            )
            return
        path, _ = QFileDialog.getSaveFileName(
            self.dialog, _tr("Save CSV"),
            self._default_output_path(default_name), "CSV Files (*.csv)")
        if not path:
            return
        try:
            import pandas as pd

            df.to_csv(path, index=not isinstance(df.index, pd.RangeIndex))
        except Exception:
            QgsMessageLog.logMessage(
                traceback.format_exc(), "FARM tools", Qgis.Critical
            )
            self._push_message(_tr("Error exporting CSV."), Qgis.Critical, 6)
            return
        self._push_message(_tr("CSV exported successfully: {0}").format(path), Qgis.Success, 5)

    def handle_export_all(self):
        """Export raw data, annual/thermo tables and all indices to one file."""
        if self.climate_data is None:
            self.dialog.pop_message(_tr("Run an analysis first."), "warning")
            return
        path, _ = QFileDialog.getSaveFileName(
            self.dialog, _tr("Export all"),
            self._default_output_path("climaplots.xlsx"), "Excel (*.xlsx)")
        if not path:
            return
        try:
            from ..services.climaplots import export_service  # lazy

            out = export_service.export(path, self.climate_data, self._save_data)
            self._push_message(_tr("Saved: {0}").format(out), Qgis.Success, 5)
        except Exception as e:  # noqa: BLE001
            QgsMessageLog.logMessage(
                traceback.format_exc(), "FARM tools", Qgis.Critical
            )
            self.dialog.pop_message(_tr("Export failed.") + "\n" + str(e), "warning")

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _push_message(self, message, level, duration):
        """Show non-blocking feedback in the QGIS message bar."""
        self.interface.messageBar().pushMessage(
            "FARM tools", message, level=level, duration=duration
        )

    def _default_output_path(self, filename):
        """Return a sensible default save path (Downloads, then Documents)."""
        download_dir = QStandardPaths.writableLocation(
            QStandardPaths.StandardLocation.DownloadLocation
        )
        if not download_dir:
            download_dir = QStandardPaths.writableLocation(
                QStandardPaths.StandardLocation.DocumentsLocation
            )
        if not download_dir:
            return filename
        return os.path.join(download_dir, filename)
