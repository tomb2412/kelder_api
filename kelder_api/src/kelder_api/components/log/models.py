from datetime import datetime
from typing import List

from pydantic import BaseModel, Field, computed_field

from src.kelder_api.components.velocity.utils import (
    convert_to_decimal_degrees,
    haversine,
)


class LegData(BaseModel):
    """The leg tracks the start time and position of a tack, and the last COG. All GPS for consistancy"""

    start_datetime: datetime = Field(description="The start datetime of the leg")
    start_coords: List[str] = Field(
        description="The lat and lon of the leg start coords"
    )
    course_over_ground: float = Field(
        description="The average cog (from gps) of the boat for tack detection"
    )


class JourneyData(BaseModel):
    timestamp: datetime = Field(
        description="The start datetime of the journey, named follows redis convention"
    )
    end_datetime: datetime = Field(description="The end datetime of the journey")
    start_coords: List[str] = Field(
        description="The lat and lon of the leg start coords"
    )
    end_coords: List[str] = Field(description="The lat and lon of the leg start coords")

    @computed_field
    @property
    def disance_travelled(self) -> float:
        latitude_start = convert_to_decimal_degrees(self.start_coords[0])
        longitude_start = convert_to_decimal_degrees(self.start_coords[1])
        latitude_end = convert_to_decimal_degrees(self.end_coords[0])
        longitude_end = convert_to_decimal_degrees(self.end_coords[1])

        return haversine(latitude_start, latitude_end, longitude_start, longitude_end)
