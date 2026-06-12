# -*- coding: utf-8 -*-
"""Trend / homogeneity statistics. Pure logic, no Qt.

Wraps the Mann-Kendall trend test and the Pettitt homogeneity test and formats
their results into the HTML title fragments shown above the plots.
"""
import pymannkendall as mk
import pyhomogeneity as hg


def mann_kendall_title(series):
    """Return the Mann-Kendall title fragment for a single-column series/frame."""
    result = mk.original_test(series)
    return (
        f"Mann Kendall Test: <b>{result.trend}</b>, alpha=0.05, "
        f"p-value={round(result.p, 4)}"
    )


def pettitt_title(series, index=None):
    """Return the Pettitt homogeneity title fragment.

    Args:
        series: single-column DataFrame/Series to test.
        index: optional index used to label the change-point location.
    """
    result = hg.pettitt_test(series)
    if not result.h:
        return (
            f"Pettitt Test: data is <b>homogeneous</b>, "
            f"alpha=0.05, p-value={round(result.p, 4)}"
        )

    cp_label = _format_cp_label(result.cp, index)
    return (
        f"Pettitt Test: data is <b>nonhomogeneous</b>, "
        f"probable change point location={cp_label}, "
        f"alpha=0.05, p-value={round(result.p, 4)}"
    )


def stats_title(series, index=None):
    """Combined Mann-Kendall + Pettitt title, each failure isolated."""
    try:
        title1 = mann_kendall_title(series)
    except Exception as e:  # noqa: BLE001 - surface as title text, never crash plot
        title1 = f"Mann Kendall Test failed: {e}"
    try:
        title2 = pettitt_title(series, index)
    except Exception as e:  # noqa: BLE001
        title2 = f"Pettitt Test failed: {e}"
    return title1 + "<br>" + title2


def _format_cp_label(cp, index):
    """Resolve the change-point index position to its label when possible."""
    if index is not None and type(index).__name__ == "Index":
        try:
            return index[cp]
        except Exception:
            return cp
    return str(cp)[:4]
