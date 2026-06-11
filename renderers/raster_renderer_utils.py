# -*- coding: utf-8 -*-
"""
Common raster rendering utilities for pseudocolor visualization.

Provides reusable methods for applying pseudocolor renderers with color ramps
to raster layers, following QGIS 3.44+ patterns.
"""

from qgis.core import (
    QgsColorRampShader,
    QgsLayerTreeLayer,
    QgsProject,
    QgsRasterShader,
    QgsSingleBandPseudoColorRenderer,
    QgsStyle,
)


class RasterRendererUtils:
    """Common utilities for raster rendering with color ramps."""

    @staticmethod
    def apply_pseudocolor_renderer(
        raster_layer,
        band_index,
        color_ramp_name,
        min_val,
        max_val,
        num_stops=256,
    ):

        style = QgsStyle.defaultStyle()
        color_ramp = style.colorRamp(color_ramp_name)

        if not color_ramp:
            return False

        if min_val == max_val:
            max_val = min_val + 1.0

        color_ramp_shader = QgsColorRampShader()
        color_ramp_shader.setColorRampType(QgsColorRampShader.Interpolated)

        color_ramp_items = []
        for i in range(num_stops):
            value = min_val + (max_val - min_val) * (i / (num_stops - 1))
            color = color_ramp.color(i / (num_stops - 1))
            color_ramp_items.append(QgsColorRampShader.ColorRampItem(value, color))

        color_ramp_shader.setColorRampItemList(color_ramp_items)

        raster_shader = QgsRasterShader()
        raster_shader.setRasterShaderFunction(color_ramp_shader)

        renderer = QgsSingleBandPseudoColorRenderer(
            raster_layer.dataProvider(),
            band_index,
            raster_shader,
        )

        renderer.setClassificationMin(min_val)
        renderer.setClassificationMax(max_val)

        raster_layer.setRenderer(renderer)

        return True

    @staticmethod
    def add_layer_to_project(raster_layer, at_top=True):

        QgsProject.instance().addMapLayer(raster_layer, False)

        layer_tree = QgsProject.instance().layerTreeRoot()
        if at_top:
            layer_tree.insertChildNode(0, QgsLayerTreeLayer(raster_layer))
        else:
            layer_tree.insertLayer(-1, raster_layer)

    @staticmethod
    def load_pseudocolor_raster(
        path,
        layer_name,
        band_index,
        color_ramp_name,
        at_top=True,
    ):

        from qgis.core import QgsRasterLayer

        layer = QgsRasterLayer(path, layer_name)
        if not layer.isValid():
            return None

        provider = layer.dataProvider()
        stats = provider.bandStatistics(band_index)
        min_val = stats.minimumValue
        max_val = stats.maximumValue

        apply_renderer = RasterRendererUtils.apply_pseudocolor_renderer(
            layer, band_index, color_ramp_name, min_val, max_val
        )

        if not apply_renderer:
            return None

        RasterRendererUtils.add_layer_to_project(layer, at_top=at_top)
        layer.triggerRepaint()

        return layer
