# -*- coding: utf-8 -*-
"""ETCCDI climate-index computation. Pure logic, no Qt.

Computes temperature and precipitation indices with the climdex library plus a
Standardized Precipitation Index (SPI). Each index is computed independently so
one failure never stops the others; failures are reported through an optional
``warn`` callback.
"""
import climdex.precipitation as pdex
import climdex.temperature as tdex
from scipy.stats import gamma, norm


def _noop(_msg):
    pass


def compute(df, warn=_noop):
    """Compute all climate indices for a raw daily climate dataframe.

    Args:
        df: daily dataframe with Date / Precipitation / Min Temperature /
            Max Temperature columns.
        warn: callable(str) invoked with a human-readable message whenever an
            individual index fails to compute.

    Returns:
        dict mapping index display-name -> single-column DataFrame.
    """
    df = df.copy()
    df_aux = df.copy()

    df.set_index("Date", inplace=True)
    ds = df[["Precipitation", "Max Temperature", "Min Temperature"]].copy().to_xarray()

    precip_indices = pdex.indices(time_dim="Date")
    temp_indices = tdex.indices(time_dim="Date")

    results = {}

    def _try(name, fn):
        try:
            results[name] = fn()
        except Exception as e:  # noqa: BLE001 - per-index isolation
            warn(f"Failed to compute {name}: {e}")

    def _annual(method, varname, name):
        def build():
            out = method(ds, varname=varname).to_dataframe()
            out.columns = [name]
            return out
        _try(name, build)

    def _monthly(method, varname, name):
        def build():
            out = method(ds, varname=varname).to_dataframe()[[varname]]
            out.columns = [name]
            return out
        _try(name, build)

    # --- Temperature indices ------------------------------------------------
    _annual(temp_indices.annual_frost_days, "Min Temperature", "Annual Frost Days")
    _annual(temp_indices.annual_tropical_nights, "Min Temperature", "Annual Tropical Nights")
    _annual(temp_indices.annual_icing_days, "Max Temperature", "Annual Icing Days")
    _annual(temp_indices.annual_summer_days, "Max Temperature", "Annual Summer Days")
    _monthly(temp_indices.monthly_txx, "Max Temperature", "Monthly Maximum Temperature")
    _monthly(temp_indices.monthly_txn, "Max Temperature", "Monthly Minimum Temperature of Maximum Temperatures")
    _monthly(temp_indices.monthly_tnx, "Min Temperature", "Monthly Maximum Temperature of Minimum Temperatures")
    _monthly(temp_indices.monthly_tnn, "Min Temperature", "Monthly Minimum Temperature")

    def _dtr():
        out = temp_indices.daily_temperature_range(
            ds, ds, min_varname="Min Temperature", max_varname="Max Temperature"
        ).to_dataframe(name="DTR")
        out.columns = ["Daily Temperature Range"]
        return out
    _try("Daily Temperature Range", _dtr)

    # --- Precipitation indices ----------------------------------------------
    _annual(precip_indices.monthly_rx1day, "Precipitation", "Monthly Maximum 1-day Precipitation")
    _annual(precip_indices.monthly_rx5day, "Precipitation", "Monthly Maximum 5-day Precipitation")
    _annual(precip_indices.annual_r10mm, "Precipitation", "Annual Count of Days when Precipitation Exceeds 10mm")
    _annual(precip_indices.annual_r20mm, "Precipitation", "Annual Count of Days when Precipitation Exceeds 20mm")

    def _period(method, name):
        def build():
            out = method(ds, period="ME", varname="Precipitation").to_dataframe()
            out.columns = [name]
            return out
        _try(name, build)

    _period(precip_indices.sdii, "Simple Precipitation Intensity Index")
    _period(precip_indices.cdd, "Number of Consecutive Dry Days in a Month")
    _period(precip_indices.cwd, "Number of Consecutive Wet Days in a Month")

    # --- Standardized Precipitation Index (90-day, gamma fit) ---------------
    def _spi():
        df_aux["Accumulated_Precipitation"] = df_aux["Precipitation"].rolling(window=90).sum()
        df_aux.dropna(inplace=True)
        params = gamma.fit(df_aux["Accumulated_Precipitation"], floc=0)
        df_aux["Cumulative_Probability"] = gamma.cdf(df_aux["Accumulated_Precipitation"], *params)
        df_aux["SPI"] = norm.ppf(df_aux["Cumulative_Probability"])
        out = df_aux[["SPI"]].copy()
        out.columns = ["The Standardized Precipitation Index (SPI)"]
        return out
    _try("The Standardized Precipitation Index (SPI)", _spi)

    return results
