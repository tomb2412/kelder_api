import math
import numpy as np
from datetime import datetime

EARTH_RADUIS = 6371


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
    """Calculate initial bearing (forward azimuth) from point 1 to point 2. Coords in DD.DD"""
    latitude_start, longitude_start, latitude_end, longitude_end = map(math.radians, [latitude_start, longitude_start, latitude_end, longitude_end])
    
    dlon = longitude_end - longitude_start
    
    y = math.sin(dlon) * math.cos(latitude_end)
    x = math.cos(latitude_start) * math.sin(latitude_end) - math.sin(latitude_start) * math.cos(latitude_end) * math.cos(dlon)
    
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
    This only supports northern hemisphere calculations. 
    if lon = TRUE: The coversion is for longitude DDDMM.MMM -> DD.DDDD
    if lon = FALSE: The conversion is for latitude DDMM.MMM
    """
    degree = degree.zfill(10)
    if lon:
        return float(degree[0:3]) + float(degree[3:]) / 60
    else:
        return float(degree[0:2]) + float(degree[2:]) / 60

def haversine(
    latitude_start: str, latitude_end: str, longitude_start: str, longitude_end: str
) -> float:
    """Requires a DD.DD format"""
    d_latitude = (latitude_end - latitude_start) * math.pi / 180
    d_longitude = (longitude_end - longitude_start) * math.pi / 180

    latitude_start = (latitude_start) * math.pi / 180.0
    latitude_end = (latitude_end) * math.pi / 180.0

    # Angle traced across surface
    theta = pow(math.sin(d_latitude / 2), 2) + pow(
        math.sin(d_longitude / 2), 2
    ) * math.cos(latitude_start) * math.cos(latitude_end)

    distance = EARTH_RADUIS * 2 * math.asin(math.sqrt(theta))
    return distance
