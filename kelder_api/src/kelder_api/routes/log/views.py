import logging
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Request

from src.kelder_api.app.getters import get_log_tracker
from src.kelder_api.components.log.models import JourneyData
from src.kelder_api.components.log.service import LogTracker

logger = logging.getLogger(__name__)

router = APIRouter(tags=["LOG"])


def get_dependancy(request: Request) -> LogTracker:
    return get_log_tracker(request.app)


@router.get("/get_journey")
async def getCurrentJourney(
    log_tracker: LogTracker = Depends(get_dependancy),
    datetime: datetime = datetime.now(timezone.utc)
) -> JourneyData:
    logger.info("Current journey request recieved.")
    return await log_tracker.get_journey_set(datetime)
