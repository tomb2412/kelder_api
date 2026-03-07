from datetime import datetime

from pydantic import BaseModel, Field, computed_field

from src.kelder_api.components.coordinate import Coordinate


class LegData(BaseModel):
    """Track the start metadata of a tack and the most recent course over ground."""

    start_datetime: datetime = Field(description="The start datetime of the leg")
    start_coordinate: Coordinate = Field(description="Position at the start of the leg")
    course_over_ground: float = Field(
        description="The average cog (from gps) of the boat for tack detection"
    )


class JourneyData(BaseModel):
    timestamp: datetime = Field(
        description="The start datetime of the journey, named follows redis convention"
    )
    end_datetime: datetime = Field(description="The end datetime of the journey")
    start_coordinate: Coordinate = Field(description="Position at journey departure")
    end_coordinate: Coordinate = Field(description="Position at journey end")
    gps_data: str = Field(
        description="The complete gps track for the journey.", default="[]"
    )

    @computed_field
    @property
    def distance_travelled(self) -> float:
        return round(self.start_coordinate - self.end_coordinate, 2)
