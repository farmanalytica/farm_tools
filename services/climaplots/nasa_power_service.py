# -*- coding: utf-8 -*-
"""NASA POWER data acquisition. Pure logic, no Qt.

Fetches daily climate data (max/min temperature, precipitation, relative
humidity, surface irradiation and 2 m wind speed) from NASA's POWER API for a
point and returns a tidy pandas DataFrame. Two agronomic variables are derived
locally: reference evapotranspiration ET0 (Hargreaves) and growing degree days.
"""
import datetime
import json

import numpy as np
import pandas as pd
import requests

from . import disk_cache

# Daily point-API parameters (incl. WS2M wind speed at 2 m).
_BASE_URL = (
    "https://power.larc.nasa.gov/api/temporal/daily/point?"
    "parameters=T2M_MAX,PRECTOTCORR,T2M_MIN,RH2M,ALLSKY_SFC_SW_DWN,WS2M&community=RE&"
    "longitude={longitude}&latitude={latitude}&"
    "start={start}&end={end}&format=JSON"
)

_COLUMN_RENAME = {
    "index": "Date",
    "PRECTOTCORR": "Precipitation",
    "T2M_MIN": "Min Temperature",
    "T2M_MAX": "Max Temperature",
    "RH2M": "Relative Humidity",
    "ALLSKY_SFC_SW_DWN": "Irradiation",
    "WS2M": "Wind Speed",
}

# NASA POWER daily data starts in 1981.
MIN_YEAR = 1981

# Growing-degree-days base temperature (deg C).
GDD_BASE = 10.0


def last_complete_year():
    """Last calendar year guaranteed to have complete data (previous year)."""
    return datetime.date.today().year - 1


def fetch(longitude, latitude, proxy="", start_year=MIN_YEAR, end_year=None, use_cache=True):
    """Fetch daily climate data for a coordinate and a year range.

    Args:
        longitude / latitude: point coordinates (str or float).
        proxy: optional proxy URL; if it fails the request is retried directly.
        start_year / end_year: inclusive year range (defaults: 1981 -> last
            complete year).

    Returns:
        pandas.DataFrame with a datetime ``Date`` column, the renamed climate
        variables, and derived ``Reference ET0`` and ``Growing Degree Days``.
    """
    if end_year is None:
        end_year = last_complete_year()
    start_year = max(int(start_year), MIN_YEAR)
    end_year = max(int(end_year), start_year)

    cache_file = disk_cache.cache_path("power", round(float(longitude), 4),
                                       round(float(latitude), 4), start_year, end_year)
    if use_cache:
        cached = disk_cache.load(cache_file)
        if cached is not None:
            return cached

    url = _BASE_URL.format(
        longitude=float(longitude), latitude=float(latitude),
        start=f"{start_year}0101", end=f"{end_year}1231",
    )

    proxies = {"http": proxy, "https": proxy} if proxy else None
    response = _request_with_optional_proxy(url, proxies)

    content = json.loads(response.content.decode("utf-8"))
    df = pd.DataFrame.from_dict(content["properties"]["parameter"])
    df = df.reset_index().rename(columns=_COLUMN_RENAME)

    # API uses -999.0 as a fill value.
    df = df.replace(-999.0, np.nan)
    df["Date"] = pd.to_datetime(df["Date"])
    for col in ("Irradiation", "Wind Speed"):
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")

    _add_derived(df, float(latitude))

    if use_cache:
        disk_cache.save(cache_file, df)

    return df


def _add_derived(df, latitude_deg):
    """Add Reference ET0 (Hargreaves) and Growing Degree Days columns in place."""
    tmin = df["Min Temperature"]
    tmax = df["Max Temperature"]
    tmean = (tmin + tmax) / 2.0

    # Growing degree days (base GDD_BASE), clipped at 0.
    df["Growing Degree Days"] = (tmean - GDD_BASE).clip(lower=0)

    # Hargreaves reference ET0 (mm/day):
    #   ET0 = 0.0023 * (Tmean + 17.8) * sqrt(Tmax - Tmin) * Ra
    # with Ra (extraterrestrial radiation) expressed in mm/day.
    doy = df["Date"].dt.dayofyear.to_numpy()
    ra_mm = _extraterrestrial_radiation_mm(latitude_deg, doy)
    temp_range = (tmax - tmin).clip(lower=0).to_numpy()
    et0 = 0.0023 * (tmean.to_numpy() + 17.8) * np.sqrt(temp_range) * ra_mm
    df["Reference ET0"] = np.clip(et0, 0, None)


def _extraterrestrial_radiation_mm(latitude_deg, doy):
    """FAO-56 extraterrestrial radiation Ra for each day-of-year, in mm/day."""
    phi = np.radians(latitude_deg)
    j = doy.astype(float)
    dr = 1 + 0.033 * np.cos(2 * np.pi * j / 365.0)          # inverse rel. distance
    decl = 0.409 * np.sin(2 * np.pi * j / 365.0 - 1.39)     # solar declination
    ws = np.arccos(np.clip(-np.tan(phi) * np.tan(decl), -1, 1))  # sunset hour angle
    gsc = 0.0820  # solar constant MJ m-2 min-1
    ra_mj = (24 * 60 / np.pi) * gsc * dr * (
        ws * np.sin(phi) * np.sin(decl) + np.cos(phi) * np.cos(decl) * np.sin(ws)
    )
    return ra_mj * 0.408  # MJ m-2 day-1 -> mm/day


def _request_with_optional_proxy(url, proxies):
    """GET the URL, trying the proxy first then falling back to a direct call."""
    if proxies:
        try:
            return requests.get(url=url, verify=True, timeout=1000, proxies=proxies)
        except Exception:
            return requests.get(url=url, verify=True, timeout=1000)
    return requests.get(url=url, verify=True, timeout=1000)
