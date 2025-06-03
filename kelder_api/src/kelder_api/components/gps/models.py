from datetime import time
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field, computed_field

from src.kelder_api.components.gps.utils import nmea_to_dms


VELOCITY_THRESHOLD = 1.5  # speed exceeds 1.5 kts

class status(Enum):
    UNDER_WAY = "Under Way"
    STATIONARY = "Stationary"

class sleep_interval(Enum):
    UNDER_WAY = 1  # Seconds between samples
    STATIONARY = 5

class GpsRedisData(BaseModel):
    timestamp: time = Field(description="Time stamp of the GPS measurement")
    latitude_nmea: str = Field(
        description='Latitude NMEA output: DDMM.MMMM ("Degrees, minutes, seconds")'
    )
    longitude_nmea: str = Field(
        description='Longitude NMEA output: DDDMM.MMMM ("Degrees, minutes, seconds")'
    )
    instantaneous_speed_over_ground: float = Field(description="Speed over ground in knots")

    @computed_field
    @property
    def ships_status(self) -> status:
        if self.instantaneous_speed_over_ground > VELOCITY_THRESHOLD:
            return status.UNDER_WAY
        elif self.instantaneous_speed_over_ground <= VELOCITY_THRESHOLD:
            return status.STATIONARY


    @computed_field
    @property
    def redis_string(self) -> str:
        return f"{self.timestamp}|{self.latitude_nmea}|{self.longitude_nmea}|{self.instantaneous_speed_over_ground}"


class GpsMeasurementData(GpsRedisData):
    measurement_latency: float = Field(description="Warning about GPS values")
    average_speed_over_ground: Optional[float] = Field(description="Time average speed over ground in knots", default=None)

    @computed_field
    @property
    def latitude_fmt(self) -> str:
        return nmea_to_dms(self.latitude_nmea, is_latitude=True)

    @computed_field
    @property
    def longitude_fmt(self) -> str:
        return nmea_to_dms(self.longitude_nmea, is_latitude=False)


class GpsException(Exception):
    def __init__(self, msg):
        super().__init__(msg)
