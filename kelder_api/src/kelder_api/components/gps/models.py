from pydantic import BaseModel, computed_field, Field

from typing import Optional

from datetime import time

from src.kelder_api.components.gps.utils import nmea_to_dms


class GpsRedisData(BaseModel):
    timestamp: time = Field(description="Time stamp of the GPS measurement")
    latitude_nmea: float = Field(
        description='Latitude NMEA output: DDMM.MMMM ("Degrees, minutes, seconds")'
    )
    longitude_nmea: float = Field(
        description='Longitude NMEA output: DDDMM.MMMM ("Degrees, minutes, seconds")'
    )
    speed_over_ground: float = Field(description="Speed over ground in knots")

    @computed_field
    @property
    def redis_string(self) -> str:
        return f"{self.timestamp}|{self.latitude_nmea}|{self.longitude_nmea}|{self.speed_over_ground}"


class GpsMeasurementData(GpsRedisData):
    measurement_latency: float = Field(description = "Warning about GPS values")

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
