# -*- coding: utf-8 -*-
"""Build map links and point rows for PDF rendering."""

from urllib.parse import quote


def format_coordinate(value):
    """Return a fixed precision coordinate string."""
    return "{:.6f}".format(value)


def build_google_maps_url(latitude, longitude):
    """Create a robust mobile-friendly Google Maps destination URL."""
    return "https://maps.google.com/?q={},{}".format(
        format_coordinate(latitude),
        format_coordinate(longitude),
    )


def build_google_maps_directions_url(coordinates, travel_mode="driving"):
    """Create a Google Maps directions URL using current location as origin.

    Expects coordinates in (longitude, latitude) tuples.
    Google Maps uses the device/browser current location when origin is omitted.
    """
    if len(coordinates) < 2:
        raise ValueError("At least 2 points are required to build a route.")

    def pair(longitude, latitude):
        return "{},{}".format(
            format_coordinate(latitude),
            format_coordinate(longitude),
        )

    destination = pair(coordinates[-1][0], coordinates[-1][1])
    url = (
        "https://www.google.com/maps/dir/?api=1&travelmode={mode}"
        "&destination={destination}"
    ).format(
        mode=quote(travel_mode, safe=""),
        destination=quote(destination, safe=","),
    )

    waypoints = [pair(lon, lat) for lon, lat in coordinates[:-1]]
    if waypoints:
        waypoints_value = "|".join(waypoints)
        url = "{}&waypoints={}".format(url, quote(waypoints_value, safe=",|"))

    return url


def build_route_items(coordinates, max_points_per_route=10):
    """Build one or more route links suitable for PDF rendering.

    Splits long routes into overlapping chunks to respect waypoint limits.
    """
    if len(coordinates) < 2:
        return []

    route_items = []
    start = 0
    chunk_index = 1

    while start < len(coordinates) - 1:
        end = min(start + max_points_per_route, len(coordinates))
        chunk = coordinates[start:end]
        route_items.append(
            {
                "index": chunk_index,
                "start_point": start + 1,
                "end_point": end,
                "point_count": len(chunk),
                "url": build_google_maps_directions_url(chunk),
            }
        )

        if end >= len(coordinates):
            break

        start = end - 1
        chunk_index += 1

    return route_items


def build_mark_items(coordinates):
    """Transform (lon, lat) tuples into display rows used by the HTML template."""
    marks = []
    for index, (longitude, latitude) in enumerate(coordinates, start=1):
        marks.append(
            {
                "index": index,
                "latitude": format_coordinate(latitude),
                "longitude": format_coordinate(longitude),
                "url": build_google_maps_url(latitude, longitude),
            }
        )
    return marks
