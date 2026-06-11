# -*- coding: utf-8 -*-
"""
NASA POWER climate acquisition for the optical time-series overlay.

Fetches daily precipitation and min/max temperature from NASA's POWER point API
for a coordinate over the same date range as the Sentinel-2 series, and returns
a tidy pandas DataFrame. Pure logic, no Qt.
"""

import json

import numpy as np
import pandas as pd
import requests


# Daily point-API parameters: corrected precipitation + 2 m min/max temperature.
_BASE_URL = (
    "https://power.larc.nasa.gov/api/temporal/daily/point?"
    "parameters=PRECTOTCORR,T2M_MIN,T2M_MAX&community=AG&"
    "longitude={longitude}&latitude={latitude}&"
    "start={start}&end={end}&format=JSON"
)

_COLUMN_RENAME = {
    "index": "Date",
    "PRECTOTCORR": "Precipitation",
    "T2M_MIN": "Min Temperature",
    "T2M_MAX": "Max Temperature",
}


class NasaPowerService:
    """Fetches daily NASA POWER climate data for a point and date range."""

    @staticmethod
    def fetch_daily(longitude, latitude, start_date, end_date, proxy=""):
        """Fetch daily climate data for ``[start_date, end_date]`` (YYYY-MM-DD).

        Args:
            longitude / latitude: point coordinates (str or float).
            start_date / end_date: inclusive ISO dates (``YYYY-MM-DD``).
            proxy: optional proxy URL; if it fails the request retries directly.

        Returns:
            pandas.DataFrame with a datetime ``Date`` column plus
            ``Precipitation``, ``Min Temperature`` and ``Max Temperature``.
        """
        start = start_date.replace("-", "")
        end = end_date.replace("-", "")
        url = _BASE_URL.format(
            longitude=float(longitude), latitude=float(latitude),
            start=start, end=end,
        )

        proxies = {"http": proxy, "https": proxy} if proxy else None
        response = NasaPowerService._request_with_optional_proxy(url, proxies)
        if not response.ok:
            raise RuntimeError(
                f"NASA POWER request failed (HTTP {response.status_code}): "
                f"{response.reason}"
            )

        content = json.loads(response.content.decode("utf-8"))
        parameters = content.get("properties", {}).get("parameter", {})
        if not parameters:
            raise RuntimeError("NASA POWER returned no data for this point/range.")

        df = pd.DataFrame.from_dict(parameters)
        df = df.reset_index().rename(columns=_COLUMN_RENAME)
        # API uses -999.0 as a fill value.
        df = df.replace(-999.0, np.nan)
        df["Date"] = pd.to_datetime(df["Date"], format="%Y%m%d")
        return df.sort_values("Date").reset_index(drop=True)

    @staticmethod
    def monthly_precipitation(df):
        """Accumulated precipitation per calendar month.

        Returns ``(month_start_datetimes, accumulated_mm)`` as parallel lists;
        months with no valid daily data are dropped.
        """
        if df is None or df.empty or "Precipitation" not in df.columns:
            return [], []
        series = (
            df.set_index("Date")["Precipitation"]
            .resample("MS")
            .sum(min_count=1)
            .dropna()
        )
        months = list(series.index)
        values = [float(v) for v in series.values]
        return months, values

    @staticmethod
    def _request_with_optional_proxy(url, proxies):
        """GET the URL, trying the proxy first then falling back to direct."""
        if proxies:
            try:
                return requests.get(url=url, verify=True, timeout=120, proxies=proxies)
            except Exception:
                return requests.get(url=url, verify=True, timeout=120)
        return requests.get(url=url, verify=True, timeout=120)
