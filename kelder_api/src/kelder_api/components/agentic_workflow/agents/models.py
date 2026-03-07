from datetime import datetime, timezone
from typing import List, Optional

from pydantic import BaseModel, Field, computed_field

from src.kelder_api.components.coordinate import Coordinate, bearing_degrees


class Waypoint(BaseModel):
    name: Optional[str] = Field(None, description="Name of the waypoint")
    coordinate: Coordinate = Field(description="Position of the waypoint in decimal degrees")


class PilotageInfo(BaseModel):
    departure: str = Field(..., description="Pilotage notes for departure harbour")
    arrival: str = Field(..., description="Pilotage notes for arrival harbour")


class PortOfRefuge(BaseModel):
    name: str = Field(..., description="Port name")
    coordinate: Coordinate = Field(..., description="Lat/Long coordinates of the port")


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
        """Haversine distances between consecutive waypoints in nautical miles."""
        distances = []
        for index in range(len(self.course_to_steer) - 1):
            wp_start = self.course_to_steer[index]
            wp_end = self.course_to_steer[index + 1]
            distances.append(wp_start.coordinate - wp_end.coordinate)
        return distances

    @computed_field
    @property
    def bearing_between_waypoints(self) -> List[float]:
        """Forward azimuth bearings between consecutive waypoints in degrees."""
        bearings = []
        for index in range(len(self.course_to_steer) - 1):
            wp_start = self.course_to_steer[index]
            wp_end = self.course_to_steer[index + 1]
            bearings.append(
                bearing_degrees(
                    latitude_start=wp_start.coordinate.latitude,
                    longitude_start=wp_start.coordinate.longitude,
                    latitude_end=wp_end.coordinate.latitude,
                    longitude_end=wp_end.coordinate.longitude,
                )
            )
        return bearings
