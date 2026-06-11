# -*- coding: utf-8 -*-
"""Pure-logic tests for the DEM registry: bbox math, catalog loading, dataset model."""

from unittest.mock import MagicMock

import pytest

from farm_tools.services.dem_registry import (
    check_bbox_intersects,
    get_ee_bbox,
    DEMDataset,
    DEMRegistry,
)


# --------------------------------------------------------------------------- #
# check_bbox_intersects  (a/b = [min_x, min_y, max_x, max_y])
# --------------------------------------------------------------------------- #
class TestBboxIntersects:
    def test_overlapping(self):
        assert check_bbox_intersects([0, 0, 10, 10], [5, 5, 15, 15]) is True

    def test_identical(self):
        assert check_bbox_intersects([0, 0, 1, 1], [0, 0, 1, 1]) is True

    def test_one_contains_other(self):
        assert check_bbox_intersects([0, 0, 10, 10], [2, 2, 3, 3]) is True

    def test_disjoint_on_x(self):
        assert check_bbox_intersects([0, 0, 1, 1], [2, 0, 3, 1]) is False

    def test_disjoint_on_y(self):
        assert check_bbox_intersects([0, 0, 1, 1], [0, 2, 1, 3]) is False

    def test_edge_touching_counts_as_intersect(self):
        # Touching at x==1 is NOT excluded by the strict `<` comparison.
        assert check_bbox_intersects([0, 0, 1, 1], [1, 0, 2, 1]) is True

    def test_symmetric(self):
        a, b = [0, 0, 5, 5], [3, 3, 9, 9]
        assert check_bbox_intersects(a, b) == check_bbox_intersects(b, a)


# --------------------------------------------------------------------------- #
# get_ee_bbox  (non-ee branch: object exposing .geometry().bounds().getInfo())
# --------------------------------------------------------------------------- #
def test_get_ee_bbox_extracts_min_max_from_ring():
    ring = [[-5, -2], [3, -2], [3, 4], [-5, 4], [-5, -2]]
    aoi = MagicMock()
    aoi.geometry.return_value.bounds.return_value.getInfo.return_value = {
        "coordinates": [ring]
    }

    geometry, bbox = get_ee_bbox(aoi)

    assert bbox == (-5, -2, 3, 4)
    assert geometry is aoi.geometry.return_value


# --------------------------------------------------------------------------- #
# DEMDataset model
# --------------------------------------------------------------------------- #
def _dataset_kwargs(**over):
    base = dict(
        name="SRTM",
        collection="USGS/SRTMGL1_003",
        band="elevation",
        resolution=30,
        description="desc",
        is_global=True,
        is_collection=False,
        info="info",
    )
    base.update(over)
    return base


class TestDEMDataset:
    def test_required_fields_assigned(self):
        d = DEMDataset(**_dataset_kwargs())
        assert d.name == "SRTM"
        assert d.band == "elevation"
        assert d.is_collection is False

    def test_optional_coverage_bbox_defaults_none(self):
        assert DEMDataset(**_dataset_kwargs()).coverage_bbox is None

    def test_missing_required_field_raises(self):
        kw = _dataset_kwargs()
        del kw["band"]
        with pytest.raises(KeyError):
            DEMDataset(**kw)


# --------------------------------------------------------------------------- #
# DEMRegistry loads the shipped catalog
# --------------------------------------------------------------------------- #
class TestDEMRegistry:
    def test_catalog_loads_and_is_nonempty(self):
        reg = DEMRegistry()
        datasets = reg.list_datasets()
        assert len(datasets) > 0
        assert all(isinstance(d, DEMDataset) for d in datasets)

    def test_get_dataset_unknown_raises(self):
        reg = DEMRegistry()
        with pytest.raises(ValueError, match="not found"):
            reg.get_dataset("__does_not_exist__")

    def test_every_catalog_entry_round_trips(self):
        reg = DEMRegistry()
        for d in reg.list_datasets():
            assert reg.get_dataset(d.name) is d
