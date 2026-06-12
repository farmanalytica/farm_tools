# -*- coding: utf-8 -*-
"""Open-Meteo (ERA5 reanalysis) data acquisition. Pure logic, no Qt.

A free, key-less alternative to NASA POWER, backed by the ERA5/ERA5-Land
reanalysis (daily, global, from 1940). Returns the SAME DataFrame schema as
``nasa_power_service`` so the rest of the plugin is source-agnostic. Reference
evapotranspiration (ET0, FAO-56) is provided directly by the API; growing
degree days are derived locally.
"""
import datetime

import pandas as pd
import requests

from . import disk_cache

_URL = "https://archive-api.open-meteo.com/v1/archive"

# Open-Meteo daily variable -> ClimaPlots column.
_DAILY = {
    "temperature_2m_max": "Max Temperature",
    "temperature_2m_min": "Min Temperature",
    "precipitation_sum": "Precipitation",
    "relative_humidity_2m_mean": "Relative Humidity",
    "shortwave_radiation_sum": "Irradiation",        # MJ/m2/day -> kWh/m2/day below
    "wind_speed_10m_mean": "Wind Speed",             # m/s (wind_speed_unit=ms)
    "et0_fao_evapotranspiration": "Reference ET0",   # mm/day
}

MIN_YEAR = 1940  # ERA5 starts in 1940
GDD_BASE = 10.0


def last_complete_year():
    return datetime.date.today().year - 1


def fetch(longitude, latitude, proxy="", start_year=MIN_YEAR, end_year=None, use_cache=True):
    """Fetch daily ERA5 data for a coordinate and year range (see schema above)."""
    if end_year is None:
        end_year = last_complete_year()
    start_year = max(int(start_year), MIN_YEAR)
    end_year = max(int(end_year), start_year)

    cache_file = disk_cache.cache_path("openmeteo", round(float(longitude), 4),
                                       round(float(latitude), 4), start_year, end_year)
    if use_cache:
        cached = disk_cache.load(cache_file)
        if cached is not None:
            return cached

    params = {
        "latitude": float(latitude),
        "longitude": float(longitude),
        "start_date": f"{start_year}-01-01",
        "end_date": f"{end_year}-12-31",
        "daily": ",".join(_DAILY.keys()),
        "timezone": "GMT",
        "wind_speed_unit": "ms",
    }
    proxies = {"http": proxy, "https": proxy} if proxy else None
    response = _request(params, proxies)
    daily = response.json()["daily"]

    df = pd.DataFrame({"Date": pd.to_datetime(daily["time"])})
    for api_name, col in _DAILY.items():
        df[col] = pd.to_numeric(pd.Series(daily.get(api_name)), errors="coerce")

    # Open-Meteo gives daily shortwave as MJ/m2; NASA POWER uses kWh/m2/day.
    if "Irradiation" in df.columns:
        df["Irradiation"] = df["Irradiation"] / 3.6

    tmean = (df["Min Temperature"] + df["Max Temperature"]) / 2.0
    df["Growing Degree Days"] = (tmean - GDD_BASE).clip(lower=0)

    if use_cache:
        disk_cache.save(cache_file, df)
    return df


def _request(params, proxies):
    """GET the archive endpoint, trying the proxy first then directly."""
    if proxies:
        try:
            return requests.get(_URL, params=params, timeout=1000, proxies=proxies, verify=True)
        except Exception:
            return requests.get(_URL, params=params, timeout=1000, verify=True)
    return requests.get(_URL, params=params, timeout=1000, verify=True)
