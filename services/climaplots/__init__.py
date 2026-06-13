# -*- coding: utf-8 -*-
"""ClimaPlots service layer: pure computation, free of Qt widgets.

Modules:
    nasa_power_service  - NASA POWER data fetch
    openmeteo_service   - Open-Meteo (ERA5) data fetch
    indices_service     - ETCCDI climate indices + SPI (needs extlibs climdex)
    stats_service       - Mann-Kendall / Pettitt title fragments (needs extlibs)
    plot_service        - plotly figure builders (returns PlotResult)
    orchestrator        - sequences fetch + indices into one ClimateData
    export_service      - xlsx / zip-of-CSV workbook export
    disk_cache          - on-disk CSV cache for fetched series
    types               - ClimateData / PlotResult dataclasses

IMPORTANT: no eager submodule imports here. ``indices_service``,
``stats_service`` and ``orchestrator`` depend on extlibs packages (climdex,
pymannkendall, pyhomogeneity) that may not be provisioned yet; callers import
them lazily so the rest of the plugin loads regardless.
"""
