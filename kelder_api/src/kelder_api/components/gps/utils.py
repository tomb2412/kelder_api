import math
from datetime import datetime
from typing import List, Tuple

EARTH_RADUIS = 6371


def nmea_to_dms(nmea_val, is_latitude=True) -> str:
    """
    Utility to support human readable conversion from nmea gps DDMM.MMM to Degrees, Minutes, Seconds
    """
    if is_latitude:
        degrees = int(float(nmea_val) // 100)
        minutes_full = float(nmea_val) - (degrees * 100)
    else:
        degrees = int(float(nmea_val) // 100)
        minutes_full = float(nmea_val) - (degrees * 100)

    minutes = int(minutes_full)
    seconds = (minutes_full - minutes) * 60

    return "%+03d°%02d′%04.2f″" % (degrees, minutes, seconds)


def time_elapsed_seconds(time_str: datetime) -> datetime:
    """
    Method to calulate the time difference from the last successful reading
    """
    now = datetime.now()
    parsed_time = time_str.replace(year=now.year, month=now.month, day=now.day)

    time_elapsed_seconds = time_difference_seconds(parsed_time, now)
    return time_elapsed_seconds


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


def convert_to_decimal_degrees(lat_or_long: str) -> float:
    """
    This only supports northern hemisphere calculations
    """
    lat_or_long = lat_or_long.zfill(10)
    return float(lat_or_long[0:2]) + float(lat_or_long[2:]) / 60


def haversine(latitude_start: str, latitude_end: str, longitude_start: str, longitude_end: str) -> float:
    latitude_start = convert_to_decimal_degrees(latitude_start)
    latitude_end = convert_to_decimal_degrees(latitude_end)
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


def gps_velocity(gps_history_raw: List[str]) -> Tuple[float, float, float]:
    """
    Method to calculate the speed over ground from gps measurements
    """

    time_start = gps_history_raw[0][0]
    latitude_start = gps_history_raw[0][1]
    longitude_start = gps_history_raw[0][2]

    time_end = gps_history_raw[-1][0]
    latitude_end = gps_history_raw[-1][1]
    longitude_end = gps_history_raw[-1][2]

    distance = haversine(latitude_start, latitude_end, longitude_start, longitude_end)
    time = time_difference_seconds(
        parse_timestamp(time_start), parse_timestamp(time_end)
    )

    try:
        speed_over_ground = distance / time
    except ZeroDivisionError:
        speed_over_ground = 0

    return speed_over_ground
