import math
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
    latitude_start = convert_to_decimal_degrees(latitude_start, lon=False)
    latitude_end = convert_to_decimal_degrees(latitude_end, lon=False)
    longitude_start = convert_to_decimal_degrees(longitude_start)
    longitude_end = convert_to_decimal_degrees(longitude_end)

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
