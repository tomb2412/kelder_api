from datetime import datetime

from pydantic import BaseModel, Field, computed_field

from src.kelder_api.components.velocity.utils import (
    convert_to_decimal_degrees,
    haversine,
)


class LegData(BaseModel):
    """Track the start metadata of a tack and the most recent course over ground."""

    start_datetime: datetime = Field(description="The start datetime of the leg")
    start_latitude: str = Field(description="The lat and lon of the leg start coords")
    start_longitude: str = Field(description="The lat and lon of the leg start coords")
    course_over_ground: float = Field(
        description="The average cog (from gps) of the boat for tack detection"
    )


class JourneyData(BaseModel):
    timestamp: datetime = Field(
        description="The start datetime of the journey, named follows redis convention"
    )
    end_datetime: datetime = Field(description="The end datetime of the journey")
    start_latitude: str = Field(description="The lat and lon of the leg start coords")
    start_longitude: str = Field(description="The lat and lon of the leg start coords")
    end_latitude: str = Field(description="The lat and lon of the leg end coords")
    end_longitude: str = Field(description="The lat and lon of the leg end coords")
    gps_data: str = Field(
        description="The complete gps track for the journey.", default="[]"
    )

    @computed_field
    @property
    def distance_travelled(self) -> float:
        latitude_start = convert_to_decimal_degrees(self.start_latitude)
        longitude_start = convert_to_decimal_degrees(self.start_longitude)
        latitude_end = convert_to_decimal_degrees(self.end_latitude)
        longitude_end = convert_to_decimal_degrees(self.end_longitude)

        return round(
            haversine(latitude_start, latitude_end, longitude_start, longitude_end), 2
        )
