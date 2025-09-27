from pydantic import BaseModel, Field

from datetime import time

class GPSCard(BaseModel):
    timestamp: time | str = Field(description="The time the GPS measurement was taken")
    latitude: str = Field(description="The latitude in degrees ° minutes \" seconds \'")
    longitude: str = Field(description="The longitude in degrees ° minutes \" seconds \'")
    speed_over_ground: float = Field(description="speed over ground  / knts")
    log: float = Field(description="The distance travelled in current trip nautical miles")
    # TODO Remove these defaults and insert real figures
    drift: float = Field(description="Component of velocity perpendicular to heading / knts", defualt = 1.2)
    dtw: float = Field(description="The distance to the next waypoint / nautical miles", default = 4.7)
