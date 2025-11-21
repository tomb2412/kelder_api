from enum import Enum

from pydantic import BaseModel, Field
from datetime import datetime, timezone


class VesselState(str, Enum):
    UNDERWAY = "underway"
    STATIONARY = "stationary"

    # Other states could include anchored, moored, home


class VesselStateModel(BaseModel):
    timestamp: datetime = Field(default=datetime.now(tz=timezone.utc))
    vessel_state: VesselState