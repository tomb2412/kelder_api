from enum import StrEnum


class RedisSetNames(StrEnum):
    GPS = "GPS"
    COMPASS = "COMPASS"
    VELOCITY = "VELOCITY"
    LOG = "LOG"
    DRIFT = "DRIFT"
    BILGE_DEPTH = "BILGE_DEPTH"
    PASSAGE_PLAN = "PASSAGE_PLAN"
    VESSEL_STATE = "VESSEL_STATE"
    JOURNEY = "JOURNEY"
    LEG = "LEG"
