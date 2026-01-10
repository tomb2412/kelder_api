import logging
from datetime import datetime, timezone
from http import HTTPStatus

from fastapi import APIRouter, Depends, HTTPException, Request

from src.kelder_api.app.getters import get_log_tracker
from src.kelder_api.components.log.models import JourneyData
from src.kelder_api.components.log.service import LogTracker

logger = logging.getLogger("api.routes.log")

router = APIRouter(tags=["LOG"])


def get_dependancy(request: Request) -> LogTracker:
    return get_log_tracker(request.app)


@router.get("/get_journey")
async def getCurrentJourney(
    log_tracker: LogTracker = Depends(get_dependancy),
    datetime: datetime = datetime.now(timezone.utc),
) -> JourneyData:
    logger.info("Current journey request recieved.")
    journey_data = await log_tracker.get_journey_set(datetime)

    if journey_data:
        return journey_data
    else:
        raise HTTPException(
            status_code=HTTPStatus.NOT_FOUND, detail="No data in the set"
        )
