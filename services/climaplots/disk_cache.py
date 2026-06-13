# -*- coding: utf-8 -*-
"""Tiny on-disk cache for fetched climate series (shared by data sources).

Series are stored as CSV under the OS temp dir, keyed by source + lon/lat/
year-range. Historical data is immutable, so the cache never needs invalidating;
delete the folder to clear it. All operations are best-effort and never raise.
"""
import hashlib
import os
import tempfile

import pandas as pd

CACHE_DIR = os.path.join(tempfile.gettempdir(), "farm_tools_climaplots_cache")


def cache_path(*parts):
    key = "|".join(str(p) for p in parts)
    digest = hashlib.md5(key.encode("utf-8"), usedforsecurity=False).hexdigest()
    return os.path.join(CACHE_DIR, digest + ".csv")


def load(path):
    """Return the cached DataFrame, or None on miss/corruption."""
    if not os.path.isfile(path):
        return None
    try:
        df = pd.read_csv(path)
        if "Date" in df.columns:
            df["Date"] = pd.to_datetime(df["Date"])
        return df
    except Exception:
        return None


def save(path, df):
    """Persist a DataFrame; failures are ignored (caching is best-effort)."""
    try:
        os.makedirs(CACHE_DIR, exist_ok=True)
        df.to_csv(path, index=False)
    except Exception:
        pass
