from __future__ import annotations

import math
from typing import Literal

EARTH_RADIUS_KM = 6371.0
EARTH_RADIUS_NM = 3440.065


def haversine(
    latitude_start: float,
    latitude_end: float,
    longitude_start: float,
    longitude_end: float,
    unit: Literal["nautical_miles", "kilometers"] = "nautical_miles",
) -> float:
    """Surface distance between two decimal-degree coordinate pairs.

    Args:
        latitude_start:  Starting latitude in decimal degrees.
        latitude_end:    Ending latitude in decimal degrees.
        longitude_start: Starting longitude in decimal degrees.
        longitude_end:   Ending longitude in decimal degrees.
        unit:            ``"nautical_miles"`` (default) or ``"kilometers"``.
    """
    earth_radius_lookup = {
        "nautical_miles": EARTH_RADIUS_NM,
        "kilometers": EARTH_RADIUS_KM,
    }
    try:
        earth_radius = earth_radius_lookup[unit]
    except KeyError as exc:
        raise ValueError(f"Unsupported unit '{unit}' supplied to haversine") from exc

    d_latitude = (latitude_end - latitude_start) * math.pi / 180
    d_longitude = (longitude_end - longitude_start) * math.pi / 180

    lat_start_rad = latitude_start * math.pi / 180.0
    lat_end_rad = latitude_end * math.pi / 180.0

    theta = pow(math.sin(d_latitude / 2), 2) + pow(
        math.sin(d_longitude / 2), 2
    ) * math.cos(lat_start_rad) * math.cos(lat_end_rad)

    return earth_radius * 2 * math.asin(math.sqrt(theta))


def bearing_degrees(
    latitude_start: float,
    longitude_start: float,
    latitude_end: float,
    longitude_end: float,
) -> float:
    """Forward azimuth (0–360°) between two decimal-degree coordinate pairs."""
    lat_s, lon_s, lat_e, lon_e = map(
        math.radians, [latitude_start, longitude_start, latitude_end, longitude_end]
    )
    dlon = lon_e - lon_s
    y = math.sin(dlon) * math.cos(lat_e)
    x = math.cos(lat_s) * math.sin(lat_e) - math.sin(lat_s) * math.cos(lat_e) * math.cos(dlon)
    return (math.degrees(math.atan2(y, x)) + 360) % 360


def convert_to_decimal_degrees(degree: str, lon: bool = True) -> float:
    """Convert an NMEA DDMM.MMMM / DDDMM.MMMM string to decimal degrees.

    Handles leading signs (e.g. ``"-0018.9046"``), trailing direction letters
    (``"5123.45S"``), or legacy strings where the minus sign is embedded in the
    minutes portion (e.g. ``"000-18.9046"``).
    """
    if degree is None:
        raise ValueError("Invalid NMEA degree value: None")

    value = str(degree).strip()
    if not value:
        raise ValueError("Invalid NMEA degree value: empty string")

    sign = 1.0
    if value and value[0] in "+-":
        if value[0] == "-":
            sign *= -1.0
        value = value[1:]

    if not value:
        return 0.0

    if "." in value:
        whole, frac = value.split(".", 1)
    else:
        whole, frac = value, ""

    if len(whole) <= 2:
        degrees_str = "0"
        minutes_str = whole.zfill(2)
    else:
        degrees_str = whole[:-2] or "0"
        minutes_str = whole[-2:]

    minutes_val = minutes_str
    if frac:
        minutes_val = f"{minutes_val}.{frac}"

    return sign * (float(degrees_str) + float(minutes_val) / 60.0)


def decimal_to_dms_format(decimal_deg: float, is_lon: bool = True) -> str:
    """Format decimal degrees as an NMEA-style DDMM.mmmmmm string.

    Uses 3 degree digits for longitudes ≥ 100°, otherwise 2.
    """
    sign = "-" if decimal_deg < 0 else ""
    absolute_deg = abs(decimal_deg)
    degrees = int(absolute_deg)
    minutes = (absolute_deg - degrees) * 60
    width = 3 if is_lon and degrees >= 100 else 2
    return f"{sign}{degrees:0{width}d}{minutes:09.6f}"
