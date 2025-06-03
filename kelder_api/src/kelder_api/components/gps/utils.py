from datetime import datetime
from typing import List, Tuple, Union
import math as m

EARTH_RADUIS = 6371

def nmea_to_dms(nmea_val, is_latitude=True) -> str:
    if is_latitude:
        degrees = int(nmea_val // 100)
        minutes_full = nmea_val - (degrees * 100)
    else:
        degrees = int(nmea_val // 100)
        minutes_full = nmea_val - (degrees * 100)

    minutes = int(minutes_full)
    seconds = (minutes_full - minutes) * 60

    return "%+03d°%02d′%04.2f″" % (degrees, minutes, seconds)


def time_elapsed_seconds(time_str: str) -> datetime:
    # Method to calulate the time difference from the last successful reading
    now = datetime.now()
    parsed_time = parse_timestamp(time_str, now)

    time_elapsed_seconds = time_difference_seconds(parsed_time, now)

    return time_elapsed_seconds

def parse_timestamp(time: str, now: Union[None, datetime] = None) -> datetime:
    """
    Method to parse the gps timestamp as string

    args:
        date_now
    """
    time_format = "%H:%M:%S+00:00"

    parsed_time = datetime.strptime(time_str, time_format)
    
    if now:
        parsed_time = parsed_time.replace(year=now.year, month=now.month, day=now.day)

    return parsed_time

def time_difference_seconds(time_start: datetime, time_end: datetime) -> datetime:
    # Method to return the seconds between two time stamps
    return (time_end - time_start).total_seconds()

def haversine(latitude_start, latitude_end, longitude_start, longitude_end) -> int:
    d_latitude = (latitude_end - latitude_start) * m.pi/180
    d_longitude = (longitude_end - longitude_start) * m.pi/180

    latitude_start = (latitude_start) * m.pi / 180.0
    latitude_end = (latitude_end) * m.pi / 180.0

    # Angle traced across surface
    theta = (pow(m.sin(d_latitude / 2), 2) + 
         pow(m.sin(d_longitude / 2), 2) * 
             m.cos(latitude_start) * m.cos(latitude_end))

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
    time = time_difference_seconds(time_start, time_end)

    speed_over_ground = distance/time

    return speed_over_ground