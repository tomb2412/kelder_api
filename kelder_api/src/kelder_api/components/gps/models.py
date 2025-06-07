from datetime import time, datetime
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field, computed_field

from src.kelder_api.components.gps.utils import nmea_to_dms, haversine

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

class GpsMeasurementViewData(GpsRedisData):
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

    log_distance: float = Field(description="The distance over ground travelled in nm so far")
    log_start_time: datetime = Field(description="The time the ships status has been underway")

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

class GpsMeasurementBackgroundData(GpsRedisData):
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

    log_distance: float = Field(description="The distance over ground travelled in nm so far")
    log_start_time: datetime = Field(description="The time the ships status has been underway")

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

class LogDistanceUnderWay(BaseModel):
    current_latitude_nmea: str = Field(description="The previous nmea latutiude")
    current_longitude_nmea: str = Field(description="The previous nmea longitude")
    previous_latitude_nmea: str = Field(description="The previous nmea latutiude")
    previous_longitude_nmea: str = Field(description="The previous nmea longitude")

    previous_log: float = Field(description="The distance travelled whilst underway")
    ships_status: status = Field(description="The ships motion status to control when to reset the logs")

    @computed_field
    @property
    def log_distance_under_way(self) -> float:
        if self.ships_status==status.UNDER_WAY:
            return haversine(
                self.previous_latitude_nmea,
                self.previous_longitude_nmea,
                self.latitude_nmea,
                self.longitude_nmea
            )
