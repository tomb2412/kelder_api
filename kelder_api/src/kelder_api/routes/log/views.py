import logging
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, Request

from src.kelder_api.components.log.service import LogTracker
from src.kelder_api.components.log.models import JourneyData
from src.kelder_api.app.getters import get_log_tracker

logger = logging.getLogger(__name__)

router = APIRouter(tags=["LOG"])


def get_dependancy(request: Request) -> LogTracker:
    return get_log_tracker(request.app)


@router.get("/get_current_journey")
async def getCurrentJourney(
    log_tracker: LogTracker = Depends(get_log_tracker),
) -> JourneyData:
    logger.info("Current journey request recieved.")
    return log_tracker.journey_data
