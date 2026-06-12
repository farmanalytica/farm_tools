# -*- coding: utf-8 -*-
"""Export the full analysis to a single workbook. Pure logic, no Qt.

Writes the raw daily data, the annual-trends and thermo-pluviometric tables and
every computed climate index into one ``.xlsx`` (openpyxl). If no Excel engine
is available it falls back to a ``.zip`` of CSVs at the same path.
"""
import os
import zipfile

import pandas as pd


def _safe_sheet(name, used):
    """Excel sheet name: <= 31 chars, unique, no illegal characters."""
    for ch in r"[]:*?/\\":
        name = name.replace(ch, " ")
    name = name.strip()[:31] or "Sheet"
    base, i = name, 1
    while name.lower() in used:
        suffix = f" {i}"
        name = base[:31 - len(suffix)] + suffix
        i += 1
    used.add(name.lower())
    return name


def _tables(climate_data, save_data):
    """Yield (label, DataFrame) pairs to export, skipping empty ones."""
    if climate_data is not None and climate_data.df is not None:
        yield "Raw daily", climate_data.df
    if save_data.get(1) is not None:
        yield "Annual trends", save_data[1]
    if save_data.get(2) is not None:
        yield "Thermo-pluviometric", save_data[2]
    if climate_data is not None:
        for name, idf in climate_data.indices.items():
            yield name, idf


def export(path, climate_data, save_data):
    """Write everything to ``path`` (.xlsx, or .zip of CSVs as fallback).

    Returns the actual path written (the extension may change on fallback).
    """
    tables = list(_tables(climate_data, save_data))
    try:
        with pd.ExcelWriter(path, engine="openpyxl") as writer:
            used = set()
            for label, df in tables:
                df.to_excel(writer, sheet_name=_safe_sheet(label, used),
                            index=not _has_default_index(df))
        return path
    except Exception:
        return _export_zip(path, tables)


def _has_default_index(df):
    return isinstance(df.index, pd.RangeIndex)


def _export_zip(xlsx_path, tables):
    """Fallback: a zip of CSVs (one per table) next to the requested path."""
    zip_path = os.path.splitext(xlsx_path)[0] + ".zip"
    used = set()
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for label, df in tables:
            name = _safe_sheet(label, used)
            zf.writestr(name + ".csv", df.to_csv(index=not _has_default_index(df)))
    return zip_path
