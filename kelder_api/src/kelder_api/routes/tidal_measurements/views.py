import logging
from fastapi import APIRouter
from datetime import datetime

from src.kelder_api.routes.tidal_measurements.tidal_clients import (
    get_height_of_tide_now,
    get_tide_predictions
)

logger = logging.getLogger("core status")
router = APIRouter(tags=["Tidal Information"])


@router.get("/get_height_of_tide")
async def read_root():
    logger.debug("Height of tide requested")
    return await get_height_of_tide_now()


@router.get("/get_tidal_predictions")
async def read_root():
    logger.debug("Tideal predictions requested")
    return await get_tide_predictions(datetime.now().date())
