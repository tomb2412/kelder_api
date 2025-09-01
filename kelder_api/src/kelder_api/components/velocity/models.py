from pydantic import BaseModel, Field
from datetime import datetime
from enum import Enum

class CalculationType(str, Enum):
    LENGTH = "length"
    TIMESERIES = "timeseries"


class GPSVelocity(BaseModel):
    """Output from the velocity calculation"""
    timestamp: datetime = Field(description="Timestamp from when the velocity was taken")
    speed_over_ground: float | None = Field(description="Average SOG over ground in knots. None if unreliable data identified")
    course_over_ground: float | None = Field(description="The average bearing from True north of the gps course in degreed")
    number_of_measurements: int = Field(description="datapoint count used in calculation")