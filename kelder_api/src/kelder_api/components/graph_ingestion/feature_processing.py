from __future__ import annotations

import math

from shapely.geometry import shape


def _parse_wkt_coordinates(coordinates: list[list[float]]) -> str:
    return ", ".join(f"{lon} {lat}" for lon, lat in coordinates)


def build_danger_zone_coords(
    coordinates: list[float],
    radius_deg: float = 0.0018,
    segments: int = 32,
    cardinal: str | None = None,
) -> str:
    """
    Build a ring WKT coordinate string around a point.

    Coordinates are expected in [longitude, latitude] order.
    """
    if len(coordinates) < 2:
        raise ValueError("coordinates must contain longitude and latitude")

    center_lon = coordinates[0]
    center_lat = coordinates[1]

    if cardinal:
        direction = cardinal.lower().strip()
        if direction == "north":
            center_lat -= radius_deg * 1.05
        elif direction == "south":
            center_lat += radius_deg * 1.05
        elif direction == "east":
            center_lon -= radius_deg * 1.05
        elif direction == "west":
            center_lon += radius_deg * 1.05
        else:
            raise ValueError(f"Unsupported cardinal direction: {cardinal}")

    ring: list[list[float]] = []
    for index in range(segments):
        angle = 2 * math.pi * index / segments
        lon = center_lon + radius_deg * math.cos(angle)
        lat = center_lat + radius_deg * math.sin(angle)
        ring.append([lon, lat])
    ring.append(ring[0])

    return _parse_wkt_coordinates(ring)


def _parse_light(feature: dict) -> str | None:
    properties = feature.get("properties", {})
    character = properties.get("seamark:light:character")
    colour = properties.get("seamark:light:colour")
    group = properties.get("seamark:light:group")
    period = properties.get("seamark:light:period")
    if not any([character, colour, group, period]):
        return None
    return f"{character}-{colour}-group:{group}-period:{period}"


def process_special_purpose(feature: dict) -> dict:
    properties = feature.get("properties", {})
    return {
        "name": properties.get("seamark:name"),
        "type": "SPECIAL_PURPOSE",
        "coordinates": feature["geometry"]["coordinates"],
        "light": _parse_light(feature),
    }


def process_isolated_danger(feature: dict) -> dict:
    properties = feature.get("properties", {})
    return {
        "name": properties.get("seamark:name"),
        "type": "ISOLATED_DANGER",
        "coordinates": feature["geometry"]["coordinates"],
        "light": _parse_light(feature),
    }


def process_cardinal_mark(feature: dict) -> dict:
    properties = feature.get("properties", {})
    category = (
        properties.get("seamark:buoy_cardinal:category")
        or properties.get("seamark:beacon_cardinal:category")
        or "unknown"
    )
    return {
        "name": properties.get("seamark:name"),
        "type": f"{category.upper()} CARDINAL",
        "category": category,
        "coordinates": feature["geometry"]["coordinates"],
        "light": _parse_light(feature),
    }


def process_lateral_mark(feature: dict) -> dict:
    properties = feature.get("properties", {})
    category = (
        properties.get("seamark:buoy_lateral:category")
        or properties.get("seamark:beacon_lateral:category")
    )
    if category is None:
        colour = (
            properties.get("seamark:buoy_lateral:colour")
            or properties.get("seamark:beacon_lateral:colour")
        )
        if colour == "red":
            category = "port"
        elif colour == "green":
            category = "starboard"
        else:
            category = "unknown"
    return {
        "name": properties.get("seamark:name"),
        "type": f"{category.upper()} LATERAL",
        "coordinates": feature["geometry"]["coordinates"],
        "light": _parse_light(feature),
    }


def process_harbour(feature: dict) -> dict:
    geometry = shape(feature["geometry"])
    centroid = geometry.centroid
    properties = feature.get("properties", {})
    return {
        "name": properties.get("name"),
        "category": properties.get("seamark:harbour:category"),
        "coordinates": [centroid.x, centroid.y],
    }


def process_coastline(feature: dict) -> dict:
    properties = feature.get("properties", {})
    geometry = feature["geometry"]
    geometry_type = geometry["type"]
    if geometry_type == "Polygon":
        coordinates = _parse_wkt_coordinates(geometry["coordinates"][0])
    elif geometry_type == "LineString":
        coordinates = _parse_wkt_coordinates(geometry["coordinates"])
    else:
        raise TypeError(f"Unsupported coastline geometry type: {geometry_type}")
    return {
        "name": properties.get("name"),
        "type": properties.get("place", "mainland"),
        "linestring": coordinates,
    }


def process_wreck(feature: dict) -> dict:
    properties = feature.get("properties", {})
    geometry = feature["geometry"]
    geometry_type = geometry["type"]

    if geometry_type in {"Polygon", "LineString"}:
        if geometry_type == "Polygon":
            coords = geometry["coordinates"][0]
        else:
            coords = geometry["coordinates"]
        polygon = _parse_wkt_coordinates(coords)
        centroid = shape(geometry).centroid
        coordinates = [centroid.x, centroid.y]
    elif geometry_type == "Point":
        coordinates = geometry["coordinates"]
        polygon = build_danger_zone_coords(coordinates)
    else:
        raise TypeError(f"Unsupported wreck geometry type: {geometry_type}")

    return {
        "name": properties.get("name"),
        "type": "WRECK",
        "coordinates": coordinates,
        "danger_zone": polygon,
    }
