# -*- coding: utf-8 -*-
"""
AOI service layer.

Extract and convert uploaded AOI geometries to EE objects.
"""

import json
import ee

from qgis.core import (
    QgsProject,
    QgsMapLayer,
    QgsWkbTypes,
    QgsGeometry,
    QgsCoordinateTransform,
    QgsCoordinateReferenceSystem,
    QgsDistanceArea,
    QgsUnitTypes,
)


def _remove_z_dimension(coords):

    if isinstance(coords[0], (int, float)):
        return coords[:2]
    return [_remove_z_dimension(c) for c in coords]


class AOIService:
    """Service for extracting and converting AOI geometries to Earth Engine objects."""

    @staticmethod
    def _validate_vector_polygon_layer(layer):

        if not layer or layer.type() != QgsMapLayer.VectorLayer:
            raise ValueError("Layer must be a valid vector layer.")

        if layer.geometryType() != QgsWkbTypes.PolygonGeometry:
            raise ValueError("Layer must be polygon or multipolygon.")

    @staticmethod
    def _get_dissolved_geometry(layer, use_selected_features=True):

        features = (
            layer.selectedFeatures()
            if use_selected_features and layer.selectedFeatureCount() > 0
            else list(layer.getFeatures())
        )

        if not features:
            raise ValueError("Layer has no geometries.")

        # GEOS' unaryUnion silently returns a null/empty geometry when any
        # input feature is invalid (e.g. self-intersecting rings), so each
        # feature is fixed individually first — this both avoids the failure
        # and lets us name the offending feature(s) if it happens anyway.
        geometries = []
        invalid_fids = []
        for f in features:
            geom = f.geometry()
            if not geom or geom.isNull() or geom.isEmpty():
                invalid_fids.append(f.id())
                continue
            if not geom.isGeosValid():
                geom = geom.makeValid()
                if not geom or geom.isNull() or geom.isEmpty():
                    invalid_fids.append(f.id())
                    continue
            geometries.append(geom)

        if not geometries:
            raise ValueError("Layer has no geometries.")

        dissolved = QgsGeometry.unaryUnion(geometries)

        if dissolved.isEmpty():
            fids = ", ".join(str(fid) for fid in invalid_fids[:10])
            more = "..." if len(invalid_fids) > 10 else ""
            detail = (
                f" Invalid feature id(s): {fids}{more}." if invalid_fids else ""
            )
            raise ValueError(
                "Could not dissolve AOI geometry — one or more features have "
                "invalid geometry that QGIS could not repair automatically."
                f"{detail} Fix them with Vector → Geometry Tools → "
                "Fix Geometries and try again."
            )

        return dissolved

    @staticmethod
    def _layer_to_geojson_4326(layer, use_selected_features=True):
        """
        Dissolve a layer's features into one 2D, EPSG:4326 GeoJSON geometry.

        Returns a tuple of the GeoJSON dict and the Bounding Box
        [min_x, min_y, max_x, max_y]. Shared by the Earth Engine and shapely
        converters so both stay in sync.
        """
        geometry = AOIService._get_dissolved_geometry(layer, use_selected_features)

        if layer.crs().authid() != "EPSG:4326":
            transform = QgsCoordinateTransform(
                layer.crs(),
                QgsCoordinateReferenceSystem("EPSG:4326"),
                QgsProject.instance(),
            )
            geometry.transform(transform)

        rectangle = geometry.boundingBox()
        bbox = (
            rectangle.xMinimum(),
            rectangle.yMinimum(),
            rectangle.xMaximum(),
            rectangle.yMaximum(),
        )

        geojson_str = geometry.asJson()
        if not geojson_str:
            raise ValueError(
                f"Could not export geometry to GeoJSON. "
                f"Geometry type: {geometry.type()}, WKB type: {geometry.wkbType()}"
            )

        geojson = json.loads(geojson_str)
        geojson["coordinates"] = _remove_z_dimension(geojson["coordinates"])
        return geojson, bbox

    @staticmethod
    def _layer_to_ee_feature_collection(layer, use_selected_features=True):
        """
        Convert a QGIS layer to an Earth Engine FeatureCollection, assuring
        compatibility (2D and EPSG:4326)

        Returns a tuple of FeatureCollection and Bounding Box [min_x, min_y, max_x, max_y]
        """
        geojson, bbox = AOIService._layer_to_geojson_4326(layer, use_selected_features)
        ee_geometry = ee.Geometry(geojson)
        return ee.FeatureCollection([ee.Feature(ee_geometry)]), bbox

    @staticmethod
    def get_ee_feature_colection_from_layer(layer, use_selected_features=True):

        AOIService._validate_vector_polygon_layer(layer)
        return AOIService._layer_to_ee_feature_collection(layer, use_selected_features)

    @staticmethod
    def get_shapely_geometry_from_layer(layer, use_selected_features=True):
        """
        Dissolved AOI as a shapely geometry in EPSG:4326.

        agrigee_lite's ``get.sits`` builds its ee.Feature from a shapely
        geometry via ``__geo_interface__``, so the time-series path needs the
        AOI in shapely form rather than as an ee object.
        """
        from shapely.geometry import shape

        AOIService._validate_vector_polygon_layer(layer)
        geojson, _bbox = AOIService._layer_to_geojson_4326(layer, use_selected_features)
        return shape(geojson)

    @staticmethod
    def get_area_m2_from_layer(layer, use_selected_features=True):
        """Ellipsoidal area of the dissolved AOI in square metres.

        Computed with QGIS' ``QgsDistanceArea`` (ellipsoidal, so robust for
        geographic CRSs) on the main thread — no Earth Engine round-trip. Used
        to translate the Landsat page's "min valid coverage %" into agrigee_lite's
        absolute ``min_valid_pixel_count``.
        """
        AOIService._validate_vector_polygon_layer(layer)
        geometry = AOIService._get_dissolved_geometry(layer, use_selected_features)

        calc = QgsDistanceArea()
        calc.setSourceCrs(layer.crs(), QgsProject.instance().transformContext())
        calc.setEllipsoid(QgsProject.instance().ellipsoid() or "WGS84")
        area = calc.measureArea(geometry)
        return calc.convertAreaMeasurement(area, QgsUnitTypes.AreaSquareMeters)
