from pydantic import BaseModel, Field

from src.kelder_api.components.db_manager.models import JourneyHistoryRecord


class JourneyHistory(BaseModel):
    journeys: list[JourneyHistoryRecord] = Field(
        description="Journey data sent to the passage history ui."
    )
    limit: int = Field(description="The number of journeys total.")
