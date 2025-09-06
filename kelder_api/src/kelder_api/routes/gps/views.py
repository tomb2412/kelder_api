import logging

from fastapi import APIRouter, Depends, Request

from src.kelder_api.app.getters import get_gps_interface
from src.kelder_api.components.gps_new.interface import GPSInterface

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Core Sensing"])

def get_dependancy(request: Request) -> GPSInterface:
    return get_gps_interface(request.app)

@router.get("/gps_coords")
async def getGpCoords(gps_interface: GPSInterface = Depends(get_dependancy)):
    logger.info("Requesting GPS data")
    gps_data = await gps_interface.read_gps_latest(active=True)
    logger.info(f"Successfully read gps data: {gps_data}")
    return gps_data
