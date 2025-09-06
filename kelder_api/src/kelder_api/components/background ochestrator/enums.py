from enum import Enum


class VesselState(Enum, str):
    UNDERWAY = "underway"
    STATIONARY = "stationary"

    # Other states could include anchored, moored, home
