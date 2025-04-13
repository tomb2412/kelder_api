from pydantic import BaseModel, computed_field, Field

from datetime import datetime

class GpsMeasurementData(BaseModel):
    timestamp: datetime = Field(description="Time stamp of the GPS measurement")

    latitude_nmea: float = Field(description="Latitude NMEA output: DDDMM.MMMM (\"Degrees, minutes, seconds\")")
    latitude_dec: float = Field(description= "Latitude in decimal representation")
    latitude_fmt: str = Field(description = "Latitude string formatted output \"DD°MM′SS.SSSS″\"")

    longitude_nmea: float = Field(description="Longitude NMEA output: DDDMM.MMMM (\"Degrees, minutes, seconds\")")
    longitude_dec: float = Field(description= "Longitude in decimal representation")
    longitude_fmt: str = Field(description = "Longitude string formatted output \"DD°MM′SS.SSSS″\"")

    speed_over_ground: float = Field(description= "Speed over ground in knots")

    true_course: float = Field(description = "True course")
    magnetic_variation_absolute: float = Field(description="Magnetic variation")
    magnetic_variation_direction: str = Field(decription="Direction of magnetic variation")
    #Computed field for heading here
    
class GpsException(Exception):
    def __init__(self, msg):
        self.super(msg)
