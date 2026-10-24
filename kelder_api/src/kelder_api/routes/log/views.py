from datetime import datetime, timezone
from http import HTTPStatus

from fastapi import APIRouter, Depends, HTTPException, Query, Request

from src.kelder_api.app.getters import get_db_manager, get_log_tracker
from src.kelder_api.components.db_manager.service import DBManager
from src.kelder_api.components.log.models import JourneyData
from src.kelder_api.components.log.service import LogTracker
from src.kelder_api.configuration.logging_controller import get_logger

logger = get_logger(__name__, "routes.log")

router = APIRouter(tags=["LOG"])


def get_dependancy(request: Request) -> LogTracker:
    return get_log_tracker(request.app)


def get_db_dependancy(request: Request) -> DBManager:
    return get_db_manager(request.app)


@router.get("/get_journey")
async def getCurrentJourney(
    log_tracker: LogTracker = Depends(get_dependancy),
    db_manager: DBManager = Depends(get_db_dependancy),
    timestamp: datetime | None = Query(default=None, alias="datetime"),
) -> JourneyData:
    logger.info("Current journey request recieved.")
    if timestamp is None or timestamp.date() >= datetime.now(timezone.utc).date():
        journey_data = await log_tracker.get_journey_set(timestamp)
    else:
        record = db_manager.latest_trip_on(timestamp.date())
        journey_data = JourneyData.from_history_record(record) if record else None

    if journey_data:
        return journey_data
    else:
        raise HTTPException(
            status_code=HTTPStatus.NOT_FOUND, detail="No data in the set"
        )
