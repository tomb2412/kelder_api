from datetime import datetime

import numpy as np


def parse_timestamp(time: str) -> datetime:
    """Parse a GPS timestamp string in ``HH:MM:SS+00:00`` format."""
    return datetime.strptime(time, "%H:%M:%S+00:00")


def time_difference_seconds(time_start: datetime, time_end: datetime) -> float:
    """Elapsed seconds between two timestamps."""
    return (time_end - time_start).total_seconds()


def average_bearing(bearings) -> float:
    """Circular mean of a sequence of bearings using the unit-vector method."""
    bearings_rad = np.radians(bearings)
    x = np.mean(np.cos(bearings_rad))
    y = np.mean(np.sin(bearings_rad))
    return (np.degrees(np.arctan2(y, x)) + 360) % 360
