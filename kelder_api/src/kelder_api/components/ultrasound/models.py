from datetime import datetime

from pydantic import BaseModel, Field


class BilgeDepth(BaseModel):
    timestamp: datetime = Field(description="Timestamp of the distance measurement")
    bilge_depth: float | None = Field(description="The depth of the reading")
