from datetime import datetime

from pydantic import BaseModel


class PassagePlanProgress(BaseModel):
    timestamp: datetime
    distance_to_waypoint: float | None  # nautical miles
    next_waypoint_name: str | None
    next_waypoint_index: int | None
    # nautical miles from the current leg, positive to starboard of the track
    cross_track_error: float | None = None
