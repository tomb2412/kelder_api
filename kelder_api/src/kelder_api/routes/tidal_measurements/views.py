import logging
from datetime import datetime, timezone

from fastapi import APIRouter

from src.kelder_api.routes.tidal_measurements.tidal_clients import (
    get_height_of_tide_now,
    get_tide_predictions,
)

THREE_HOURS_IN_SECONDS = 10800

logger = logging.getLogger("core status")
router = APIRouter(tags=["Tidal Information"])


@router.get("/get_height_of_tide")
async def get_height_of_tide():
    logger.debug("Height of tide requested")
    return await get_height_of_tide_now()


@router.get("/get_tidal_predictions")
async def get_tidal_events():
    logger.debug("Tideal predictions requested")
    return await get_tide_predictions(datetime.now(timezone.utc).date())


@router.get("/get_next_tidal_event")
async def get_next_tidal_event():
    logger.debug("Next highwater")
    now = datetime.now(timezone.utc)
    tidal_events = await get_tide_predictions(now.date())

    for tidal_event in tidal_events:
        if (
            abs((tidal_event.datetime_stamp - now).total_seconds())
            <= THREE_HOURS_IN_SECONDS
        ):
            return tidal_event

    # TODO: what to return or raise?
    return {}
