from datetime import datetime, timezone
from typing import List, Optional

from pydantic import BaseModel, Field, computed_field

from src.kelder_api.components.velocity.utils import (
    bearing_degrees,
    haversine,
)


class Waypoint(BaseModel):
    name: Optional[str] = Field(None, description="Name of the waypoint")
    latitude: float = Field(description=("Latitude of waypoint in decimal degrees"))
    latitude_hemisphere: str = Field(
        description="North or south hemisphere e.g 'N' or 'S'", default="N"
    )
    longitude: float = Field(
        description=("Longitude of waypoinfloatt in decimal degrees")
    )
    longitude_hemisphere: str = Field(
        description="East or west hemisphere of longitude", default="W"
    )

    # @computed_field
    # @property
    # def latitude(self) -> float:
    #     return convert_to_decimal_degrees(self.latitude)

    # @computed_field
    # @property
    # def longitude(self) -> float:
    #     return convert_to_decimal_degrees(self.longitude)


class PilotageInfo(BaseModel):
    departure: str = Field(..., description="Pilotage notes for departure harbour")
    arrival: str = Field(..., description="Pilotage notes for arrival harbour")


class PortOfRefuge(BaseModel):
    name: str = Field(..., description="Port name")
    coordinates: str = Field(..., description="Lat/Long coordinates")


class PassagePlan(BaseModel):
    timestamp: datetime = Field(
        description="The timestamp the passage plan was created",
        default=datetime.now(tz=timezone.utc),
    )
    departure_place_name: str = Field(
        ..., description="Place of departure for the passage plan, e.g. 'Cowes'"
    )
    desination_place_name: str = Field(
        ..., description="Desination of the passage plan, e.g. 'Southampton'"
    )
    course_to_steer: List[Waypoint] = Field(
        ..., description="List of waypoints forming the course to steer"
    )

    @computed_field
    @property
    def distance_between_waypoints(self) -> List[float]:
        """Compute haversine distances between consecutive waypoints."""
        distances = []
        for index in range(len(self.course_to_steer) - 1):
            waypoint_start = self.course_to_steer[index]
            waypoint_end = self.course_to_steer[index + 1]
            distances.append(
                haversine(
                    latitude_start=waypoint_start.latitude,
                    latitude_end=waypoint_end.latitude,
                    longitude_start=waypoint_start.longitude,
                    longitude_end=waypoint_end.longitude,
                )
            )

        return distances

    @computed_field
    @property
    def bearing_between_waypoints(self) -> List[float]:
        """Calculate bearings between consecutive waypoints."""
        bearings = []
        for index in range(len(self.course_to_steer) - 1):
            waypoint_start = self.course_to_steer[index]
            waypoint_end = self.course_to_steer[index + 1]
            bearings.append(
                bearing_degrees(
                    latitude_start=waypoint_start.latitude,
                    longitude_start=waypoint_start.longitude,
                    latitude_end=waypoint_end.latitude,
                    longitude_end=waypoint_end.longitude,
                )
            )

        return bearings
