# -*- coding: utf-8 -*-
"""
Fetching an Earth Engine image to disk.

Every page that exports a GeoTIFF asked Earth Engine for a download URL, got
it with ``requests``, picked a non-colliding filename and wrote the bytes.
That sequence lives here once, so a page only says what it wants written and
at what resolution.
"""

import os
import tempfile
from dataclasses import dataclass
from typing import Optional

import requests

# Native pixel size of the sensors the plugin exports.
SENTINEL_SCALE_M = 10
LANDSAT_SCALE_M = 30
MAPBIOMAS_SCALE_M = 30
DEM_SCALE_M = 30

WGS84 = "EPSG:4326"

# Earth Engine assembles the GeoTIFF before it answers, so the wait is the
# export, not the transfer.
_DOWNLOAD_TIMEOUT_S = 300


def resolve_output_folder(output_folder: Optional[str]) -> str:
    """``output_folder`` when it is a real directory, else the system temp dir."""
    if output_folder and os.path.isdir(output_folder):
        return output_folder
    return tempfile.gettempdir()


def unique_path(folder: str, filename: str) -> str:
    """``filename`` inside ``folder``, suffixed ``_1``, ``_2``, … if taken."""
    candidate = os.path.join(folder, filename)
    if not os.path.exists(candidate):
        return candidate

    stem, extension = os.path.splitext(filename)
    counter = 1
    while True:
        candidate = os.path.join(folder, f"{stem}_{counter}{extension}")
        if not os.path.exists(candidate):
            return candidate
        counter += 1


@dataclass
class GeoTiffRequest:
    """Where an Earth Engine image should land, and how it should be gridded.

    ``product`` only names the export in the error message. ``crs`` of ``None``
    leaves the image in its own projection, which is what the DEM page wants.
    """

    region: object
    filename: str
    output_folder: Optional[str] = None
    scale: int = SENTINEL_SCALE_M
    product: str = "Download"
    crs: Optional[str] = WGS84


def download_geotiff(image, request: GeoTiffRequest) -> str:
    """Write ``image`` as a GeoTIFF under a free name, and return that path."""
    parameters = {
        "scale": request.scale,
        "region": request.region.bounds().getInfo(),
        "format": "GeoTIFF",
    }
    if request.crs:
        parameters["crs"] = request.crs

    response = requests.get(
        image.getDownloadURL(parameters), timeout=_DOWNLOAD_TIMEOUT_S
    )
    if not response.ok:
        raise RuntimeError(
            f"{request.product} download failed "
            f"(HTTP {response.status_code}): {response.reason}"
        )

    output_path = unique_path(
        resolve_output_folder(request.output_folder), request.filename
    )
    with open(output_path, "wb") as handle:
        handle.write(response.content)
    return output_path
