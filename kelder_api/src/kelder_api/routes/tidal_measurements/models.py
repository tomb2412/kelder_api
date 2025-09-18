from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field


class TidalEvent(str, Enum):
    HIGH_WATER = "HighWater"
    LOW_WATER = "LowWater"


class TideInfo(BaseModel):
    """Model to store generic tidal data"""

    datetime_stamp: datetime = Field(description="Timestamp in UTC")
    height_of_tide: float = Field(description="Height of tide above CD in m")
    event: TidalEvent | None = Field(
        description="HW or LW, or not provided", default=None
    )
