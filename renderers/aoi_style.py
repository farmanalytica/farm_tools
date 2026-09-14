# -*- coding: utf-8 -*-
"""
The single definition of what an AOI looks like on the canvas.

Both the polygon drawn with the AOI tool and the CAR boundary loaded from a
KML use this fill, so a drawn AOI and a fetched one are visibly the same kind
of thing.
"""

from qgis.core import QgsFillSymbol

_AOI_FILL = {
    "color": "27,107,57,40",
    "outline_color": "255,0,0,255",
    "outline_width": "0.6",
}


def build_aoi_fill_symbol():
    """Translucent green fill with a solid red outline."""
    return QgsFillSymbol.createSimple(dict(_AOI_FILL))
