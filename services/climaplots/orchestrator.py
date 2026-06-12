# -*- coding: utf-8 -*-
"""Facade that sequences the heavy analysis pipeline. Pure logic, no Qt.

This is the single entry point the background worker calls: fetch the raw daily
data from the selected source, compute the climate indices, and return one
typed :class:`ClimateData` object. Cheap figure building is done separately on
the GUI thread via :mod:`plot_service`.
"""
from . import indices_service, nasa_power_service, openmeteo_service
from .types import ClimateData

# Available data sources (key -> fetcher module with a matching fetch()).
SOURCES = {
    "power": nasa_power_service,
    "openmeteo": openmeteo_service,
}


def run_analysis(longitude, latitude, proxy="", warn=None, start_year=None, end_year=None,
                 longitude_b=None, latitude_b=None, source="power", source_b=None):
    """Fetch climate data and compute indices for a coordinate.

    Args:
        longitude / latitude: queried point.
        proxy: optional proxy URL.
        warn: optional callable(str) for per-index failure messages.
        start_year / end_year: inclusive year range (None -> service defaults).
        longitude_b / latitude_b: optional comparison point (trends overlay).
        source: data-source key ("power" or "openmeteo").

    Returns:
        ClimateData with the raw dataframe and the computed indices.
    """
    fetcher = SOURCES.get(source, nasa_power_service)
    sy = start_year or fetcher.MIN_YEAR
    df = fetcher.fetch(longitude, latitude, proxy, start_year=sy, end_year=end_year)
    indices = indices_service.compute(df, warn=warn or (lambda _m: None))

    df_b = None
    used_source_b = ""
    if longitude_b not in (None, "") and latitude_b not in (None, ""):
        # Comparison point: raw series only (no indices), for the trends overlay.
        # B may use its own source (None -> same as A) for source comparison.
        used_source_b = source_b or source
        fetcher_b = SOURCES.get(used_source_b, fetcher)
        sy_b = start_year or fetcher_b.MIN_YEAR
        df_b = fetcher_b.fetch(longitude_b, latitude_b, proxy, start_year=sy_b, end_year=end_year)

    return ClimateData(
        df=df, indices=indices, longitude=str(longitude), latitude=str(latitude),
        df_b=df_b, longitude_b=str(longitude_b or ""), latitude_b=str(latitude_b or ""),
        source=source, source_b=used_source_b,
    )
