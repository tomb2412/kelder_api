from pydantic import BaseModel, Field


class CompassCard(BaseModel):
    heading: float | None = Field(
        description="Compass bearing in degrees; None when unavailable"
    )
    course_over_ground: float | None = Field(
        description="Average GPS course over ground in degrees; None when unavailable"
    )
