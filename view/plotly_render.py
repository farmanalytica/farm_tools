# -*- coding: utf-8 -*-
"""Render arbitrary plotly figures inside a QtWebKit ``QWebView``.

This QGIS build ships only QtWebKit (no QtWebEngine/Chromium). The site-packages
``plotly`` is 6.x, whose bundled plotly.js (v3) does NOT run under QtWebKit, so
``fig.to_html(include_plotlyjs="cdn")`` renders blank. Like ``sar_plot.py`` we:

  1. reuse the vendored last-v1 plotly.js (``assets/plotly-1.58.5.min.js``),
  2. drop the v6 default template the old engine can't parse (``template="none"``),
  3. decode plotly 6.x base64 typed-arrays ("bdata") into plain lists, which v1.58
     cannot decode itself (numbers would render as garbage),
  4. write the page to a temp file and load it via a ``file://`` URL - QtWebKit
     renders large embedded plotly content reliably from a file, unlike setHtml.

Unlike ``sar_plot.render_chart_html`` (which hand-builds traces for one specific
dataframe shape), this module accepts any ``plotly.graph_objects.Figure``. The
same ``render_html`` feeds both the in-plugin view and "open in browser", so the
chart is identical in both.
"""
import base64
import json
import os
import tempfile

import numpy as np

from qgis.PyQt.QtCore import QUrl

from .webcompat import USING_WEBENGINE

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


def _decode_typed_arrays(obj):
    """Recursively turn plotly 6.x base64 typed-array dicts into plain lists."""
    if isinstance(obj, dict):
        if "bdata" in obj and "dtype" in obj:
            try:
                arr = np.frombuffer(base64.b64decode(obj["bdata"]), dtype=obj["dtype"])
                return arr.tolist()
            except Exception:
                return obj
        return {k: _decode_typed_arrays(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_decode_typed_arrays(v) for v in obj]
    return obj


def _json_default(o):
    """Serialize numpy / datetime values the stdlib json encoder can't handle."""
    if isinstance(o, np.generic):
        return o.item()
    if isinstance(o, np.ndarray):
        return o.tolist()
    if hasattr(o, "isoformat"):  # datetime / date / pandas.Timestamp
        return o.isoformat()
    return str(o)


def figure_to_json(fig):
    """Serialize a plotly figure to QtWebKit-safe JSON (no base64, no v6 template)."""
    fig.update_layout(template="none")
    fig_dict = _decode_typed_arrays(fig.to_dict())
    return json.dumps(fig_dict, default=_json_default)


def render_html(fig, config):
    """Return a self-contained HTML page rendering ``fig`` with vendored plotly.js."""
    fig_json = figure_to_json(fig)
    config_json = json.dumps(config or {})
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


def show_in_webview(web_view, fig, config, previous_path=None):
    """Render ``fig`` into ``web_view`` via a temp ``file://`` page.

    Deletes ``previous_path`` (the temp file from the last render for this view)
    and returns the new temp path so the caller can track it for cleanup.
    """
    _safe_remove(previous_path)
    html = render_html(fig, config)
    fd, path = tempfile.mkstemp(suffix=".html", prefix="farm_tools_climaplots_")
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        f.write(html)
    web_view.load(QUrl.fromLocalFile(path))
    return path


def run_js(web_view, js):
    """Execute ``js`` in an already-loaded view, cross-backend.

    WebEngine exposes ``page().runJavaScript``; QtWebKit uses
    ``page().mainFrame().evaluateJavaScript``. Best-effort — silently no-ops if
    the page isn't ready or the backend rejects the call.
    """
    try:
        if USING_WEBENGINE:
            web_view.page().runJavaScript(js)
        else:
            web_view.page().mainFrame().evaluateJavaScript(js)
    except Exception:
        pass


def restyle_bar_colors(web_view, colors):
    """Live-update the first bar trace's per-point colors without reloading.

    ``Plotly.restyle`` mutates the existing chart in place, so this is cheap
    enough to call on every slider tick (unlike ``show_in_webview``, which
    rebuilds and reloads the whole page). ``colors`` is one CSS color per bar.

    The JS is wrapped in try/catch and returns a status string so ``run_js``'s
    callback reveals whether ``Plotly`` / the ``'chart'`` div were available.
    """
    payload = json.dumps({"marker.color": [colors]})
    js = (
        "(function(){{"
        "  try {{"
        "    if (typeof Plotly === 'undefined') return 'no-plotly';"
        "    if (!document.getElementById('chart')) return 'no-div';"
        "    Plotly.restyle('chart', {0}, [0]);"
        "    return 'ok';"
        "  }} catch (e) {{ return 'ERR: ' + e; }}"
        "}})();"
    ).format(payload)
    run_js(web_view, js)


def open_in_browser(fig, config):
    """Write ``fig`` to a temp HTML page (same vendored render) and open it."""
    import webbrowser

    html = render_html(fig, config)
    fd, path = tempfile.mkstemp(suffix=".html", prefix="farm_tools_climaplots_browser_")
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        f.write(html)
    webbrowser.open(QUrl.fromLocalFile(path).toString())


def clear_webview(web_view, previous_path=None):
    """Blank a web view and remove its temp file."""
    _safe_remove(previous_path)
    try:
        web_view.setHtml("")
    except Exception:
        pass
    return None


def _safe_remove(path):
    if path and os.path.exists(path):
        try:
            os.remove(path)
        except OSError:
            pass
