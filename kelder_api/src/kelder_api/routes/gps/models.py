from datetime import time

from pydantic import BaseModel, Field

from src.kelder_api.components.gps_new.types import GPSStatus


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
    xte: float | None = Field(
        default=None,
        description=(
            "Cross track error from the current leg / nautical miles, "
            "positive to starboard of the track"
        ),
    )
    next_waypoint: str | None = Field(
        default=None,
        description="Name of the active waypoint being steered to",
    )
    next_waypoint_number: int | None = Field(
        default=None,
        description="Position of the active waypoint in the route, starting at 1",
    )
    fix_status: GPSStatus | None = Field(
        default=None,
        description=(
            "Status of the most recent GPS reading (A = fix, V = no fix). The "
            "position fields always come from the last reading with a fix."
        ),
    )
    satellites: int | None = Field(
        default=None,
        description="Number of satellites used in the most recent reading",
    )
    hdop: float | None = Field(
        default=None,
        description="Horizontal dilution of precision of the most recent reading",
    )


class GPSMap(BaseModel):
    longitude: str = Field(description="decimal degrees")
    latitude: str = Field(description="decimal degrees")
    cog: str = Field(description="The cog from the velocity")
    track: list[dict] | None = Field(
        default=None,
        description="Full journey track as decimal degree points with timestamps",
    )
