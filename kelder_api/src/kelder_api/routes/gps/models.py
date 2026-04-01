from datetime import time

from pydantic import BaseModel, Field


class GPSCard(BaseModel):
    timestamp: time | str = Field(description="The time the GPS measurement was taken")
    latitude: str = Field(description="The latitude in degrees ° minutes \" seconds '")
    longitude: str = Field(
        description="The longitude in degrees ° minutes \" seconds '"
    )
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
    dtw: float | None = Field(
        default=None,
        description="The distance to the next waypoint / nautical miles",
    )

class GPSMap(BaseModel):
    longitude: str = Field(description="decimal degrees")
    latitude: str = Field(description="decimal degrees")
    cog: str = Field(description = "The cog from the velocity")
    track: list[dict] | None = Field(
        default=None,
        description="Full journey track as decimal degree points with timestamps",
    )
