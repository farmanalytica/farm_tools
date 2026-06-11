# -*- coding: utf-8 -*-
"""
Vegetation-index call-composition tests.

These functions wrap Earth Engine; we don't run EE. Instead we pass a MagicMock
``ee.Image`` and assert each function builds the right EE call graph (bands,
expression string, scaling). A regression here (e.g. swapped bands) is a real
science bug, so the assertions are deliberately tight.
"""

import pytest

from farm_tools.tools import indexes


# --------------------------------------------------------------------------- #
# normalizedDifference family — assert the exact band pair + rename("index")
# --------------------------------------------------------------------------- #
NORMALIZED_DIFF = {
    "nvdi": ["B8", "B4"],   # NDVI
    "gndvi": ["B8", "B3"],
    "ndre": ["B8", "B5"],
    "ndmi": ["B8", "B11"],
    "nbr": ["B8", "B12"],
    "ndwi": ["B3", "B8"],
}


@pytest.mark.ee
@pytest.mark.parametrize("fn_name,bands", NORMALIZED_DIFF.items())
def test_normalized_difference_bands(ee_image, fn_name, bands):
    fn = getattr(indexes, fn_name)

    result = fn(ee_image)

    ee_image.normalizedDifference.assert_called_once_with(bands)
    nd = ee_image.normalizedDifference.return_value
    nd.rename.assert_called_once_with("index")
    assert result is nd.rename.return_value


# --------------------------------------------------------------------------- #
# expression-based indices — assert the formula string + scaling
# --------------------------------------------------------------------------- #
@pytest.mark.ee
def test_evi_expression_and_scaling(ee_image):
    indexes.evi(ee_image)

    # NIR/RED/BLUE are scaled by 10000 before the expression.
    assert ee_image.select.call_args_list[0].args == ("B8",)
    args, _ = ee_image.expression.call_args
    expr, bands = args
    assert expr == "2.5 * ((NIR - RED) / (NIR + 6 * RED - 7.5 * BLUE + 1))"
    assert set(bands) == {"NIR", "RED", "BLUE"}
    ee_image.expression.return_value.rename.assert_called_once_with("index")


@pytest.mark.ee
def test_reci_uses_unscaled_bands(ee_image):
    # ReCI selects B8/B5 directly (no .divide(10000)).
    indexes.reci(ee_image)
    expr, bands = ee_image.expression.call_args.args
    assert expr == "(NIR / REDEDGE) - 1"
    assert set(bands) == {"NIR", "REDEDGE"}


# --------------------------------------------------------------------------- #
# registry integrity
# --------------------------------------------------------------------------- #
@pytest.mark.ee
def test_registry_values_are_callable_and_named():
    for name, fn in indexes.INDEX_REGISTRY.items():
        assert callable(fn), f"{name} not callable"


@pytest.mark.ee
def test_registry_functions_return_renamed_index(ee_image):
    for name, fn in indexes.INDEX_REGISTRY.items():
        ee_image.reset_mock()
        fn(ee_image)
        # every index renames its output band to "index"
        renamed = [
            c for m in (ee_image.normalizedDifference, ee_image.expression)
            for c in [m.return_value.rename]
            if m.called
        ]
        assert any(r.call_args and r.call_args.args == ("index",) for r in renamed), (
            f"{name} did not rename output to 'index'"
        )


# --------------------------------------------------------------------------- #
# custom expression
# --------------------------------------------------------------------------- #
@pytest.mark.ee
def test_calc_custom_empty_expression_raises(ee_image):
    with pytest.raises(ValueError):
        indexes.calc_custom(ee_image, "")


@pytest.mark.ee
def test_calc_custom_passes_expression_through(ee_image):
    indexes.calc_custom(ee_image, "B8 / B4")
    expr, bands = ee_image.expression.call_args.args
    assert expr == "B8 / B4"
    # all 12 reflectance bands are exposed to the custom formula
    assert set(bands) == {
        "B1", "B2", "B3", "B4", "B5", "B6",
        "B7", "B8", "B8A", "B9", "B11", "B12",
    }
