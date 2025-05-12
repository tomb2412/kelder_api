from datetime import datetime
from typing import List, Tuple


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
    time_format = "%H:%M:%S+00:00"

    now = datetime.now()

    parsed_time = datetime.strptime(time_str, time_format)
    parsed_time = parsed_time.replace(year=now.year, month=now.month, day=now.day)

    time_elapsed_seconds = (now - parsed_time).total_seconds()

    return time_elapsed_seconds


def gps_velocity(gps_history_raw: List[str]) -> Tuple[float, float, float]:
    time_start = gps_history_raw[0][0]
    lat_start = gps_history_raw[0][1]
    long_start = gps_history_raw[0][2]

    time_end = gps_history_raw[4][0]
    lat_end = gps_history_raw[4][1]
    long_end = gps_history_raw[4][2]

    # TO FINISH....
