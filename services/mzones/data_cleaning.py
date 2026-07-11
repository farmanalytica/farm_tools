# -*- coding: utf-8 -*-
"""Data cleaning for the sampled points DataFrame (pure, no UI)."""
import numpy as np


def limpar_dataframe(df, pd):
    """Coerce variable columns to numeric, drop NoData/sentinels/zero-variance.

    Returns (cleaned_df, n_rows_removed, zero_variance_columns).
    """
    if pd is None or df is None or getattr(df, "empty", True):
        return df, 0, []

    df = df.copy()
    var_cols = [c for c in df.columns if c not in ['X', 'Y', 'valor']]

    for c in var_cols:
        df[c] = pd.to_numeric(df[c], errors='coerce')

    for c in var_cols:
        s = df[c].astype(float)
        s[~np.isfinite(s)] = np.nan
        df[c] = s

    sentinelas = set([-9999, -99999, -32768, 32767, 65535])
    LIM_ABS = 1e19
    for c in var_cols:
        s = df[c].astype(float)
        s[np.isin(s, list(sentinelas))] = np.nan
        s[np.abs(s) > LIM_ABS] = np.nan
        df[c] = s

    n0 = len(df)
    df = df.dropna(subset=var_cols)
    n1 = len(df)

    zero_var_cols = []
    for c in var_cols:
        serie = pd.to_numeric(df[c], errors='coerce')
        if serie.nunique(dropna=True) <= 1:
            zero_var_cols.append(c)
    if zero_var_cols:
        df = df.drop(columns=zero_var_cols, errors='ignore')

    return df, (n0 - n1), zero_var_cols
