import logging
from http import HTTPStatus

from fastapi import APIRouter, Depends, HTTPException, Request

from src.kelder_api.app.getters import get_db_manager
from src.kelder_api.components.db_manager.models import JourneyHistoryRecord
from src.kelder_api.components.db_manager.service import DBManager
from src.kelder_api.routes.db_manager.models import JourneyHistory

logger = logging.getLogger("api.routes.db_manager")

router = APIRouter(tags=["DB Manager"])


def get_dependancy(request: Request) -> DBManager:
    return get_db_manager(request.app)


@router.get("/journeys/latest", response_model=JourneyHistory)
async def get_latest_journey(
    db_manager: DBManager = Depends(get_dependancy),
    limit: int | None = None,
) -> JourneyHistory:
    logger.info("Request received for journey history")
    latest_journey = db_manager.list_trips()
        
    if latest_journey is None:
        raise HTTPException(
            status_code=HTTPStatus.NOT_FOUND,
            detail="No journey history available",
        )
    
    else: 
        for journey in latest_journey[:limit]:
            journey.gps_data = "[]"
    
    return JourneyHistory(journeys=latest_journey[:limit], limit = len(latest_journey))
