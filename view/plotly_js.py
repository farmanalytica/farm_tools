# -*- coding: utf-8 -*-
"""
The vendored plotly.js both chart renderers embed.

This QGIS build ships only QtWebKit, whose engine cannot run the plotly.js v3
bundled with plotly 6.x. Every chart page therefore inlines the last v1 release
from ``assets/``. Reading a ~3 MB file per chart would be wasteful, so it is
read once and kept.
"""

import functools
import os

_PLOTLY_JS_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "assets",
    "plotly-1.58.5.min.js",
)


@functools.lru_cache(maxsize=1)
def plotly_js() -> str:
    """The vendored plotly.js source, read once per session."""
    with open(_PLOTLY_JS_PATH, "r", encoding="utf-8") as handle:
        return handle.read()
