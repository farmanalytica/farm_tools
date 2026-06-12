# -*- coding: utf-8 -*-
"""
Field Guide controller for the FARM tools QGIS plugin.

Owns all UI interplay for the Field Guide page (capture toggling, session
state sync, file dialogs, prompts) and delegates the pure sampling/export
logic to ``services/fieldguide_service.py``.
"""

import csv
import os
import traceback
from datetime import datetime, timezone

from qgis.core import Qgis, QgsMessageLog
from qgis.PyQt.QtCore import QCoreApplication, QStandardPaths, QUrl, Qt
from qgis.PyQt.QtGui import QDesktopServices
from qgis.PyQt.QtWidgets import QApplication, QFileDialog, QMessageBox

from ..services import raster_analysis
from ..services.fieldguide_service import FieldGuideService, parse_decimal
from ..services.fieldguide_pdf import PdfReportComposer
from ..services.fieldguide_pdf.links import build_google_maps_directions_url
from ..tools.canvas_marker_tool import CanvasMarkerTool
from ..view.styles import STYLE_BTN_DRAW_ACTIVE, STYLE_BTN_SECONDARY


def _tr(text):
    return QCoreApplication.translate("RAVI", text)


class FieldGuideCtrl:
    """Orchestrates Field Guide actions between the dialog, canvas, and service."""

    def __init__(self, dialog, interface):
        self.dialog = dialog
        self.interface = interface
        self.service = FieldGuideService()
        self.marker_tool = CanvasMarkerTool(interface)
        self.marker_tool.on_deactivated = self._on_capture_deactivated
        self.pdf_composer = PdfReportComposer(interface)
        # Metadata about the last raster-based optimal point selection run,
        # consumed by the CSV/GPX/PDF exports; None while in manual mode.
        self._raster_session = None

        self.marker_tool.coordinates_changed.connect(self.update_points)
        self.dialog.stack.currentChanged.connect(self._on_page_changed)
        self.dialog.finished.connect(self._on_dialog_finished)
        self.update_points([])

    # ------------------------------------------------------------------
    # Capture mode
    # ------------------------------------------------------------------

    def handle_capture_toggled(self, checked):
        """Enable or disable interactive point capture from the toggle button."""
        if checked:
            self.marker_tool.enable()
        else:
            self.marker_tool.disable()
        self._set_capture_ui(checked)

    def _set_capture_ui(self, active):
        """Sync the capture button and status label without re-triggering signals."""
        btn = self.dialog.fg_btn_capture
        btn.blockSignals(True)
        btn.setChecked(active)
        btn.blockSignals(False)
        btn.setStyleSheet(STYLE_BTN_DRAW_ACTIVE if active else STYLE_BTN_SECONDARY)
        self.dialog.fg_capture_status_lbl.setText(
            _tr("Capture ON") if active else _tr("Capture OFF")
        )

    def _on_capture_deactivated(self):
        """Another tool displaced the capture tool — sync the toggle button."""
        if self.dialog.fg_btn_capture.isChecked():
            self._set_capture_ui(False)

    def _on_page_changed(self, index):
        """Release the capture tool when the user leaves the Field Guide page."""
        if self.dialog.stack.widget(index) is self.dialog.fieldguide_page:
            return
        if self.dialog.fg_btn_capture.isChecked():
            self.marker_tool.disable()
            self._set_capture_ui(False)

    def _on_dialog_finished(self, _result):
        """Release the capture tool when the dialog closes."""
        if self.dialog.fg_btn_capture.isChecked():
            self.marker_tool.disable()
            self._set_capture_ui(False)

    def cleanup(self):
        """Release the capture tool and remove canvas graphics (plugin unload)."""
        self.marker_tool.disable()
        self.marker_tool.clear()

    # ------------------------------------------------------------------
    # Session state sync
    # ------------------------------------------------------------------

    def update_points(self, coordinates):
        """Refresh the session summary, point list, and action button states."""
        coordinates = list(coordinates)
        point_count = len(coordinates)
        self.dialog.fg_point_count_lbl.setText(str(point_count))

        points_list = self.dialog.fg_points_list
        points_list.blockSignals(True)
        points_list.clear()
        if point_count == 0:
            self.dialog.fg_last_point_lbl.setText(_tr("No points yet"))
            self.dialog.fg_route_status_lbl.setText(_tr("Add at least 2 points"))
        else:
            for index, (longitude, latitude) in enumerate(coordinates, start=1):
                points_list.addItem(
                    _tr("Point {index}: {lat:.6f}, {lon:.6f}").format(
                        index=index, lat=latitude, lon=longitude
                    )
                )
            last_longitude, last_latitude = coordinates[-1]
            self.dialog.fg_last_point_lbl.setText(
                "{:.6f}, {:.6f}".format(last_latitude, last_longitude)
            )
            self.dialog.fg_route_status_lbl.setText(
                _tr("Ready") if point_count >= 2 else _tr("Add at least 2 points")
            )
        points_list.blockSignals(False)

        self._update_action_states()

    def handle_selection_changed(self):
        """Keep selection-dependent actions synced with the list widget state."""
        self._update_action_states()

    def _update_action_states(self):
        """Enable only actions that are valid for the current session state."""
        point_count = len(self.marker_tool.coordinates)
        has_points = point_count > 0
        has_route = point_count >= 2
        has_selected_point = self.selected_point_index() >= 0
        self.dialog.fg_btn_remove_last.setEnabled(has_points)
        self.dialog.fg_btn_delete_selected.setEnabled(has_selected_point)
        self.dialog.fg_btn_clear.setEnabled(has_points)
        self.dialog.fg_btn_export_csv.setEnabled(has_points)
        self.dialog.fg_btn_export_gpx.setEnabled(has_points)
        self.dialog.fg_btn_temp_layer.setEnabled(has_points)
        self.dialog.fg_btn_pdf.setEnabled(has_points)
        self.dialog.fg_btn_route.setEnabled(has_route)

    def selected_point_index(self):
        """Return the selected point index from the live session list, if any."""
        point_count = len(self.marker_tool.coordinates)
        if point_count <= 0:
            return -1

        selected_indexes = self.dialog.fg_points_list.selectedIndexes()
        if not selected_indexes:
            return -1

        selected_row = selected_indexes[0].row()
        if selected_row < 0 or selected_row >= point_count:
            return -1
        return selected_row

    def select_point_index(self, index):
        """Select a point row when it exists, otherwise clear the list selection."""
        point_count = len(self.marker_tool.coordinates)
        points_list = self.dialog.fg_points_list
        if index < 0 or index >= point_count:
            points_list.clearSelection()
            points_list.setCurrentRow(-1)
        else:
            points_list.setCurrentRow(index)
        self._update_action_states()

    # ------------------------------------------------------------------
    # Mark management
    # ------------------------------------------------------------------

    def handle_clear_marks(self):
        """Remove all map marks and reset stored coordinate state."""
        n = len(self.marker_tool.coordinates)
        if n == 0:
            self._push_message(_tr("No marks to clear."), Qgis.Warning, 3)
            return

        if n > 3:
            confirmation = QMessageBox.question(
                self.dialog,
                _tr("Clear marks"),
                _tr("Clear all {0} captured point(s)?").format(n),
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
            if confirmation != QMessageBox.StandardButton.Yes:
                return

        self.marker_tool.clear()
        self._raster_session = None
        self._push_message(_tr("{0} mark(s) removed.").format(n), Qgis.Info, 3)

    def handle_remove_last(self):
        """Remove only the most recently captured map mark."""
        removed = self.marker_tool.remove_last()
        if not removed:
            self._push_message(_tr("No marks to remove."), Qgis.Warning, 3)
            return

        n = len(self.marker_tool.coordinates)
        self._push_message(
            _tr("Last mark removed. {0} point(s) remaining.").format(n), Qgis.Info, 3
        )

    def handle_delete_selected(self):
        """Remove the point selected in the session list, keeping order consistent."""
        selected_index = self.selected_point_index()
        if selected_index < 0:
            self._push_message(
                _tr("Select a mark in the session list to delete it."),
                Qgis.Warning,
                4,
            )
            return

        removed_point_number = selected_index + 1
        removed = self.marker_tool.remove_at(selected_index)
        if not removed:
            self._push_message(
                _tr("Unable to delete the selected mark."), Qgis.Warning, 4
            )
            return

        remaining_points = len(self.marker_tool.coordinates)
        self.select_point_index(min(selected_index, remaining_points - 1))
        self._push_message(
            _tr("Point {0} deleted. {1} point(s) remaining.").format(
                removed_point_number, remaining_points
            ),
            Qgis.Info,
            4,
        )

    # ------------------------------------------------------------------
    # Polygon feature sampling
    # ------------------------------------------------------------------

    def handle_mark_samples(self):
        """Place one or more sample marks for every feature in the selected layer."""
        if self.dialog.fg_use_raster_selection_checkbox.isChecked():
            self.extract_sample_points_with_raster()
            return

        layer = self.dialog.fg_layer_combo.currentLayer()
        if layer is None:
            self._push_message(
                _tr("Select a polygon layer from the current project first."),
                Qgis.Warning,
                4,
            )
            return

        sampling_settings = self._sampling_settings()
        action_title = self._polygon_sampling_action_title(sampling_settings)

        try:
            sampled_points, skipped_count = self.service.extract_layer_sample_points(
                layer,
                sampling_settings,
            )
        except Exception:
            QgsMessageLog.logMessage(
                traceback.format_exc(), "FARM tools", level=Qgis.Critical
            )
            self._push_message(
                _tr("Error generating marks from layer {0}.").format(layer.name()),
                Qgis.Critical,
                6,
            )
            return

        if not sampled_points:
            self._push_message(
                _tr("No valid sample marks found in layer {0}.").format(layer.name()),
                Qgis.Warning,
                5,
            )
            return

        merge_mode = 'append'
        existing_points = len(self.marker_tool.coordinates)
        if existing_points > 0:
            merge_mode = self._choose_points_merge_mode(
                existing_points,
                action_title,
                _tr(
                    "Choose whether to append the generated marks or replace "
                    "the current list."
                ),
            )
            if merge_mode is None:
                return

        if merge_mode == 'replace':
            self.marker_tool.clear()
            self._raster_session = None

        self.marker_tool.add_wgs84_points(sampled_points)

        points_label = self._sampling_points_label(sampling_settings)
        method_label = self._sampling_method_label(sampling_settings)
        sampled_point_count = len(sampled_points)

        if skipped_count > 0:
            self._push_message(
                _tr("{0} {1} added from {2} using {3}; {4} feature(s) skipped.").format(
                    sampled_point_count,
                    points_label,
                    layer.name(),
                    method_label,
                    skipped_count,
                ),
                Qgis.Info,
                6,
            )
            return

        self._push_message(
            _tr("{0} {1} added from {2} using {3}.").format(
                sampled_point_count,
                points_label,
                layer.name(),
                method_label,
            ),
            Qgis.Success,
            5,
        )

    def _sampling_settings(self):
        """Return the current polygon sampling quantity and distribution settings."""
        service = self.service
        quantity_mode = self.dialog.fg_quantity_mode_combo.currentData()
        sample_count = int(self.dialog.fg_samples_spin.value())
        hectares_per_mark = float(self.dialog.fg_density_spin.value())
        distribution_method = self.dialog.fg_distribution_combo.currentData()

        if quantity_mode not in {
            service.FEATURE_SAMPLE_QUANTITY_FIXED,
            service.FEATURE_SAMPLE_QUANTITY_DENSITY,
        }:
            quantity_mode = service.FEATURE_SAMPLE_QUANTITY_FIXED
        sample_count = max(1, min(service.MAX_MARKS_PER_FEATURE, sample_count))
        hectares_per_mark = max(0.1, hectares_per_mark)

        valid_methods = {
            service.FEATURE_SAMPLE_METHOD_SPREAD,
            service.FEATURE_SAMPLE_METHOD_GRID,
            service.FEATURE_SAMPLE_METHOD_ZIGZAG,
        }
        if distribution_method not in valid_methods:
            distribution_method = service.FEATURE_SAMPLE_METHOD_SPREAD
        if quantity_mode == service.FEATURE_SAMPLE_QUANTITY_FIXED and sample_count == 1:
            distribution_method = 'centroid'
        return {
            'quantity_mode': quantity_mode,
            'sample_count': sample_count,
            'hectares_per_mark': hectares_per_mark,
            'distribution_method': distribution_method,
        }

    def _polygon_sampling_action_title(self, sampling_settings):
        """Return a context-appropriate title for polygon sampling actions."""
        if (
            sampling_settings['quantity_mode'] == self.service.FEATURE_SAMPLE_QUANTITY_FIXED
            and sampling_settings['sample_count'] == 1
        ):
            return _tr("Mark feature centroids")
        return _tr("Mark feature samples")

    def _sampling_method_label(self, sampling_settings):
        """Return a label for the currently selected sampling method."""
        service = self.service
        distribution_method = sampling_settings['distribution_method']
        quantity_mode = sampling_settings['quantity_mode']
        sample_count = sampling_settings['sample_count']

        if (
            (
                quantity_mode == service.FEATURE_SAMPLE_QUANTITY_FIXED
                and sample_count == 1
            )
            or distribution_method == 'centroid'
        ):
            return _tr("centroid")

        if distribution_method == service.FEATURE_SAMPLE_METHOD_GRID:
            base_label = _tr("systematic grid")
        elif distribution_method == service.FEATURE_SAMPLE_METHOD_ZIGZAG:
            base_label = _tr("zigzag transect")
        else:
            base_label = _tr("spread optimized")

        if quantity_mode == service.FEATURE_SAMPLE_QUANTITY_DENSITY:
            density_label = '{:g}'.format(
                round(float(sampling_settings['hectares_per_mark']), 2)
            )
            return _tr("{0} at 1 mark per {1} ha").format(base_label, density_label)
        return base_label

    def _sampling_points_label(self, sampling_settings):
        """Return a label for the generated mark type."""
        if (
            sampling_settings['quantity_mode'] == self.service.FEATURE_SAMPLE_QUANTITY_FIXED
            and (
                sampling_settings['sample_count'] == 1
                or sampling_settings['distribution_method'] == 'centroid'
            )
        ):
            return _tr("centroid mark(s)")
        return _tr("sample mark(s)")

    # ------------------------------------------------------------------
    # Raster-based optimal point selection
    # ------------------------------------------------------------------

    def handle_raster_layer_changed(self, layer):
        """Validate the chosen raster and sync the band selector range."""
        band_selector = self.dialog.fg_raster_band_selector
        band_selector.blockSignals(True)
        if layer is None or not raster_analysis.raster_layer_supports_analysis(layer):
            band_selector.setRange(1, 1)
            band_selector.setValue(1)
            if (
                layer is not None
                and self.dialog.fg_use_raster_selection_checkbox.isChecked()
            ):
                self._push_message(
                    _tr(
                        "Layer {0} cannot be analyzed: web/tile rasters have "
                        "no readable pixel grid. Choose a file-based raster."
                    ).format(layer.name()),
                    Qgis.Warning,
                    5,
                )
        else:
            band_count = max(1, layer.bandCount())
            band_selector.setRange(1, band_count)
            if band_selector.value() > band_count:
                band_selector.setValue(1)
        band_selector.blockSignals(False)
        self._update_raster_status()

    def handle_raster_band_changed(self, _band_index):
        """Refresh the raster status line when the analyzed band changes."""
        self._update_raster_status()

    def handle_polygon_layer_changed(self, _layer):
        """Refresh the raster status line when the sampled polygon layer changes."""
        self._update_raster_status()

    def handle_use_raster_selection_toggled(self, checked):
        """Switch between manual marking and raster-based optimal selection."""
        self._update_raster_status()
        if not checked:
            return

        polygon_layer = self.dialog.fg_layer_combo.currentLayer()
        raster_layer = self.dialog.fg_raster_layer_combo.currentLayer()
        if polygon_layer is None or raster_layer is None:
            self._push_message(
                _tr(
                    "Select a polygon layer and a raster layer, then use "
                    "Mark optimal points (raster)."
                ),
                Qgis.Info,
                5,
            )
            return

        if not self.extract_sample_points_with_raster():
            checkbox = self.dialog.fg_use_raster_selection_checkbox
            checkbox.setChecked(False)

    def extract_sample_points_with_raster(self):
        """Compute and mark one optimal point per polygon from the raster.

        Returns True when points were marked, False on any validation
        failure, computation error, or user cancellation.
        """
        polygon_layer = self.dialog.fg_layer_combo.currentLayer()
        if polygon_layer is None:
            self._push_message(
                _tr("Select a polygon layer from the current project first."),
                Qgis.Warning,
                4,
            )
            return False

        raster_layer = self.dialog.fg_raster_layer_combo.currentLayer()
        if raster_layer is None:
            self._push_message(
                _tr("Select a raster layer for optimal point selection."),
                Qgis.Warning,
                4,
            )
            return False

        band_index = int(self.dialog.fg_raster_band_selector.value())

        QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
        try:
            sampled_points, point_values, skipped_count = (
                self.service.extract_optimal_points_from_raster(
                    polygon_layer,
                    raster_layer,
                    band_index,
                )
            )
        except ValueError as exc:
            self._push_message(str(exc), Qgis.Warning, 6)
            return False
        except Exception:
            QgsMessageLog.logMessage(
                traceback.format_exc(), "FARM tools", level=Qgis.Critical
            )
            self._push_message(
                _tr("Error computing optimal points from raster {0}.").format(
                    raster_layer.name()
                ),
                Qgis.Critical,
                6,
            )
            return False
        finally:
            QApplication.restoreOverrideCursor()

        if not sampled_points:
            self._push_message(
                _tr(
                    "No valid optimal points found: raster {0} has no usable "
                    "data inside the polygons of {1}."
                ).format(raster_layer.name(), polygon_layer.name()),
                Qgis.Warning,
                6,
            )
            return False

        merge_mode = 'append'
        existing_points = len(self.marker_tool.coordinates)
        if existing_points > 0:
            merge_mode = self._choose_points_merge_mode(
                existing_points,
                _tr("Mark optimal points (raster)"),
                _tr(
                    "Choose whether to append the generated marks or replace "
                    "the current list."
                ),
            )
            if merge_mode is None:
                return False

        if merge_mode == 'replace':
            self.marker_tool.clear()
            self._raster_session = None

        self.marker_tool.add_wgs84_points(sampled_points)
        self._store_raster_session(
            polygon_layer,
            raster_layer,
            band_index,
            sampled_points,
            point_values,
            skipped_count,
        )
        self._update_raster_status()

        if skipped_count > 0:
            self._push_message(
                _tr(
                    "{0} optimal point(s) added from {1} (band {2}); "
                    "{3} feature(s) skipped without valid raster data."
                ).format(
                    len(sampled_points),
                    raster_layer.name(),
                    band_index,
                    skipped_count,
                ),
                Qgis.Info,
                6,
            )
        else:
            self._push_message(
                _tr("{0} optimal point(s) added from {1} (band {2}).").format(
                    len(sampled_points), raster_layer.name(), band_index
                ),
                Qgis.Success,
                5,
            )
        return True

    def _store_raster_session(
        self,
        polygon_layer,
        raster_layer,
        band_index,
        sampled_points,
        point_values,
        skipped_count,
    ):
        """Persist raster selection metadata and per-point values for exports."""
        extent = raster_layer.extent()
        values = {}
        if self._raster_session is not None:
            values = dict(self._raster_session.get('values', {}))
        for (latitude, longitude), value in zip(sampled_points, point_values):
            values[(round(longitude, 8), round(latitude, 8))] = value

        self._raster_session = {
            'raster_selection_enabled': True,
            'raster_layer_name': raster_layer.name(),
            'raster_layer_crs': raster_layer.crs().authid(),
            'raster_band_index': band_index,
            'raster_extent': (
                extent.xMinimum(),
                extent.yMinimum(),
                extent.xMaximum(),
                extent.yMaximum(),
            ),
            'polygon_layer_name': polygon_layer.name(),
            'timestamp': datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ'),
            'skipped_features': skipped_count,
            'notes': 'Local maximum detection with 3x3 morphological kernel',
            'source_label': '{}:band_{}'.format(raster_layer.name(), band_index),
            'method_label': 'Local maximum (raster-based)',
            'values': values,
        }

    def _update_raster_status(self):
        """Refresh the raster status label from the current widget state."""
        status_label = self.dialog.fg_raster_status_label
        if not self.dialog.fg_use_raster_selection_checkbox.isChecked():
            status_label.setText(
                _tr(
                    "Manual marking mode. Enable raster selection to compute "
                    "optimal points."
                )
            )
            return

        raster_layer = self.dialog.fg_raster_layer_combo.currentLayer()
        if raster_layer is None:
            status_label.setText(
                _tr("Select a raster layer to compute optimal points.")
            )
            return

        if not raster_analysis.raster_layer_supports_analysis(raster_layer):
            status_label.setText(
                _tr(
                    "Raster {0} cannot be analyzed (web/tile layer). Choose a "
                    "file-based raster."
                ).format(raster_layer.name())
            )
            return

        band_index = int(self.dialog.fg_raster_band_selector.value())
        polygon_layer = self.dialog.fg_layer_combo.currentLayer()
        if polygon_layer is None:
            status_label.setText(
                _tr("Raster selected: {0} Band {1} | Select a polygon layer").format(
                    raster_layer.name(), band_index
                )
            )
            return

        status_label.setText(
            _tr(
                "Raster selected: {0} Band {1} | Ready to sample {2} feature(s)"
            ).format(
                raster_layer.name(), band_index, polygon_layer.featureCount()
            )
        )

    # ------------------------------------------------------------------
    # Manual coordinate
    # ------------------------------------------------------------------

    def handle_add_manual(self):
        """Validate manual decimal WGS84 input and create a numbered map point."""
        latitude_text = self.dialog.fg_lat_input.text().strip()
        longitude_text = self.dialog.fg_lon_input.text().strip()

        if not latitude_text or not longitude_text:
            self._push_message(
                _tr("Fill latitude and longitude to add a manual coordinate."),
                Qgis.Warning,
                4,
            )
            return

        try:
            latitude = parse_decimal(latitude_text)
            longitude = parse_decimal(longitude_text)
        except ValueError:
            self._push_message(
                _tr("Invalid coordinates. Use decimal format (e.g.: -23.550520)."),
                Qgis.Warning,
                4,
            )
            return

        if latitude < -90 or latitude > 90:
            self._push_message(
                _tr("Latitude is out of allowed range (-90 to 90)."), Qgis.Warning, 4
            )
            return

        if longitude < -180 or longitude > 180:
            self._push_message(
                _tr("Longitude is out of allowed range (-180 to 180)."), Qgis.Warning, 4
            )
            return

        try:
            self.marker_tool.add_wgs84_point(latitude, longitude)
        except Exception:
            QgsMessageLog.logMessage(
                traceback.format_exc(), "FARM tools", level=Qgis.Critical
            )
            self._push_message(
                _tr("Error adding manual coordinate."), Qgis.Critical, 5
            )
            return

        self.dialog.fg_lat_input.clear()
        self.dialog.fg_lon_input.clear()
        self.dialog.fg_lat_input.setFocus()

    # ------------------------------------------------------------------
    # Routes
    # ------------------------------------------------------------------

    def handle_route(self):
        """Open Google Maps directions using all captured points as ordered stops."""
        coordinates = self.marker_tool.coordinates
        if len(coordinates) < 2:
            self._push_message(
                _tr("Add at least 2 points to open a route in Google Maps."),
                Qgis.Warning,
                4,
            )
            return

        route_urls = []
        try:
            for batch in self.service.iter_route_batches(coordinates):
                route_urls.append(build_google_maps_directions_url(batch))
        except Exception:
            self._push_message(_tr("Could not build route."), Qgis.Critical, 5)
            return

        if len(route_urls) > 1:
            self._push_message(
                _tr("Large route detected. Opening {0} Google Maps segments.").format(
                    len(route_urls)
                ),
                Qgis.Info,
                5,
            )

        opened_count = 0
        for url in route_urls:
            if QDesktopServices.openUrl(QUrl(url)):
                opened_count += 1

        if opened_count == 0:
            self._push_message(
                _tr("Could not open route in Google Maps."), Qgis.Warning, 4
            )
            return

        if len(route_urls) == 1:
            self._push_message(
                _tr("Route opened in Google Maps with {0} point(s).").format(
                    len(coordinates)
                ),
                Qgis.Success,
                4,
            )
            return

        self._push_message(
            _tr("Large route split into {0} segments in Google Maps.").format(
                opened_count
            ),
            Qgis.Info,
            5,
        )

    # ------------------------------------------------------------------
    # Import / export
    # ------------------------------------------------------------------

    def handle_export_csv(self):
        """Export captured WGS84 points to a CSV file (longitude, latitude)."""
        coordinates = self.marker_tool.coordinates
        if not coordinates:
            self._push_message(_tr("There are no points to export."), Qgis.Warning, 4)
            return

        output_path, _ = QFileDialog.getSaveFileName(
            self.dialog,
            _tr("Save points to CSV"),
            self._default_output_path('field_guide_points.csv'),
            'CSV Files (*.csv)',
        )
        if not output_path:
            return

        raster_session = self._raster_session
        try:
            with open(output_path, mode='w', newline='', encoding='utf-8') as csv_file:
                writer = csv.writer(csv_file)
                header = ['order', 'longitude', 'latitude']
                if raster_session is not None:
                    header += [
                        'raster_source',
                        'selection_method',
                        'raster_value_at_point',
                    ]
                writer.writerow(header)
                for index, (longitude, latitude) in enumerate(coordinates, start=1):
                    row = [
                        index,
                        '{:.8f}'.format(longitude),
                        '{:.8f}'.format(latitude),
                    ]
                    if raster_session is not None:
                        signature = (round(longitude, 8), round(latitude, 8))
                        value = raster_session['values'].get(signature)
                        if value is not None:
                            row += [
                                raster_session['source_label'],
                                raster_session['method_label'],
                                '{:.6f}'.format(value),
                            ]
                        else:
                            row += ['', '', '']
                    writer.writerow(row)
        except Exception:
            QgsMessageLog.logMessage(
                traceback.format_exc(), "FARM tools", level=Qgis.Critical
            )
            self._push_message(_tr("Error exporting CSV."), Qgis.Critical, 6)
            return

        self._push_message(
            _tr("CSV exported successfully: {0}").format(output_path), Qgis.Success, 5
        )

    def handle_export_gpx(self):
        """Export captured WGS84 points to a GPS-compatible GPX file."""
        coordinates = self.marker_tool.coordinates
        if not coordinates:
            self._push_message(_tr("There are no points to export."), Qgis.Warning, 4)
            return

        output_path, _ = QFileDialog.getSaveFileName(
            self.dialog,
            _tr("Save points to GPX"),
            self._default_output_path('field_guide_points.gpx'),
            'GPX Files (*.gpx)',
        )
        if not output_path:
            return
        if not output_path.lower().endswith('.gpx'):
            output_path += '.gpx'

        raster_metadata = None
        if self._raster_session is not None:
            raster_metadata = {
                'source': self._raster_session['source_label'],
                'method': self._raster_session['method_label'],
                'values': self._raster_session['values'],
            }

        try:
            self.service.write_marks_gpx(
                output_path, coordinates, raster_metadata=raster_metadata
            )
        except Exception:
            QgsMessageLog.logMessage(
                traceback.format_exc(), "FARM tools", level=Qgis.Critical
            )
            self._push_message(_tr("Error exporting GPX."), Qgis.Critical, 6)
            return

        self._push_message(
            _tr("GPX exported successfully: {0}").format(output_path), Qgis.Success, 5
        )

    def handle_temp_layer(self):
        """Add the current marks to the project as a temporary point vector layer."""
        coordinates = self.marker_tool.coordinates
        if not coordinates:
            self._push_message(_tr("There are no points to add."), Qgis.Warning, 4)
            return

        try:
            layer = self.service.build_temp_marks_layer(coordinates)
        except Exception:
            QgsMessageLog.logMessage(
                traceback.format_exc(), "FARM tools", level=Qgis.Critical
            )
            layer = None

        if layer is None:
            self._push_message(
                _tr("Could not create the temporary point layer."), Qgis.Critical, 6
            )
            return

        self.service.project.addMapLayer(layer)
        self._push_message(
            _tr("Temporary layer added to the project: {0} ({1} point(s)).").format(
                layer.name(), len(coordinates)
            ),
            Qgis.Success,
            5,
        )

    def handle_import_csv(self):
        """Import WGS84 points from CSV and draw them on the map canvas."""
        input_path, _ = QFileDialog.getOpenFileName(
            self.dialog,
            _tr("Import points CSV"),
            '',
            'CSV Files (*.csv);;All Files (*)',
        )
        if not input_path:
            return

        import_mode = 'append'
        existing_points = len(self.marker_tool.coordinates)
        if existing_points > 0:
            import_mode = self._choose_points_merge_mode(
                existing_points,
                _tr("Import points CSV"),
                _tr(
                    "Choose whether to append imported points or replace the "
                    "current list."
                ),
            )
            if import_mode is None:
                return

        try:
            valid_points, skipped_count = self.service.parse_csv_points(input_path)
        except ValueError as exc:
            self._push_message(str(exc), Qgis.Warning, 6)
            return
        except Exception:
            QgsMessageLog.logMessage(
                traceback.format_exc(), "FARM tools", level=Qgis.Critical
            )
            self._push_message(_tr("Error importing CSV."), Qgis.Critical, 6)
            return

        imported_count = len(valid_points)
        if imported_count == 0:
            self._push_message(
                _tr("No valid points found in CSV."), Qgis.Warning, 5
            )
            return

        if import_mode == 'replace':
            self.marker_tool.clear()
            self._raster_session = None

        self.marker_tool.add_wgs84_points(valid_points)

        if skipped_count > 0:
            self._push_message(
                _tr("{0} point(s) imported; {1} row(s) skipped.").format(
                    imported_count, skipped_count
                ),
                Qgis.Info,
                6,
            )
            return

        self._push_message(
            _tr("{0} point(s) imported successfully.").format(imported_count),
            Qgis.Success,
            5,
        )

    def handle_generate_pdf(self):
        """Generate PDF report with current canvas screenshot and map links."""
        coordinates = self.marker_tool.coordinates
        if not coordinates:
            self._push_message(
                _tr("No points marked. Add map points before generating the PDF."),
                Qgis.Warning,
                4,
            )
            return

        output_path, _ = QFileDialog.getSaveFileName(
            self.dialog,
            _tr("Save Field Guide PDF"),
            self._default_output_path('field_guide.pdf'),
            'PDF Files (*.pdf)',
        )
        if not output_path:
            return

        footer_note = None
        if self._raster_session is not None:
            footer_note = _tr(
                "Points selected using raster-based optimal location: {0} "
                "(Band {1}). Local maximum detection applied within each "
                "polygon boundary."
            ).format(
                self._raster_session['raster_layer_name'],
                self._raster_session['raster_band_index'],
            )

        try:
            final_path = self.pdf_composer.generate(
                coordinates, output_path, footer_note=footer_note
            )
        except Exception as exc:
            QgsMessageLog.logMessage(
                traceback.format_exc(), "FARM tools", level=Qgis.Critical
            )
            error_detail = str(exc).strip()
            if error_detail:
                user_message = _tr("Error generating PDF: {0}").format(error_detail)
            else:
                user_message = _tr("Error generating PDF.")
            self._push_message(user_message, Qgis.Critical, 8)
            return

        self._push_message(
            _tr("PDF generated successfully: {0}").format(final_path), Qgis.Success, 5
        )

        opened = QDesktopServices.openUrl(QUrl.fromLocalFile(final_path))
        if not opened:
            self._push_message(
                _tr("PDF saved, but could not be opened automatically."),
                Qgis.Warning,
                4,
            )

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

    def _choose_points_merge_mode(self, existing_points, window_title, informative_text):
        """Ask whether new points should append to or replace current points."""
        message_box = QMessageBox(self.dialog)
        message_box.setIcon(QMessageBox.Icon.Question)
        message_box.setWindowTitle(window_title)
        message_box.setText(
            _tr("There are already {0} point(s) in this session.").format(
                existing_points
            )
        )
        message_box.setInformativeText(informative_text)
        append_button = message_box.addButton(
            _tr("Append"), QMessageBox.ButtonRole.AcceptRole
        )
        replace_button = message_box.addButton(
            _tr("Replace"), QMessageBox.ButtonRole.DestructiveRole
        )
        message_box.addButton(_tr("Cancel"), QMessageBox.ButtonRole.RejectRole)
        message_box.setDefaultButton(append_button)
        message_box.exec()

        clicked = message_box.clickedButton()
        if clicked == append_button:
            return 'append'
        if clicked == replace_button:
            return 'replace'
        return None
