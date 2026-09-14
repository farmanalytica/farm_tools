# -*- coding: utf-8 -*-
"""
Common raster rendering utilities for pseudocolor visualization.

Provides reusable methods for applying pseudocolor renderers with color ramps
to raster layers, following QGIS 3.44+ patterns.
"""

from dataclasses import dataclass

from qgis.core import (
    QgsColorRampShader,
    QgsLayerTreeLayer,
    QgsProject,
    QgsRasterLayer,
    QgsRasterShader,
    QgsSingleBandPseudoColorRenderer,
    QgsStyle,
)

_DEFAULT_STOP_COUNT = 256
_FLAT_BAND_SPREAD = 1.0


@dataclass
class PseudocolorStyle:
    """How one raster band is painted: which QGIS colour ramp, over which band."""

    color_ramp_name: str
    band_index: int = 1
    stop_count: int = _DEFAULT_STOP_COUNT


class RasterRendererUtils:
    """Common utilities for raster rendering with color ramps."""

    @staticmethod
    def apply_pseudocolor_renderer(raster_layer, style, value_range):
        """Paint ``raster_layer`` with ``style`` across ``value_range``.

        ``value_range`` is a ``(minimum, maximum)`` pair. Returns ``False``
        when QGIS does not know the named colour ramp.
        """
        color_ramp = QgsStyle.defaultStyle().colorRamp(style.color_ramp_name)
        if not color_ramp:
            return False

        min_val, max_val = value_range
        if min_val == max_val:
            max_val = min_val + _FLAT_BAND_SPREAD

        last_stop = style.stop_count - 1
        color_ramp_items = []
        for stop in range(style.stop_count):
            position = stop / last_stop
            value = min_val + (max_val - min_val) * position
            color_ramp_items.append(
                QgsColorRampShader.ColorRampItem(value, color_ramp.color(position))
            )

        color_ramp_shader = QgsColorRampShader()
        color_ramp_shader.setColorRampType(QgsColorRampShader.Interpolated)
        color_ramp_shader.setColorRampItemList(color_ramp_items)

        raster_shader = QgsRasterShader()
        raster_shader.setRasterShaderFunction(color_ramp_shader)

        renderer = QgsSingleBandPseudoColorRenderer(
            raster_layer.dataProvider(),
            style.band_index,
            raster_shader,
        )
        renderer.setClassificationMin(min_val)
        renderer.setClassificationMax(max_val)

        raster_layer.setRenderer(renderer)
        return True

    @staticmethod
    def add_layer_to_project(raster_layer):
        """Register the layer and put its node at the top of the layer tree."""
        QgsProject.instance().addMapLayer(raster_layer, False)
        layer_tree = QgsProject.instance().layerTreeRoot()
        layer_tree.insertChildNode(0, QgsLayerTreeLayer(raster_layer))

    @staticmethod
    def load_pseudocolor_raster(path, layer_name, style):
        """Load ``path``, paint it with ``style``, and add it to the project.

        Returns the loaded layer, or ``None`` when the raster is unreadable or
        the colour ramp is unknown.
        """
        layer = QgsRasterLayer(path, layer_name)
        if not layer.isValid():
            return None

        stats = layer.dataProvider().bandStatistics(style.band_index)
        applied = RasterRendererUtils.apply_pseudocolor_renderer(
            layer, style, (stats.minimumValue, stats.maximumValue)
        )
        if not applied:
            return None

        RasterRendererUtils.add_layer_to_project(layer)
        layer.triggerRepaint()
        return layer
