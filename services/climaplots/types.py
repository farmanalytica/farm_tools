# -*- coding: utf-8 -*-
"""Typed boundary objects passed between the services, worker and UI layers.

These dataclasses are the public contract between the pure-computation services
and the Qt UI / worker code. Keeping the contract explicit lets the dialog stay
free of pandas/xarray details and lets the background worker hand a single typed
object back to the GUI thread.
"""
from dataclasses import dataclass, field
from typing import Dict

import pandas as pd


@dataclass
class ClimateData:
    """Result of the heavy analysis pipeline (data fetch + climate indices).

    Attributes:
        df: Raw daily climate dataframe (Date + variables).
        indices: Mapping of climate-index name -> computed DataFrame. One entry
            per index that computed successfully (failures are skipped).
        longitude/latitude: The queried point, echoed back for plot titles.
    """
    df: pd.DataFrame
    indices: Dict[str, pd.DataFrame] = field(default_factory=dict)
    longitude: str = ""
    latitude: str = ""
    # Optional comparison point B (annual-trends overlay only). df_b is the raw
    # daily dataframe for B; indices are not computed for the comparison point.
    df_b: object = None
    longitude_b: str = ""
    latitude_b: str = ""
    # Data-source keys ("power" / "openmeteo") used for A and B (for legends).
    source: str = "power"
    source_b: str = ""


@dataclass
class PlotResult:
    """A built figure plus the tabular data behind it (for CSV export).

    Attributes:
        figure: A plotly ``graph_objects.Figure`` ready to render.
        data: The DataFrame used to build the figure, stored for "save CSV".
    """
    figure: object
    data: pd.DataFrame
