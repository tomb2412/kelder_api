import logging 

from fastapi import APIRouter
import redis

from src.kelder_api.components.gps.models import GpsMeasurementData
from src.kelder_api.components.gps.service import ReadGPSCoords, SenseGpCoords

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Core Sensing"])

r = redis.Redis(host='redis', port=6379,decode_responses=True)

@router.get("/gps_coords")
async def getGpCoords():
    logger.info("Requesting GPS data")
    gps_data = await ReadGPSCoords()
    return gps_data
    