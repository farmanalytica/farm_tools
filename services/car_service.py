# -*- coding: utf-8 -*-
"""
CAR (Cadastro Ambiental Rural) lookup service.

Resolves a Brazilian CAR code to its property geometry by reading the public
static index published by the *conformidade rural* project on S3, then writes
the matched feature to disk as a GeoJSON FeatureCollection.

The bucket is public (plain HTTPS GET, no signing). Lookup is two-step:

1. ``stem_index_{UF}.json`` — maps a CAR code to its geometry chunk file.
2. ``chunks/chunk_{X}_{Y}.geojson`` — a FeatureCollection holding the geometry;
   the matching feature carries ``cod_imovel`` (or ``unavailable_id``) equal to
   the CAR code.

Pure logic only: no QGIS or UI imports here. KML conversion and layer loading
stay on the main thread in the controller/renderer.
"""

import json
import os
import re

import requests

# Public bucket published by the conformidade rural project (see
# C:\repos\conformidaderural — areaOverlayLayer.js / gen_featured_ndvi.py).
S3_BASE = (
    "https://dados-car-963200076509-us-east-2-an.s3.us-east-2.amazonaws.com"
    "/local_chunks/area_overlay"
)

# UF-NNNNNNN-HEX32, e.g. GO-5219258-CAE9B45810F4458584BAB4E860CF288E
CAR_RE = re.compile(r"^[A-Z]{2}-\d+-[0-9A-F]{32}$")
_CHUNK_RE = re.compile(r"chunk_(-?\d+_-?\d+)\.geojson")
_REQUEST_TIMEOUT = 120


class CarService:
    """Fetches CAR property geometry from the public S3 static index."""

    @staticmethod
    def normalize_code(code: str) -> str:
        """Trim and uppercase the CAR code (the index keys are uppercase)."""
        return (code or "").strip().upper()

    @staticmethod
    def is_valid_code(code: str) -> bool:
        return bool(CAR_RE.match(CarService.normalize_code(code)))

    @staticmethod
    def fetch_geojson(code: str, output_folder=None, proxy=None) -> str:
        """Resolve ``code`` to its geometry and save it as a GeoJSON file.

        Returns the path to the written ``.geojson`` FeatureCollection.
        Raises ``RuntimeError`` with a user-facing message on any failure.
        """
        code = CarService.normalize_code(code)
        if not CarService.is_valid_code(code):
            raise RuntimeError(
                "Invalid CAR code. Expected a format like "
                "GO-5219258-CAE9B45810F4458584BAB4E860CF288E."
            )

        uf = code[:2]
        proxies = {"http": proxy, "https": proxy} if proxy else None

        index = CarService._get_json(f"{S3_BASE}/stem_index_{uf}.json", proxies)
        if index is None:
            raise RuntimeError(
                f"No CAR index found for state '{uf}'. "
                "Check the state prefix of the code."
            )

        chunk_file = index.get(code)
        if not chunk_file:
            # The index may store a longer stem; match by prefix as the web app does.
            stem = next(
                (k for k in index if k.upper().startswith(code)), None
            )
            chunk_file = index.get(stem) if stem else None
        if not chunk_file:
            raise RuntimeError(
                "CAR code not found in the registry index for this state."
            )

        match = _CHUNK_RE.search(chunk_file)
        if not match:
            raise RuntimeError("Unexpected chunk reference in the registry index.")

        chunk = CarService._get_json(
            f"{S3_BASE}/chunks/chunk_{match.group(1)}.geojson", proxies
        )
        if chunk is None:
            raise RuntimeError("Failed to download the property geometry chunk.")

        feature = CarService._find_feature(chunk, code)
        if feature is None:
            raise RuntimeError("Property geometry not found in the registry chunk.")

        collection = {"type": "FeatureCollection", "features": [feature]}
        return CarService._write_geojson(collection, code, output_folder)

    @staticmethod
    def _find_feature(collection: dict, code: str):
        for feature in collection.get("features", []) or []:
            props = feature.get("properties") or {}
            fid = str(props.get("cod_imovel") or props.get("unavailable_id") or "")
            if fid.strip().upper() == code:
                return feature
        return None

    @staticmethod
    def _get_json(url: str, proxies):
        """GET ``url`` as JSON; proxy first then direct. ``None`` on HTTP 404."""
        response = CarService._request(url, proxies)
        if response.status_code == 404:
            return None
        if not response.ok:
            raise RuntimeError(
                f"CAR registry request failed (HTTP {response.status_code}): "
                f"{response.reason}"
            )
        return json.loads(response.content.decode("utf-8"))

    @staticmethod
    def _request(url: str, proxies):
        if proxies:
            try:
                return requests.get(
                    url, verify=True, timeout=_REQUEST_TIMEOUT, proxies=proxies
                )
            except Exception:
                pass
        return requests.get(url, verify=True, timeout=_REQUEST_TIMEOUT)

    @staticmethod
    def _write_geojson(collection: dict, code: str, output_folder) -> str:
        import tempfile

        target_dir = (
            output_folder
            if (output_folder and os.path.isdir(output_folder))
            else tempfile.gettempdir()
        )
        path = CarService._unique_path(target_dir, f"CAR_{code}.geojson")
        with open(path, "w", encoding="utf-8") as handle:
            json.dump(collection, handle, ensure_ascii=False)
        return path

    @staticmethod
    def _unique_path(folder: str, filename: str) -> str:
        candidate = os.path.join(folder, filename)
        if not os.path.exists(candidate):
            return candidate
        base, ext = os.path.splitext(filename)
        counter = 1
        while True:
            candidate = os.path.join(folder, f"{base}_{counter}{ext}")
            if not os.path.exists(candidate):
                return candidate
            counter += 1
