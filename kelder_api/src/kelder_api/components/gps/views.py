import logging 

from fastapi import APIRouter

from src.kelder_api.components.gps.models import GpsMeasurementData
from src.kelder_api.components.gps.service import getGpCoords as getGpCoordsService

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Core Sensing"])

@router.get("/gps_coords")
async def getGpCoords():
    logger.info("Requesting GPS data")
    gps_data = await getGpCoordsService()
    logger.info("Successfully retrieved GPS data")
    return gps_data
    