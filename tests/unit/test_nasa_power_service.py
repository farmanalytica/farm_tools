# -*- coding: utf-8 -*-
"""
NASA POWER service tests. Network is mocked at ``requests.get``; we verify URL
construction, the -999 fill -> NaN conversion, date parsing/sorting, proxy
fallback, and the monthly precipitation roll-up.
"""

import json
from unittest.mock import MagicMock

import numpy as np
import pandas as pd
import pytest

from farm_tools.services.nasa_power_service import NasaPowerService

MODULE = "farm_tools.services.nasa_power_service"


def _fake_response(parameter_dict, ok=True, status=200):
    resp = MagicMock()
    resp.ok = ok
    resp.status_code = status
    resp.reason = "OK" if ok else "Server Error"
    payload = {"properties": {"parameter": parameter_dict}}
    resp.content = json.dumps(payload).encode("utf-8")
    return resp


@pytest.fixture
def sample_params():
    return {
        "PRECTOTCORR": {"20240102": 5.0, "20240101": 0.0, "20240103": -999.0},
        "T2M_MIN": {"20240101": 18.0, "20240102": 19.0, "20240103": 17.0},
        "T2M_MAX": {"20240101": 30.0, "20240102": 31.0, "20240103": -999.0},
    }


class TestFetchDaily:
    def test_builds_url_with_compacted_dates(self, mocker, sample_params):
        get = mocker.patch(f"{MODULE}.requests.get",
                           return_value=_fake_response(sample_params))

        NasaPowerService.fetch_daily(-47.9, -15.8, "2024-01-01", "2024-01-03")

        url = get.call_args.kwargs["url"]
        assert "start=20240101" in url and "end=20240103" in url
        assert "longitude=-47.9" in url and "latitude=-15.8" in url

    def test_fill_value_becomes_nan(self, mocker, sample_params):
        mocker.patch(f"{MODULE}.requests.get",
                     return_value=_fake_response(sample_params))

        df = NasaPowerService.fetch_daily(0, 0, "2024-01-01", "2024-01-03")

        assert np.isnan(df.loc[df["Date"] == "2024-01-03", "Precipitation"].iloc[0])

    def test_rows_sorted_by_date(self, mocker, sample_params):
        mocker.patch(f"{MODULE}.requests.get",
                     return_value=_fake_response(sample_params))

        df = NasaPowerService.fetch_daily(0, 0, "2024-01-01", "2024-01-03")

        assert list(df["Date"]) == sorted(df["Date"])
        assert set(df.columns) == {
            "Date", "Precipitation", "Min Temperature", "Max Temperature"
        }

    def test_http_error_raises(self, mocker):
        mocker.patch(f"{MODULE}.requests.get",
                     return_value=_fake_response({}, ok=False, status=503))
        with pytest.raises(RuntimeError, match="HTTP 503"):
            NasaPowerService.fetch_daily(0, 0, "2024-01-01", "2024-01-03")

    def test_empty_parameter_block_raises(self, mocker):
        mocker.patch(f"{MODULE}.requests.get",
                     return_value=_fake_response({}))
        with pytest.raises(RuntimeError, match="no data"):
            NasaPowerService.fetch_daily(0, 0, "2024-01-01", "2024-01-03")

    def test_proxy_failure_falls_back_to_direct(self, mocker, sample_params):
        good = _fake_response(sample_params)
        get = mocker.patch(
            f"{MODULE}.requests.get",
            side_effect=[ConnectionError("proxy down"), good],
        )

        df = NasaPowerService.fetch_daily(
            0, 0, "2024-01-01", "2024-01-03", proxy="http://proxy:8080"
        )

        assert len(df) == 3
        assert get.call_count == 2  # proxied attempt, then direct
        assert "proxies" not in get.call_args.kwargs  # second call is direct


class TestMonthlyPrecipitation:
    def test_accumulates_per_month(self):
        df = pd.DataFrame({
            "Date": pd.to_datetime(
                ["2024-01-05", "2024-01-20", "2024-02-10"]),
            "Precipitation": [3.0, 7.0, 4.0],
        })
        months, values = NasaPowerService.monthly_precipitation(df)
        assert values == [10.0, 4.0]
        assert [m.month for m in months] == [1, 2]

    def test_empty_df_returns_empty_lists(self):
        assert NasaPowerService.monthly_precipitation(pd.DataFrame()) == ([], [])

    def test_none_returns_empty_lists(self):
        assert NasaPowerService.monthly_precipitation(None) == ([], [])

    def test_all_nan_month_dropped(self):
        df = pd.DataFrame({
            "Date": pd.to_datetime(["2024-01-05", "2024-01-20"]),
            "Precipitation": [np.nan, np.nan],
        })
        assert NasaPowerService.monthly_precipitation(df) == ([], [])
