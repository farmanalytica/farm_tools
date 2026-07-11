# -*- coding: utf-8 -*-
"""Pure-logic coverage for management-zone raster grid helpers."""

import math

import pytest

from farm_tools.services.mzones.raster_io import compute_grid, xy_to_rowcol


class _Extent:
    def __init__(self, x_min, x_max, y_min, y_max):
        self._x_min = x_min
        self._x_max = x_max
        self._y_min = y_min
        self._y_max = y_max

    def xMinimum(self):
        return self._x_min

    def xMaximum(self):
        return self._x_max

    def yMinimum(self):
        return self._y_min

    def yMaximum(self):
        return self._y_max


def test_compute_grid_rejects_nan_extent_with_clear_error():
    extent = _Extent(math.nan, 10.0, 0.0, 10.0)

    with pytest.raises(ValueError, match="Boundary extent is invalid"):
        compute_grid(extent, 2.0)


def test_compute_grid_rejects_zero_area_extent():
    extent = _Extent(10.0, 10.0, 0.0, 10.0)

    with pytest.raises(ValueError, match="zero area"):
        compute_grid(extent, 2.0)


def test_xy_to_rowcol_returns_none_for_nan_coordinates():
    gt = (0.0, 2.0, 0.0, 10.0, 0.0, -2.0)

    assert xy_to_rowcol(gt, math.nan, 4.0) is None
    assert xy_to_rowcol(gt, 4.0, math.nan) is None

