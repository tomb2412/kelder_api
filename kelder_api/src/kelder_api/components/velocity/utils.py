import math
from datetime import datetime
from typing import Literal

import numpy as np

EARTH_RADIUS_KM = 6371.0
EARTH_RADIUS_NM = 3440.065


def parse_timestamp(time: str) -> datetime:
    """
    Method to parse the gps timestamp as string

    args:
        date_now
    """
    time_format = "%H:%M:%S+00:00"
    parsed_time = datetime.strptime(time, time_format)
    return parsed_time


def time_difference_seconds(time_start: datetime, time_end: datetime) -> datetime:
    # Method to return the seconds between two time stamps
    return (time_end - time_start).total_seconds()


def bearing_degrees(latitude_start, longitude_start, latitude_end, longitude_end):
    """Calculate the forward azimuth between two points given decimal degrees."""
    latitude_start, longitude_start, latitude_end, longitude_end = map(
        math.radians, [latitude_start, longitude_start, latitude_end, longitude_end]
    )

    dlon = longitude_end - longitude_start

    y = math.sin(dlon) * math.cos(latitude_end)
    x = math.cos(latitude_start) * math.sin(latitude_end) - math.sin(
        latitude_start
    ) * math.cos(latitude_end) * math.cos(dlon)

    bearing = math.atan2(y, x)

    # Convert to degrees and normalize to 0-360
    bearing = math.degrees(bearing)
    bearing = (bearing + 360) % 360

    return bearing


def average_bearing(bearings):
    """Average bearings using vector method"""
    bearings_rad = np.radians(bearings)

    # Convert to unit vectors
    x = np.mean(np.cos(bearings_rad))
    y = np.mean(np.sin(bearings_rad))

    # Get average bearing
    avg_bearing = np.degrees(np.arctan2(y, x))
    return (avg_bearing + 360) % 360


def convert_to_decimal_degrees(degree: str, lon: bool = True) -> float:
    """
    Convert NMEA ddmm.mmmm / dddmm.mmmm strings into decimal degrees.

    Handles leading signs (e.g. "-0018.9046"), trailing direction letters
    ("5123.45S"), or legacy strings where the minus sign is embedded in the
    minutes portion (e.g. "000-18.9046").
    """
    if degree is None:
        raise ValueError("Invalid NMEA degree value: None")

    value = str(degree).strip()
    if not value:
        raise ValueError("Invalid NMEA degree value: empty string")

    sign = 1.0

    # Leading explicit sign
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

    degrees_val = float(degrees_str)
    minutes_val = float(minutes_val)

    return sign * (degrees_val + minutes_val / 60.0)


def decimal_to_dms_format(decimal_deg, is_lon=True):
    """Format decimal degrees into NMEA-style degrees/minutes."""
    sign = "-" if decimal_deg < 0 else ""
    absolute_deg = abs(decimal_deg)
    degrees = int(absolute_deg)
    minutes = (absolute_deg - degrees) * 60
    # Use 3 digits for longitudes of 100° or more, otherwise keep 2 to avoid
    # inserting an extra leading zero for small negative longitudes.
    width = 3 if is_lon and degrees >= 100 else 2
    return f"{sign}{degrees:0{width}d}{minutes:09.6f}"


def haversine(
    latitude_start: float,
    latitude_end: float,
    longitude_start: float,
    longitude_end: float,
    unit: Literal["nautical_miles", "kilometers"] = "nautical_miles",
) -> float:
    """
    Calculate the surface distance between two latitude/longitude pairs.

    Args:
        latitude_start: Starting latitude in decimal degrees.
        latitude_end: Ending latitude in decimal degrees.
        longitude_start: Starting longitude in decimal degrees.
        longitude_end: Ending longitude in decimal degrees.
        unit: The unit to express the result in; defaults to nautical miles.
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

    latitude_start = (latitude_start) * math.pi / 180.0
    latitude_end = (latitude_end) * math.pi / 180.0

    # Angle traced across surface
    theta = pow(math.sin(d_latitude / 2), 2) + pow(
        math.sin(d_longitude / 2), 2
    ) * math.cos(latitude_start) * math.cos(latitude_end)

    distance = earth_radius * 2 * math.asin(math.sqrt(theta))
    return distance
