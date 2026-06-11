# -*- coding: utf-8 -*-
"""Headless Field Guide logic: polygon sampling, serialization, and routes.

No widget references live here; ``controllers/fieldguide_ctrl.py`` owns all UI
interplay and delegates the pure work to this service.
"""

import csv
import math
import random
import xml.etree.ElementTree as ET

from qgis.PyQt.QtCore import QCoreApplication, QVariant
from qgis.core import (
    QgsCoordinateReferenceSystem,
    QgsCoordinateTransform,
    QgsDistanceArea,
    QgsFeature,
    QgsField,
    QgsGeometry,
    QgsPointXY,
    QgsProject,
    QgsVectorLayer,
)


def _tr(text):
    return QCoreApplication.translate("RAVI", text)


def parse_decimal(value):
    """Parse decimal coordinate text, accepting comma or dot separators."""
    normalized = value.replace(',', '.')
    return float(normalized)


class FieldGuideService:
    """Pure sampling, export, and route logic for the Field Guide page."""

    MAX_POINTS_PER_GOOGLE_ROUTE = 10
    MAX_MARKS_PER_FEATURE = 50
    FEATURE_SAMPLE_METHOD_SPREAD = 'spread_optimized'
    FEATURE_SAMPLE_METHOD_GRID = 'systematic_grid'
    FEATURE_SAMPLE_METHOD_ZIGZAG = 'zigzag_transect'
    FEATURE_SAMPLE_QUANTITY_FIXED = 'fixed_count'
    FEATURE_SAMPLE_QUANTITY_DENSITY = 'area_density'

    def __init__(self):
        self.project = QgsProject.instance()
        self.wgs84 = QgsCoordinateReferenceSystem('EPSG:4326')

    # ------------------------------------------------------------------
    # Polygon feature sampling
    # ------------------------------------------------------------------

    def extract_layer_sample_points(self, layer, sampling_settings):
        """Return WGS84 sample marks for each feature in the selected polygon layer."""
        sampled_points = []
        skipped_count = 0
        transform = QgsCoordinateTransform(layer.crs(), self.wgs84, self.project)
        area_measure = None
        if sampling_settings['quantity_mode'] == self.FEATURE_SAMPLE_QUANTITY_DENSITY:
            area_measure = self._build_area_measure(layer)

        for feature in layer.getFeatures():
            geometry = feature.geometry()
            if geometry is None or geometry.isEmpty():
                skipped_count += 1
                continue

            try:
                feature_sample_count = self._feature_sample_count(
                    geometry,
                    sampling_settings,
                    area_measure=area_measure,
                )
                feature_points = self._build_feature_sample_points(
                    layer,
                    feature,
                    geometry,
                    feature_sample_count,
                    sampling_settings['distribution_method'],
                )
            except Exception:
                skipped_count += 1
                continue

            if len(feature_points) != feature_sample_count:
                skipped_count += 1
                continue

            feature_wgs84_points = []
            failed_feature = False
            for point in feature_points:
                try:
                    wgs84_point = transform.transform(point)
                except Exception:
                    failed_feature = True
                    break
                feature_wgs84_points.append((wgs84_point.y(), wgs84_point.x()))

            if failed_feature:
                skipped_count += 1
                continue

            sampled_points.extend(feature_wgs84_points)

        return sampled_points, skipped_count

    def _build_area_measure(self, layer):
        """Return a configured area measurer for geometries in the layer CRS."""
        area_measure = QgsDistanceArea()
        area_measure.setSourceCrs(layer.crs(), self.project.transformContext())
        ellipsoid = self.project.ellipsoid()
        if not ellipsoid or str(ellipsoid).upper() == 'NONE':
            ellipsoid = 'WGS84'
        area_measure.setEllipsoid(ellipsoid)
        return area_measure

    def _feature_sample_count(self, geometry, sampling_settings, area_measure=None):
        """Resolve the number of marks to generate for a single feature."""
        if sampling_settings['quantity_mode'] != self.FEATURE_SAMPLE_QUANTITY_DENSITY:
            return max(1, min(self.MAX_MARKS_PER_FEATURE, sampling_settings['sample_count']))

        if area_measure is None:
            return 1

        area_square_meters = abs(area_measure.measureArea(geometry))
        area_hectares = area_square_meters / 10000.0
        hectares_per_mark = max(0.1, float(sampling_settings['hectares_per_mark']))
        sample_count = int(math.ceil(max(area_hectares, 1e-9) / hectares_per_mark))
        return max(1, min(self.MAX_MARKS_PER_FEATURE, sample_count))

    def _build_feature_sample_points(
        self,
        layer,
        feature,
        geometry,
        sample_count,
        distribution_method,
    ):
        """Build the requested sampling pattern for a single polygon feature."""
        if sample_count <= 1 or distribution_method == 'centroid':
            centroid_point = self._feature_centroid_point(geometry)
            return [centroid_point] if centroid_point is not None else []

        bounds = geometry.boundingBox()
        if bounds.isEmpty() or bounds.width() <= 0 or bounds.height() <= 0:
            return []

        seed_token = '{}:{}:{}:{}:{:.6f}:{:.6f}:{:.6f}:{:.6f}'.format(
            layer.name(),
            feature.id(),
            distribution_method,
            sample_count,
            bounds.xMinimum(),
            bounds.yMinimum(),
            bounds.xMaximum(),
            bounds.yMaximum(),
        )
        sampling_geometry = self._preferred_sampling_geometry(
            geometry,
            sample_count,
            distribution_method,
        )
        candidates = self._build_feature_candidate_points(
            sampling_geometry,
            sample_count,
            seed_token,
        )
        if len(candidates) < sample_count:
            return []

        if distribution_method == self.FEATURE_SAMPLE_METHOD_GRID:
            selected_points = self._systematic_grid_points(
                sampling_geometry,
                candidates,
                sample_count,
            )
        elif distribution_method == self.FEATURE_SAMPLE_METHOD_ZIGZAG:
            targets = self._zigzag_targets(candidates, sample_count)
            selected_points = self._select_points_from_targets(targets, candidates)
        else:
            selected_points = self._select_maximin_points(candidates, sample_count)
            selected_points = self._sort_points_top_down(selected_points)

        selected_points = self._extend_selection_with_spread(
            selected_points,
            candidates,
            sample_count,
        )
        if len(selected_points) < sample_count:
            return []
        return selected_points[:sample_count]

    def _feature_centroid_point(self, geometry):
        """Return the polygon centroid point when available."""
        centroid_geometry = geometry.centroid()
        if centroid_geometry is None or centroid_geometry.isEmpty():
            return None
        return QgsPointXY(centroid_geometry.asPoint())

    def _feature_point_on_surface(self, geometry):
        """Return an interior point for the polygon when available."""
        point_geometry = geometry.pointOnSurface()
        if point_geometry is None or point_geometry.isEmpty():
            return None
        return QgsPointXY(point_geometry.asPoint())

    def _preferred_sampling_geometry(self, geometry, sample_count, distribution_method):
        """Return an inset polygon when possible so marks stay away from borders."""
        bounds = geometry.boundingBox()
        min_dimension = min(bounds.width(), bounds.height())
        if min_dimension <= 0:
            return geometry

        if distribution_method == self.FEATURE_SAMPLE_METHOD_GRID:
            inset_ratios = [0.05, 0.035, 0.02, 0.01]
        elif distribution_method == self.FEATURE_SAMPLE_METHOD_ZIGZAG:
            inset_ratios = [0.10, 0.07, 0.05, 0.03]
        else:
            inset_ratios = [0.12, 0.08, 0.05, 0.03]

        if sample_count >= 7 and distribution_method != self.FEATURE_SAMPLE_METHOD_GRID:
            inset_ratios = [0.10, 0.07, 0.05, 0.03]

        for inset_ratio in inset_ratios:
            inset_distance = min_dimension * inset_ratio
            if inset_distance <= 0:
                continue

            inset_geometry = geometry.buffer(-inset_distance, 8)
            if inset_geometry is None or inset_geometry.isEmpty():
                continue

            inset_bounds = inset_geometry.boundingBox()
            if inset_bounds.isEmpty() or inset_bounds.width() <= 0 or inset_bounds.height() <= 0:
                continue
            return inset_geometry

        return geometry

    def _build_feature_candidate_points(self, geometry, sample_count, seed_token):
        """Build a deterministic pool of candidate points inside one polygon."""
        bounds = geometry.boundingBox()
        if bounds.isEmpty() or bounds.width() <= 0 or bounds.height() <= 0:
            return []

        tolerance = max(bounds.width(), bounds.height()) / 1000000.0
        if tolerance <= 0:
            tolerance = 1e-9

        candidates = []
        seen_keys = set()

        self._append_candidate_point(
            candidates,
            seen_keys,
            self._feature_point_on_surface(geometry),
            geometry,
            tolerance,
            allow_boundary=True,
        )
        self._append_candidate_point(
            candidates,
            seen_keys,
            self._feature_centroid_point(geometry),
            geometry,
            tolerance,
            allow_boundary=False,
        )

        grid_divisions = max(6, int(math.ceil(math.sqrt(sample_count * 24))))
        self._append_grid_candidates(
            candidates,
            seen_keys,
            geometry,
            bounds,
            tolerance,
            grid_divisions,
            x_offset_ratio=0.5,
            y_offset_ratio=0.5,
        )
        self._append_grid_candidates(
            candidates,
            seen_keys,
            geometry,
            bounds,
            tolerance,
            grid_divisions,
            x_offset_ratio=0.25,
            y_offset_ratio=0.75,
        )

        rng = random.Random(seed_token)
        target_candidate_count = max(sample_count * 18, 80)
        max_attempts = max(target_candidate_count * 10, 400)
        attempts = 0
        while len(candidates) < target_candidate_count and attempts < max_attempts:
            attempts += 1
            candidate = QgsPointXY(
                rng.uniform(bounds.xMinimum(), bounds.xMaximum()),
                rng.uniform(bounds.yMinimum(), bounds.yMaximum()),
            )
            self._append_candidate_point(
                candidates,
                seen_keys,
                candidate,
                geometry,
                tolerance,
                allow_boundary=False,
            )

        return candidates

    def _append_grid_candidates(
        self,
        candidates,
        seen_keys,
        geometry,
        bounds,
        tolerance,
        grid_divisions,
        x_offset_ratio,
        y_offset_ratio,
    ):
        """Append deterministic grid candidates inside the polygon bounds."""
        x_step = bounds.width() / float(grid_divisions)
        y_step = bounds.height() / float(grid_divisions)
        if x_step <= 0 or y_step <= 0:
            return

        for row_index in range(grid_divisions):
            y = bounds.yMinimum() + (row_index + y_offset_ratio) * y_step
            for column_index in range(grid_divisions):
                x = bounds.xMinimum() + (column_index + x_offset_ratio) * x_step
                self._append_candidate_point(
                    candidates,
                    seen_keys,
                    QgsPointXY(x, y),
                    geometry,
                    tolerance,
                    allow_boundary=False,
                )

    def _append_candidate_point(
        self,
        candidates,
        seen_keys,
        point,
        geometry,
        tolerance,
        allow_boundary=False,
    ):
        """Add a point to the candidate pool when it is valid and unique."""
        if point is None:
            return

        point = QgsPointXY(point)
        point_key = (
            int(round(point.x() / tolerance)),
            int(round(point.y() / tolerance)),
        )
        if point_key in seen_keys:
            return

        point_geometry = QgsGeometry.fromPointXY(point)
        is_inside = geometry.contains(point_geometry)
        if not is_inside and allow_boundary:
            is_inside = geometry.intersects(point_geometry)
        if not is_inside:
            return

        candidates.append(point)
        seen_keys.add(point_key)

    def _systematic_grid_points(self, geometry, candidates, sample_count):
        """Return grid-aligned points that preserve shared rows and columns."""
        if not candidates:
            return []

        origin_point, axis_x, axis_y = self._feature_reference_frame(candidates)
        local_candidates = [
            self._project_point_to_frame(point, origin_point, axis_x, axis_y)
            for point in candidates
        ]

        major_min = min(local_point[0] for local_point in local_candidates)
        major_max = max(local_point[0] for local_point in local_candidates)
        minor_min = min(local_point[1] for local_point in local_candidates)
        minor_max = max(local_point[1] for local_point in local_candidates)
        major_span = major_max - major_min
        minor_span = minor_max - minor_min
        if major_span <= 0 or minor_span <= 0:
            return []

        column_count, row_count = self._best_grid_dimensions(
            sample_count,
            major_span / float(max(minor_span, 1e-9)),
        )
        row_sizes = self._balanced_row_sizes(sample_count, row_count, column_count)

        minor_step = minor_span / float(row_count)
        major_step = major_span / float(column_count)
        column_positions = [
            major_min + (column_index + 0.5) * major_step
            for column_index in range(column_count)
        ]
        remaining_candidates = list(candidates)
        selected_points = []
        selected_keys = set()
        for row_index, row_size in enumerate(row_sizes):
            minor_coord = minor_max - (row_index + 0.5) * minor_step
            column_indexes = self._grid_slot_indexes(row_size, column_count)
            for column_index in column_indexes:
                target_point = self._point_from_frame(
                    column_positions[column_index],
                    minor_coord,
                    origin_point,
                    axis_x,
                    axis_y,
                )
                point_signature = self._point_signature(target_point)
                if (
                    point_signature not in selected_keys
                    and self._geometry_accepts_point(geometry, target_point)
                ):
                    selected_points.append(target_point)
                    selected_keys.add(point_signature)
                    remaining_candidates = [
                        candidate
                        for candidate in remaining_candidates
                        if self._point_signature(candidate) != point_signature
                    ]
                    continue

                if not remaining_candidates:
                    continue

                nearest_index = min(
                    range(len(remaining_candidates)),
                    key=lambda index: self._distance_squared(
                        remaining_candidates[index],
                        target_point,
                    ),
                )
                chosen_point = remaining_candidates.pop(nearest_index)
                chosen_signature = self._point_signature(chosen_point)
                if chosen_signature in selected_keys:
                    continue
                selected_points.append(chosen_point)
                selected_keys.add(chosen_signature)

        return selected_points

    def _best_grid_dimensions(self, sample_count, aspect_ratio):
        """Choose grid dimensions that fit the feature aspect while staying balanced."""
        best_columns = sample_count
        best_rows = 1
        best_score = None

        for row_count in range(1, sample_count + 1):
            column_count = int(math.ceil(float(sample_count) / float(row_count)))
            grid_aspect = column_count / float(max(row_count, 1))
            empty_slots = row_count * column_count - sample_count
            score = abs(math.log(max(grid_aspect, 1e-9) / max(aspect_ratio, 1e-9)))
            score += empty_slots * 0.18
            score += abs(column_count - row_count) * 0.03

            if best_score is None or score < best_score:
                best_score = score
                best_columns = column_count
                best_rows = row_count

        return best_columns, best_rows

    def _balanced_row_sizes(self, sample_count, row_count, column_count):
        """Distribute points across rows as evenly as possible."""
        row_sizes = [sample_count // row_count] * row_count
        remainder = sample_count % row_count
        start_index = max(0, (row_count - remainder) // 2)

        for offset_index in range(remainder):
            target_index = start_index + offset_index
            if target_index >= row_count:
                target_index = row_count - 1 - (target_index - row_count)
            row_sizes[target_index] += 1

        return [min(column_count, max(1, row_size)) for row_size in row_sizes]

    def _grid_slot_indexes(self, slot_count, total_slots):
        """Return evenly spread slot indexes from a fixed column grid."""
        if slot_count <= 0 or total_slots <= 0:
            return []
        if slot_count >= total_slots:
            return list(range(total_slots))
        if slot_count == 1:
            return [total_slots // 2]

        last_slot_index = total_slots - 1
        last_point_index = slot_count - 1
        return [
            int(round(point_index * last_slot_index / float(last_point_index)))
            for point_index in range(slot_count)
        ]

    def _geometry_accepts_point(self, geometry, point):
        """Return True when the point lies inside or on the polygon boundary."""
        point_geometry = QgsGeometry.fromPointXY(QgsPointXY(point))
        return geometry.contains(point_geometry) or geometry.intersects(point_geometry)

    def _zigzag_targets(self, candidates, sample_count):
        """Return classic zigzag targets using the feature's long axis and side edges."""
        if not candidates:
            return []

        origin_point, axis_x, axis_y = self._feature_reference_frame(candidates)
        local_candidates = [
            {
                'point': point,
                'major': projected_point[0],
                'minor': projected_point[1],
            }
            for point in candidates
            for projected_point in [self._project_point_to_frame(point, origin_point, axis_x, axis_y)]
        ]

        major_min = min(item['major'] for item in local_candidates)
        major_max = max(item['major'] for item in local_candidates)
        minor_min = min(item['minor'] for item in local_candidates)
        minor_max = max(item['minor'] for item in local_candidates)

        major_span = major_max - major_min
        minor_span = minor_max - minor_min
        if major_span <= 0 or minor_span <= 0:
            return []

        start_major = major_max - major_span * 0.06
        end_major = major_min + major_span * 0.06
        if sample_count == 1:
            major_targets = [(start_major + end_major) / 2.0]
        else:
            major_step = (start_major - end_major) / float(sample_count - 1)
            major_targets = [
                start_major - point_index * major_step
                for point_index in range(sample_count)
            ]

        band_half_window = max(
            major_span / float(max(sample_count * 2, 4)),
            major_span * 0.06,
        )
        remaining_candidates = list(local_candidates)
        selected_points = []
        prefer_high_minor = False
        low_minor_target = minor_min + minor_span * 0.24
        high_minor_target = minor_max - minor_span * 0.24

        for target_major in major_targets:
            if not remaining_candidates:
                break

            band_candidates = [
                candidate
                for candidate in remaining_candidates
                if abs(candidate['major'] - target_major) <= band_half_window
            ]
            if not band_candidates:
                nearest_major_distance = min(
                    abs(candidate['major'] - target_major)
                    for candidate in remaining_candidates
                )
                band_candidates = [
                    candidate
                    for candidate in remaining_candidates
                    if abs(candidate['major'] - target_major) <= nearest_major_distance
                ]

            chosen_candidate = max(
                band_candidates,
                key=lambda candidate: self._zigzag_candidate_score(
                    candidate,
                    target_major,
                    high_minor_target if prefer_high_minor else low_minor_target,
                    major_span,
                ),
            )
            selected_points.append(chosen_candidate['point'])
            remaining_candidates.remove(chosen_candidate)
            prefer_high_minor = not prefer_high_minor

        return selected_points

    def _zigzag_candidate_score(
        self,
        candidate,
        target_major,
        target_minor,
        major_span,
    ):
        """Score a candidate for one zigzag slice using interior lane plus slice fit."""
        if major_span <= 0:
            major_span = 1.0

        minor_penalty = abs(candidate['minor'] - target_minor)
        distance_penalty = abs(candidate['major'] - target_major) / major_span
        return -minor_penalty - distance_penalty * 0.30

    def _feature_reference_frame(self, points):
        """Return origin plus orthogonal axes aligned to the dominant point spread."""
        center_x = sum(point.x() for point in points) / float(len(points))
        center_y = sum(point.y() for point in points) / float(len(points))

        sxx = 0.0
        syy = 0.0
        sxy = 0.0
        for point in points:
            dx = point.x() - center_x
            dy = point.y() - center_y
            sxx += dx * dx
            syy += dy * dy
            sxy += dx * dy

        if abs(sxy) < 1e-12 and abs(sxx - syy) < 1e-12:
            angle = 0.0
        else:
            angle = 0.5 * math.atan2(2.0 * sxy, sxx - syy)

        axis_x = (math.cos(angle), math.sin(angle))
        axis_y = (-axis_x[1], axis_x[0])
        return QgsPointXY(center_x, center_y), axis_x, axis_y

    def _project_point_to_frame(self, point, origin_point, axis_x, axis_y):
        """Project a map point into the local oriented frame."""
        dx = point.x() - origin_point.x()
        dy = point.y() - origin_point.y()
        return (
            dx * axis_x[0] + dy * axis_x[1],
            dx * axis_y[0] + dy * axis_y[1],
        )

    def _point_from_frame(self, major_coord, minor_coord, origin_point, axis_x, axis_y):
        """Return a world-coordinate point from oriented-frame coordinates."""
        return QgsPointXY(
            origin_point.x() + major_coord * axis_x[0] + minor_coord * axis_y[0],
            origin_point.y() + major_coord * axis_x[1] + minor_coord * axis_y[1],
        )

    def _select_points_from_targets(self, targets, candidates):
        """Assign one unique candidate point to each target in order."""
        remaining_candidates = list(candidates)
        selected_points = []

        for target in targets:
            if not remaining_candidates:
                break
            nearest_index = min(
                range(len(remaining_candidates)),
                key=lambda index: self._distance_squared(
                    remaining_candidates[index],
                    target,
                ),
            )
            selected_points.append(remaining_candidates.pop(nearest_index))

        return selected_points

    def _select_maximin_points(self, candidates, sample_count):
        """Choose points that maximize separation inside the polygon."""
        if sample_count <= 0 or not candidates:
            return []
        if sample_count >= len(candidates):
            return list(candidates)
        if len(candidates) == 1:
            return [candidates[0]]

        first_index = 0
        second_index = 1
        best_pair_distance = -1.0
        for left_index in range(len(candidates) - 1):
            for right_index in range(left_index + 1, len(candidates)):
                pair_distance = self._distance_squared(
                    candidates[left_index],
                    candidates[right_index],
                )
                if pair_distance > best_pair_distance:
                    best_pair_distance = pair_distance
                    first_index = left_index
                    second_index = right_index

        selected_points = [candidates[first_index], candidates[second_index]]
        selected_keys = {
            self._point_signature(candidates[first_index]),
            self._point_signature(candidates[second_index]),
        }
        remaining_candidates = [
            point
            for point in candidates
            if self._point_signature(point) not in selected_keys
        ]

        while len(selected_points) < sample_count and remaining_candidates:
            best_index = max(
                range(len(remaining_candidates)),
                key=lambda index: self._minimum_distance_squared(
                    remaining_candidates[index],
                    selected_points,
                ),
            )
            selected_points.append(remaining_candidates.pop(best_index))

        return selected_points

    def _extend_selection_with_spread(self, selected_points, candidates, sample_count):
        """Fill any missing slots using the best remaining spatial spread."""
        selected_points = list(selected_points)
        selected_keys = {
            self._point_signature(point)
            for point in selected_points
        }
        remaining_candidates = [
            point
            for point in candidates
            if self._point_signature(point) not in selected_keys
        ]

        while len(selected_points) < sample_count and remaining_candidates:
            if selected_points:
                best_index = max(
                    range(len(remaining_candidates)),
                    key=lambda index: self._minimum_distance_squared(
                        remaining_candidates[index],
                        selected_points,
                    ),
                )
            else:
                bounds = self._points_bounds(remaining_candidates)
                center_point = QgsPointXY(
                    (bounds.xMinimum() + bounds.xMaximum()) / 2.0,
                    (bounds.yMinimum() + bounds.yMaximum()) / 2.0,
                )
                best_index = max(
                    range(len(remaining_candidates)),
                    key=lambda index: self._distance_squared(
                        remaining_candidates[index],
                        center_point,
                    ),
                )

            selected_points.append(remaining_candidates.pop(best_index))

        return selected_points

    def _sort_points_top_down(self, points):
        """Sort points in a stable north-to-south, west-to-east order."""
        return sorted(points, key=lambda point: (-point.y(), point.x()))

    def _points_bounds(self, points):
        """Return a bounding box that covers the given points."""
        x_min = min(point.x() for point in points)
        x_max = max(point.x() for point in points)
        y_min = min(point.y() for point in points)
        y_max = max(point.y() for point in points)
        return QgsGeometry.fromPolygonXY(
            [[
                QgsPointXY(x_min, y_min),
                QgsPointXY(x_max, y_min),
                QgsPointXY(x_max, y_max),
                QgsPointXY(x_min, y_max),
                QgsPointXY(x_min, y_min),
            ]]
        ).boundingBox()

    def _minimum_distance_squared(self, point, other_points):
        """Return the minimum squared distance from point to a list of points."""
        return min(
            self._distance_squared(point, other_point)
            for other_point in other_points
        )

    def _distance_squared(self, left_point, right_point):
        """Return squared planar distance between two QgsPointXY objects."""
        dx = left_point.x() - right_point.x()
        dy = left_point.y() - right_point.y()
        return dx * dx + dy * dy

    def _point_signature(self, point):
        """Return a stable point signature for set membership."""
        return (round(point.x(), 9), round(point.y(), 9))

    # ------------------------------------------------------------------
    # Routes
    # ------------------------------------------------------------------

    def iter_route_batches(self, coordinates):
        """Yield route chunks with overlap so segment continuity is preserved."""
        max_points = self.MAX_POINTS_PER_GOOGLE_ROUTE
        if len(coordinates) <= max_points:
            yield coordinates
            return

        start = 0
        while start < len(coordinates) - 1:
            end = min(start + max_points, len(coordinates))
            yield coordinates[start:end]
            if end >= len(coordinates):
                break
            start = end - 1

    # ------------------------------------------------------------------
    # CSV import
    # ------------------------------------------------------------------

    def parse_csv_points(self, input_path):
        """Read and validate WGS84 points from CSV.

        Returns ``(valid_points, skipped_count)`` where valid points are
        ``(latitude, longitude)`` tuples. Raises ``ValueError`` with a
        user-facing message when the file structure is invalid.
        """
        valid_points = []
        skipped_count = 0

        with open(input_path, mode='r', newline='', encoding='utf-8-sig') as csv_file:
            reader = csv.DictReader(csv_file)

            if not reader.fieldnames:
                raise ValueError(_tr('CSV file has no header.'))

            fieldnames = [name.strip().lower() for name in reader.fieldnames]
            has_required_columns = 'longitude' in fieldnames and 'latitude' in fieldnames
            if not has_required_columns:
                raise ValueError(_tr('Header must contain longitude and latitude columns.'))

            longitude_key = reader.fieldnames[fieldnames.index('longitude')]
            latitude_key = reader.fieldnames[fieldnames.index('latitude')]

            for row in reader:
                try:
                    longitude = parse_decimal(str(row.get(longitude_key, '')).strip())
                    latitude = parse_decimal(str(row.get(latitude_key, '')).strip())
                except (TypeError, ValueError):
                    skipped_count += 1
                    continue

                if latitude < -90 or latitude > 90 or longitude < -180 or longitude > 180:
                    skipped_count += 1
                    continue

                valid_points.append((latitude, longitude))

        return valid_points, skipped_count

    # ------------------------------------------------------------------
    # GPX export
    # ------------------------------------------------------------------

    def portable_waypoint_name(self, index):
        """Return a short waypoint name that works well on handheld GPS units."""
        return 'FG{:03d}'.format(index)

    def write_marks_gpx(self, output_path, coordinates):
        """Write the captured marks as GPS waypoints and an optional ordered route."""
        gpx = ET.Element(
            'gpx',
            attrib={
                'version': '1.1',
                'creator': 'FARM tools QGIS Plugin',
                'xmlns': 'http://www.topografix.com/GPX/1/1',
                'xmlns:xsi': 'http://www.w3.org/2001/XMLSchema-instance',
                'xsi:schemaLocation': (
                    'http://www.topografix.com/GPX/1/1 '
                    'http://www.topografix.com/GPX/1/1/gpx.xsd'
                ),
            },
        )

        metadata = ET.SubElement(gpx, 'metadata')
        ET.SubElement(metadata, 'name').text = 'Field Guide Marks'
        ET.SubElement(metadata, 'desc').text = (
            'Captured marks exported from the FARM tools Field Guide.'
        )

        for index, (longitude, latitude) in enumerate(coordinates, start=1):
            waypoint = ET.SubElement(
                gpx,
                'wpt',
                attrib={
                    'lat': '{:.8f}'.format(latitude),
                    'lon': '{:.8f}'.format(longitude),
                },
            )
            waypoint_name = self.portable_waypoint_name(index)
            ET.SubElement(waypoint, 'name').text = waypoint_name
            ET.SubElement(waypoint, 'cmt').text = 'Field Guide mark {}'.format(index)
            ET.SubElement(
                waypoint,
                'desc',
            ).text = 'Mark {} ({:.8f}, {:.8f})'.format(index, latitude, longitude)
            ET.SubElement(waypoint, 'sym').text = 'Waypoint'
            ET.SubElement(waypoint, 'type').text = 'user'

        if len(coordinates) >= 2:
            route = ET.SubElement(gpx, 'rte')
            ET.SubElement(route, 'name').text = 'Field Guide Route'
            ET.SubElement(route, 'desc').text = (
                'Ordered route built from captured Field Guide marks.'
            )
            for index, (longitude, latitude) in enumerate(coordinates, start=1):
                route_point = ET.SubElement(
                    route,
                    'rtept',
                    attrib={
                        'lat': '{:.8f}'.format(latitude),
                        'lon': '{:.8f}'.format(longitude),
                    },
                )
                ET.SubElement(route_point, 'name').text = self.portable_waypoint_name(index)

        tree = ET.ElementTree(gpx)
        try:
            ET.indent(tree, space='  ')
        except AttributeError:
            pass
        tree.write(output_path, encoding='utf-8', xml_declaration=True)

    # ------------------------------------------------------------------
    # Temporary layer
    # ------------------------------------------------------------------

    def build_temp_marks_layer(self, coordinates):
        """Create a memory point layer holding the captured marks.

        Returns the layer (not yet added to the project) or ``None`` when the
        memory provider could not create it.
        """
        target_crs = self.project.crs()
        if target_crs is None or not target_crs.isValid():
            target_crs = self.wgs84

        layer_name = self._temporary_marks_layer_name()
        layer_uri = 'Point?crs={}'.format(target_crs.authid())
        layer = QgsVectorLayer(layer_uri, layer_name, 'memory')
        if not layer.isValid():
            return None

        provider = layer.dataProvider()
        provider.addAttributes([
            QgsField('order', QVariant.Int),
            QgsField('name', QVariant.String),
            QgsField('longitude', QVariant.Double, 'double', 20, 8),
            QgsField('latitude', QVariant.Double, 'double', 20, 8),
        ])
        layer.updateFields()

        transform = None
        if target_crs.authid() != self.wgs84.authid():
            transform = QgsCoordinateTransform(self.wgs84, target_crs, self.project)

        features = []
        for index, (longitude, latitude) in enumerate(coordinates, start=1):
            point = QgsPointXY(longitude, latitude)
            if transform is not None:
                point = transform.transform(point)

            feature = QgsFeature(layer.fields())
            feature.setGeometry(QgsGeometry.fromPointXY(point))
            feature.setAttributes([
                index,
                self.portable_waypoint_name(index),
                float(longitude),
                float(latitude),
            ])
            features.append(feature)

        provider.addFeatures(features)
        layer.updateExtents()
        return layer

    def _temporary_marks_layer_name(self):
        """Return a readable layer name for temporary project exports."""
        base_name = _tr('Field Guide Marks')
        existing_names = {
            layer.name()
            for layer in self.project.mapLayers().values()
            if hasattr(layer, 'name')
        }
        if base_name not in existing_names:
            return base_name

        suffix = 2
        while True:
            candidate_name = '{} {}'.format(base_name, suffix)
            if candidate_name not in existing_names:
                return candidate_name
            suffix += 1
