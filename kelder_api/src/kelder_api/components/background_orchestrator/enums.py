from enum import Enum


class VesselState(str, Enum):
    UNDERWAY = "underway"
    STATIONARY = "stationary"

    # Other states could include anchored, moored, home
