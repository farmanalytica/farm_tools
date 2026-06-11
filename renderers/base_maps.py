from qgis.core import QgsProject, QgsRasterLayer
from qgis.utils import iface


def add_google_hybrid_layer():

    existing_layers = QgsProject.instance().mapLayers().values()
    layer_names = [layer.name() for layer in existing_layers]

    if "Google Hybrid" in layer_names:
        print("Google Hybrid layer already added.")
        return

    google_hybrid_url = (
        "type=xyz&zmin=0&zmax=20&url="
        "https://mt1.google.com/vt/lyrs%3Dy%26x%3D{x}%26y%3D{y}%26z%3D{z}"
    )
    layer_name = "Google Hybrid"
    provider_type = "wms"

    try:
        google_hybrid_layer = QgsRasterLayer(
            google_hybrid_url, layer_name, provider_type
        )

        if not google_hybrid_layer.isValid():
            print("Failed to load {}. Invalid layer.".format(layer_name))
            return

        QgsProject.instance().addMapLayer(google_hybrid_layer, False)

        google_hybrid_layer.setOpacity(1)

        layer_tree = QgsProject.instance().layerTreeRoot()
        layer_tree.insertLayer(-1, google_hybrid_layer)

        iface.mapCanvas().refresh()

    except Exception as exc:
        print("Error loading {}: {}".format(layer_name, exc))
