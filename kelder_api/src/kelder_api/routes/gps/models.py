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
    drift: float = Field(
        description="Component of velocity perpendicular to heading / knts", default=1.2
    )
    dtw: float = Field(
        description="The distance to the next waypoint / nautical miles", default=4.7
    )
