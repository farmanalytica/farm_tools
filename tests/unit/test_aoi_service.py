# -*- coding: utf-8 -*-
"""
Pure helpers from the AOI service. The QGIS-coupled conversion methods live in
the qgis tier (tests/qgis/test_aoi_service_qgis.py); here we cover the
geometry-cleaning helper that needs neither QGIS nor EE.
"""

from farm_tools.services import aoi_service

_remove_z = aoi_service._remove_z_dimension


class TestRemoveZDimension:
    def test_single_xyz_point_dropped_to_xy(self):
        assert _remove_z([1.0, 2.0, 99.0]) == [1.0, 2.0]

    def test_xy_point_unchanged(self):
        assert _remove_z([1.0, 2.0]) == [1.0, 2.0]

    def test_polygon_ring(self):
        ring = [[0, 0, 5], [1, 0, 5], [1, 1, 5], [0, 0, 5]]
        assert _remove_z(ring) == [[0, 0], [1, 0], [1, 1], [0, 0]]

    def test_multipolygon_nesting(self):
        mp = [[[[0, 0, 1], [1, 0, 1], [0, 0, 1]]]]
        assert _remove_z(mp) == [[[[0, 0], [1, 0], [0, 0]]]]

    def test_preserves_xy_when_no_z(self):
        ring = [[10.5, -3.2], [10.6, -3.2], [10.5, -3.2]]
        assert _remove_z(ring) == ring
