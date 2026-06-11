# -*- coding: utf-8 -*-
"""
SAR timeseries chart renderer for the RAVI plugin.

A single ``render_chart_html`` builds a self-contained page (plotly.js embedded
inline) used for BOTH the in-plugin QWebView and the "open in browser" action,
so the chart is byte-for-byte identical in both. Load it from a ``file://`` URL.
"""

import json
import os

import plotly.express as px


_PLOTLY_JS_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "assets",
    "plotly-1.58.5.min.js",
)
_plotly_js_cache = None


def _plotly_js():
    global _plotly_js_cache
    if _plotly_js_cache is None:
        with open(_PLOTLY_JS_PATH, "r", encoding="utf-8") as f:
            _plotly_js_cache = f.read()
    return _plotly_js_cache


def _build_figure(dataframe, title="VV/VH Ratio Mean Time Series", ylabel="VV/VH Ratio Mean"):
    """Build the spectral-index time-series figure."""
    fig = px.line(
        dataframe,
        x="dates",
        y="AOI_average",
        markers=True,
        title=title,
    )
    fig.update_layout(
        xaxis_title="Date",
        yaxis_title=ylabel,
        yaxis=dict(tickformat=".3f"),
        margin=dict(l=80, r=20, t=40, b=40),
    )
    return fig


def render_chart_html(dataframe, hide_toolbar=True, title="VV/VH Ratio Mean Time Series", ylabel="VV/VH Ratio Mean", smooth_y=None, smooth_label="Smoothed", precip_bars=None):
    """Return a self-contained page that renders the figure with the vendored
    plotly.js v1.58 (QtWebKit-compatible), fed the figure JSON via Plotly.newPlot.

    Args:
        dataframe: The time-series data to plot.
        hide_toolbar: If True, hide toolbar buttons (for in-plugin view).
                     If False, show toolbar (for browser export).
                     Defaults to True for in-plugin use.
        title: Chart title (default: "VV/VH Ratio Mean Time Series").
        ylabel: Y-axis label (default: "VV/VH Ratio Mean").
        smooth_y: Optional list of smoothed y-values aligned with the
                 dataframe rows. When given, a second line trace is overlaid
                 and the raw trace is relabelled so the legend distinguishes
                 them.
        smooth_label: Legend name for the smoothed overlay.
        precip_bars: Optional dict ``{"x": [...], "y": [...], "name": str,
                 "ylabel": str}`` drawn as a bar series on a secondary
                 right-hand y-axis (e.g. accumulated monthly precipitation).
                 Bars sit behind the index line.

    The default v6 template is dropped so the JSON stays within what the old
    engine understands. Intended to be written to a temp file and loaded from a
    ``file://`` URL.
    """
    fig = _build_figure(dataframe, title=title, ylabel=ylabel)
    fig.update_layout(template="none")
    fig_dict = fig.to_dict()
    dates = dataframe["dates"].tolist()
    raw = dataframe["AOI_average"].tolist()
    if smooth_y is not None:
        triples = sorted(zip(dates, raw, smooth_y), key=lambda p: p[0])
        x = [p[0] for p in triples]
        y = [float(p[1]) for p in triples]
        sy = [float(p[2]) for p in triples]
    else:
        pairs = sorted(zip(dates, raw), key=lambda p: p[0])
        x = [p[0] for p in pairs]
        y = [float(p[1]) for p in pairs]
        sy = None
    for trace in fig_dict.get("data", []):
        trace["x"] = x
        trace["y"] = y
    if sy is not None:
        if fig_dict.get("data"):
            fig_dict["data"][0]["name"] = "Observed"
            fig_dict["data"][0]["showlegend"] = True
        fig_dict.setdefault("data", []).append({
            "type": "scatter",
            "mode": "lines",
            "name": smooth_label,
            "x": x,
            "y": sy,
            "line": {"color": "#d98f00", "width": 2},
        })
        fig_dict.setdefault("layout", {})["showlegend"] = True
    if precip_bars and precip_bars.get("x"):
        # Bar series on a secondary right axis. Inserted at the front so it
        # draws behind the index line/markers (later traces render on top).
        bar_trace = {
            "type": "bar",
            "name": precip_bars.get("name", "Precipitation"),
            "x": list(precip_bars["x"]),
            "y": [float(v) for v in precip_bars["y"]],
            "yaxis": "y2",
            "marker": {"color": "rgba(42, 93, 132, 0.45)"},
        }
        fig_dict.setdefault("data", []).insert(0, bar_trace)
        layout = fig_dict.setdefault("layout", {})
        layout["showlegend"] = True
        layout["yaxis2"] = {
            "title": precip_bars.get("ylabel", "Precipitation (mm)"),
            "overlaying": "y",
            "side": "right",
            "showgrid": False,
            "rangemode": "tozero",
        }
        # Keep the index line on the primary axis (explicit after the insert).
        for trace in fig_dict["data"]:
            if trace.get("type") != "bar" and "yaxis" not in trace:
                trace["yaxis"] = "y"
    fig_json = json.dumps(fig_dict)

    config = {
        "displaylogo": False,
        "responsive": True,
    }

    if hide_toolbar:
        config["modeBarButtonsToRemove"] = [
            "toImage",
            "sendDataToCloud",
            "zoom2d",
            "pan2d",
            "select2d",
            "lasso2d",
            "zoomIn2d",
            "zoomOut2d",
            "autoScale2d",
            "resetScale2d",
            "hoverClosestCartesian",
            "hoverCompareCartesian",
            "zoom3d",
            "pan3d",
            "orbitRotation",
            "tableRotation",
            "resetCameraLastSave",
            "resetCameraDefault3d",
            "hoverClosest3d",
            "zoomInGeo",
            "zoomOutGeo",
            "resetGeo",
            "hoverClosestGeo",
            "hoverClosestGl2d",
            "hoverClosestPie",
            "toggleHover",
            "toggleSpikelines",
            "resetViews",
        ]

    config_json = json.dumps(config)
    return _chart_page(fig_json, config_json)


def _toolbar_config(hide_toolbar):
    """Shared plotly modebar config (hide most buttons for the in-plugin view)."""
    config = {"displaylogo": False, "responsive": True}
    if hide_toolbar:
        config["modeBarButtonsToRemove"] = [
            "toImage", "sendDataToCloud", "zoom2d", "pan2d", "select2d",
            "lasso2d", "zoomIn2d", "zoomOut2d", "autoScale2d", "resetScale2d",
            "hoverClosestCartesian", "hoverCompareCartesian", "zoom3d", "pan3d",
            "orbitRotation", "tableRotation", "resetCameraLastSave",
            "resetCameraDefault3d", "hoverClosest3d", "zoomInGeo", "zoomOutGeo",
            "resetGeo", "hoverClosestGeo", "hoverClosestGl2d", "hoverClosestPie",
            "toggleHover", "toggleSpikelines", "resetViews",
        ]
    return config


def _chart_page(fig_json, config_json):
    """Self-contained HTML page embedding the vendored plotly.js v1.58."""
    return f"""<!DOCTYPE html>
<html><head><meta charset="utf-8">
<style>html,body{{height:100%;width:100%;margin:0;padding:0}}#chart{{width:100%;height:100%}}</style>
<script>{_plotly_js()}</script>
</head><body>
<div id="chart"></div>
<script>
var fig = {fig_json};
var config = {config_json};
Plotly.newPlot('chart', fig.data, fig.layout, config);
window.addEventListener('resize', function(){{ Plotly.Plots.resize('chart'); }});
</script>
</body></html>"""


_MULTISERIES_PALETTE = ["#1b6b39", "#d98f00", "#2a5d84", "#b71c1c", "#6a1b9a", "#00838f"]


def render_multiseries_chart_html(
    dataframe,
    group_col,
    hide_toolbar=True,
    title="Time Series",
    ylabel="Value",
    colors=None,
):
    """Multi-trace time-series page: one coloured line per ``group_col`` value
    (e.g. one per Landsat mission), sharing the x-axis.

    Trace dicts are built by hand — NOT via plotly express — so the JSON stays
    within what the vendored plotly.js v1.58 understands (same reason the
    single-series renderer reconstructs its trace). A px figure from a modern
    plotly carries attributes the old engine silently fails to render, leaving a
    blank chart.

    Args:
        dataframe: rows with ``dates``, ``AOI_average`` and ``group_col``.
        group_col: column whose distinct values become separate traces.
        hide_toolbar: hide modebar buttons (in-plugin view) vs show (browser).
        title, ylabel: chart labels.
        colors: optional {group_value: css_color} discrete map.
    """
    colors = colors or {}
    traces = []
    for i, (name, group) in enumerate(dataframe.groupby(group_col, sort=False)):
        group = group.sort_values("dates")
        color = colors.get(name) or _MULTISERIES_PALETTE[i % len(_MULTISERIES_PALETTE)]
        traces.append({
            "type": "scatter",
            "mode": "lines+markers",
            "name": str(name),
            "x": group["dates"].astype(str).tolist(),
            "y": [float(v) for v in group["AOI_average"].tolist()],
            "line": {"color": color},
            "marker": {"color": color},
        })

    layout = {
        "title": title,
        "xaxis": {"title": "Date"},
        "yaxis": {"title": ylabel, "tickformat": ".3f"},
        "margin": {"l": 80, "r": 20, "t": 40, "b": 40},
        "legend": {"orientation": "h"},
    }
    fig_json = json.dumps({"data": traces, "layout": layout})
    config_json = json.dumps(_toolbar_config(hide_toolbar))
    return _chart_page(fig_json, config_json)
