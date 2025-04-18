from pydantic import BaseModel, computed_field, Field

from typing import Optional

from datetime import time

class GpsRedisData(BaseModel):
    timestamp: time = Field(description="Time stamp of the GPS measurement")
    latitude_nmea: float = Field(description="Latitude NMEA output: DDDMM.MMMM (\"Degrees, minutes, seconds\")")
    longitude_nmea: float = Field(description="Longitude NMEA output: DDDMM.MMMM (\"Degrees, minutes, seconds\")")
    speed_over_ground: float = Field(description= "Speed over ground in knots")

    @computed_field
    @property
    def redis_string(self)->str:
        return f"{self.timestamp}:{self.latitude_nmea}:{self.longitude_nmea}"

class GpsMeasurementData(GpsRedisData):
    latitude_dec: float = Field(description= "Latitude in decimal representation")
    latitude_fmt: str = Field(description = "Latitude string formatted output \"DD°MM′SS.SSSS″\"")

    longitude_dec: float = Field(description= "Longitude in decimal representation")
    longitude_fmt: str = Field(description = "Longitude string formatted output \"DD°MM′SS.SSSS″\"")

    #Computed field for heading here
    
class GpsException(Exception):
    def __init__(self, msg):
        super().__init__(msg)
