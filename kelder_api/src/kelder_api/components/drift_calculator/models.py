from datetime import datetime

from pydantic import BaseModel, Field

class DriftData(BaseModel):
    timestamp: datetime = Field(description="Timestamp taken of the measurement")
    drift_speed: float | None = Field(description="Knots perpendicular to direction of motion")