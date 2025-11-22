import logging
from http import HTTPStatus

from fastapi import APIRouter, Depends, HTTPException, Request

from src.kelder_api.app.getters import get_db_manager
from src.kelder_api.components.db_manager.models import JourneyHistoryRecord
from src.kelder_api.components.db_manager.service import DBManager

logger = logging.getLogger(__name__)

router = APIRouter(tags=["DB Manager"])


def get_dependancy(request: Request) -> DBManager:
    return get_db_manager(request.app)


@router.get("/journeys/latest", response_model=JourneyHistoryRecord)
async def get_latest_journey(
    db_manager: DBManager = Depends(get_dependancy),
) -> JourneyHistoryRecord:
    logger.info("Request received for latest journey history record")
    latest_journey = db_manager.latest_trip()

    if latest_journey is None:
        raise HTTPException(
            status_code=HTTPStatus.NOT_FOUND,
            detail="No journey history available",
        )

    return latest_journey
