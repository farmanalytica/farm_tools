# -*- coding: utf-8 -*-
"""
Pure numpy helpers from the raster analysis module: morphological opening,
mean smoothing, masked maximum search, and pixel-to-world conversion. The
QGIS-coupled block reading and polygon rasterization need a real raster
provider and live in the qgis tier.
"""

import numpy as np
import pytest

from farm_tools.services import raster_analysis


class _FakeExtent:
    """Stands in for QgsRectangle in pixel/world conversions."""

    def __init__(self, x_min, y_min, x_max, y_max):
        self._x_min = x_min
        self._y_min = y_min
        self._x_max = x_max
        self._y_max = y_max

    def xMinimum(self):
        return self._x_min

    def yMaximum(self):
        return self._y_max

    def width(self):
        return self._x_max - self._x_min

    def height(self):
        return self._y_max - self._y_min


class TestShifted:
    def test_zero_shift_is_identity(self):
        arr = np.arange(9.0).reshape(3, 3)
        assert np.array_equal(raster_analysis._shifted(arr, 0, 0, 0.0), arr)

    def test_shift_down_right_fills_border(self):
        arr = np.ones((2, 2))
        out = raster_analysis._shifted(arr, 1, 1, 0.0)
        assert out[0, 0] == 0.0
        assert out[1, 1] == 1.0

    def test_shift_larger_than_array_is_all_fill(self):
        arr = np.ones((2, 2), dtype=bool)
        out = raster_analysis._shifted(arr, 3, 0, False)
        assert not out.any()


class TestBinaryOpening:
    def test_single_pixel_noise_removed(self):
        mask = np.zeros((7, 7), dtype=bool)
        mask[1, 1] = True          # lone pixel: erosion kills it
        mask[3:6, 3:6] = True      # solid 3x3 block survives
        opened = raster_analysis.binary_opening_3x3(mask)
        assert not opened[1, 1]
        assert opened[4, 4]

    def test_mask_too_small_for_erosion_returns_original(self):
        mask = np.zeros((5, 5), dtype=bool)
        mask[2, 2] = True
        opened = raster_analysis.binary_opening_3x3(mask)
        # Erosion empties the mask; the original is kept as fallback.
        assert np.array_equal(opened, mask)


class TestSmoothMean:
    def test_uniform_values_unchanged(self):
        values = np.full((5, 5), 7.0)
        valid = np.ones((5, 5), dtype=bool)
        smoothed = raster_analysis.smooth_mean_3x3(values, valid)
        assert np.allclose(smoothed, 7.0)

    def test_invalid_neighbors_excluded(self):
        values = np.zeros((3, 3))
        values[1, 1] = 9.0
        valid = np.zeros((3, 3), dtype=bool)
        valid[1, 1] = True
        smoothed = raster_analysis.smooth_mean_3x3(values, valid)
        # Only the center is valid, so its window average is itself.
        assert smoothed[1, 1] == 9.0

    def test_all_invalid_gives_nan(self):
        values = np.ones((3, 3))
        valid = np.zeros((3, 3), dtype=bool)
        smoothed = raster_analysis.smooth_mean_3x3(values, valid)
        assert np.isnan(smoothed).all()


class TestFindMaximum:
    def test_empty_mask_returns_none(self):
        values = np.ones((4, 4))
        mask = np.zeros((4, 4), dtype=bool)
        assert raster_analysis.find_maximum_in_masked_array(values, mask) is None

    def test_finds_broad_peak(self):
        values = np.zeros((9, 9))
        values[4:7, 4:7] = 10.0
        mask = np.ones((9, 9), dtype=bool)
        row, col = raster_analysis.find_maximum_in_masked_array(values, mask)
        assert 4 <= row <= 6
        assert 4 <= col <= 6

    def test_broad_peak_beats_single_pixel_spike(self):
        values = np.zeros((9, 9))
        values[1, 1] = 100.0       # isolated spike (smoothed away)
        values[5:8, 5:8] = 50.0    # broad plateau
        mask = np.ones((9, 9), dtype=bool)
        row, col = raster_analysis.find_maximum_in_masked_array(values, mask)
        assert 5 <= row <= 7
        assert 5 <= col <= 7

    def test_single_valid_pixel_found(self):
        values = np.zeros((5, 5))
        values[2, 3] = 4.0
        mask = np.zeros((5, 5), dtype=bool)
        mask[2, 3] = True
        assert raster_analysis.find_maximum_in_masked_array(values, mask) == (2, 3)

    def test_deterministic_for_same_input(self):
        rng = np.random.RandomState(42)
        values = rng.rand(20, 20)
        mask = np.ones((20, 20), dtype=bool)
        first = raster_analysis.find_maximum_in_masked_array(values, mask)
        second = raster_analysis.find_maximum_in_masked_array(values.copy(), mask.copy())
        assert first == second


class TestPixelToWorld:
    def test_pixel_centers(self):
        extent = _FakeExtent(0.0, 0.0, 10.0, 10.0)
        x, y = raster_analysis.pixel_to_world_coordinates(0, 0, extent, 10, 10)
        assert x == pytest.approx(0.5)
        assert y == pytest.approx(9.5)

        x, y = raster_analysis.pixel_to_world_coordinates(9, 9, extent, 10, 10)
        assert x == pytest.approx(9.5)
        assert y == pytest.approx(0.5)

    def test_non_square_pixels(self):
        extent = _FakeExtent(100.0, 200.0, 110.0, 204.0)
        x, y = raster_analysis.pixel_to_world_coordinates(1, 2, extent, 5, 4)
        assert x == pytest.approx(100.0 + 2.5 * 2.0)
        assert y == pytest.approx(204.0 - 1.5 * 1.0)
