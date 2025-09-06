from enum import Enum


class GPSStatus(str, Enum):
    ACTIVE = "A"
    VOID = "V"


class LatitudeHemisphere(str, Enum):
    NORTH = "N"
    SOUTH = "S"


class LongitudeHemisphere(str, Enum):
    WEST = "W"
    EAST = "E"
