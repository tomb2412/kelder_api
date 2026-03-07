from datetime import time

from pydantic import BaseModel, Field

from src.kelder_api.components.coordinate import Coordinate


class GPSCard(BaseModel):
    timestamp: time | str = Field(description="The time the GPS measurement was taken")
    coordinate: Coordinate = Field(description="Current vessel position")
    speed_over_ground: float | str = Field(description="speed over ground  / knts")
    log: float | str = Field(
        description="The distance travelled in current trip nautical miles"
    )
    drift: float | None = Field(
        description=(
            "Component of velocity perpendicular to heading / knts "
            "or None if stationary"
        )
    )
    dtw: float = Field(
        description="The distance to the next waypoint / nautical miles", default=4.7
    )


class GPSMap(BaseModel):
    coordinate: Coordinate = Field(description="Current vessel position in decimal degrees")
    cog: str = Field(description="The cog from the velocity")
    track: list[dict] | None = Field(
        default=None,
        description="Full journey track as decimal degree points with timestamps",
    )
