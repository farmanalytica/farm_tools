# -*- coding: utf-8 -*-
"""
Shared draw-AOI behaviour for the pages that offer a "Draw AOI" button.

DEM, RAVI, SAR, Landsat, SYSI and MapBiomas all wire that button to the same
toggle, and all skip their zoom-to-layer once when the AOI arrives from a
draw instead of from the combo. ``AoiDrawMixin`` holds that logic so each
controller only has to name its own combo and button.
"""

from ..tools.aoi_draw_tool import start_draw_aoi
from ..tools.map_canvas import DEFAULT_ZOOM_PADDING, zoom_canvas_to_layer


class AoiDrawMixin:
    """Draw-AOI toggle and one-shot zoom suppression for a page controller.

    The host controller must expose ``self.interface`` (a QGIS iface, or
    ``None`` when the page runs without a canvas).
    """

    _draw_tool = None
    _skip_zoom_once = False
    canvas_zoom_padding = DEFAULT_ZOOM_PADDING

    def toggle_draw_aoi(self, layer_combo, draw_button):
        """Start polygon-AOI drawing, or stop it if this page already owns the tool."""
        interface = self.interface
        if interface is None:
            return
        canvas = interface.mapCanvas()
        if self._draw_tool is not None and canvas.mapTool() is self._draw_tool:
            canvas.unsetMapTool(self._draw_tool)
            self._draw_tool = None
            return
        self._draw_tool = start_draw_aoi(
            interface,
            layer_combo,
            draw_button,
            before_select=self._suppress_next_zoom,
        )

    def _suppress_next_zoom(self):
        self._skip_zoom_once = True

    def _consume_zoom_suppression(self):
        """True when the pending zoom-to-layer should be skipped; clears the flag."""
        if not self._skip_zoom_once:
            return False
        self._skip_zoom_once = False
        return True

    def zoom_to_aoi_layer(self, layer):
        """Fit the canvas around ``layer``.

        Does nothing when there is no canvas, no usable layer, or the user
        just drew this AOI and is already looking at it.
        """
        if not layer or not layer.isValid() or self.interface is None:
            return
        if self._consume_zoom_suppression():
            return
        zoom_canvas_to_layer(
            self.interface.mapCanvas(), layer, self.canvas_zoom_padding
        )
