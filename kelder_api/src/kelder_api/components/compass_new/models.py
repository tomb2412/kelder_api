from datetime import datetime

from pydantic import BaseModel, Field


class CompassRedisData(BaseModel):
    timestamp: datetime = Field(description="Timestamp taken of the measurement")
    heading: float | None = Field(description="Bearing in degrees from true north")
