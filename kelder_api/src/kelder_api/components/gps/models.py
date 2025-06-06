from datetime import time
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field, computed_field

from src.kelder_api.components.gps.utils import nmea_to_dms

from src.kelder_api.configuration.settings import Settings


class status(Enum):
    UNDER_WAY = "Under Way"
    STATIONARY = "Stationary"


class GpsRedisData(BaseModel):
    """
    Containing GPS data from a single measurement
    """

    timestamp: time = Field(description="Time stamp of the GPS measurement")
    latitude_nmea: str = Field(
        description='Latitude NMEA output: DDMM.MMMM ("Degrees, minutes, seconds")'
    )
    longitude_nmea: str = Field(
        description='Longitude NMEA output: DDDMM.MMMM ("Degrees, minutes, seconds")'
    )
    instantaneous_speed_over_ground: float = Field(
        description="Speed over ground in knots"
    )

    @computed_field
    @property
    def redis_string(self) -> str:
        return f"{self.timestamp}|{self.latitude_nmea}|{self.longitude_nmea}|{self.instantaneous_speed_over_ground}"


class GpsMeasurementData(GpsRedisData):
    """
    Containing GPS data to be sent in a request, read from Redis
    """

    measurement_latency: float = Field(description="Warning about GPS values")
    average_speed_over_ground: Optional[float] = Field(
        description="Time average speed over ground in knots", default=None
    )
    quality_flag: Optional[bool] = Field(
        description="A flag to raise concerns over the quality of response data"
    )

    @computed_field
    @property
    def latitude_fmt(self) -> str:
        return nmea_to_dms(self.latitude_nmea, is_latitude=True)

    @computed_field
    @property
    def longitude_fmt(self) -> str:
        return nmea_to_dms(self.longitude_nmea, is_latitude=False)

    @computed_field
    @property
    def ships_status(self) -> status:
        if abs(self.average_speed_over_ground) > Settings().gps.velocity_threshold:
            return status.UNDER_WAY
        elif abs(self.average_speed_over_ground) <= Settings().gps.velocity_threshold:
            return status.STATIONARY


class GpsException(Exception):
    def __init__(self, msg):
        super().__init__(msg)
