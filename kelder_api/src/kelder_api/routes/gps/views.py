import logging
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, Request

from src.kelder_api.configuration.settings import get_settings
from src.kelder_api.app.getters import get_gps_interface
from src.kelder_api.components.gps_new.interface import GPSInterface

logger = logging.getLogger(__name__)

router = APIRouter(tags=["GPS"])

def get_dependancy(request: Request) -> GPSInterface:
    return get_gps_interface(request.app)

@router.get("/gps_coords_latest")
async def getGpCoords(gps_interface: GPSInterface = Depends(get_dependancy)):
    logger.info("Requesting GPS data")
    gps_data = await gps_interface.read_gps_latest(active=True)
    return gps_data

@router.get("/gps_coords_all")
async def getGpCoords(gps_interface: GPSInterface = Depends(get_dependancy)):
    logger.info("Requesting GPS data")
    gps_data = await gps_interface.read_gps_all_history(active=True)
    return gps_data

@router.get("/gps_coords_timeseries")
async def getGpCoords(
    start_datetime: datetime = datetime.now() - timedelta(seconds=get_settings().velocity.gps_velocity_history),
    end_datetime: datetime = datetime.now(),
    gps_interface: GPSInterface = Depends(get_dependancy),
    ):
    """Defualts to velocity history params"""
    logger.info("Requesting GPS data")
    gps_data = await gps_interface.read_gps_history_time_series(
        start_datetime=start_datetime,
        end_datetime=end_datetime,
        active=True
        )
    return gps_data

@router.get("/gps_coords_length")
async def getGpCoords(
    length: int = get_settings().velocity.gps_velocity_history,
    gps_interface: GPSInterface = Depends(get_dependancy),
    ):
    logger.info("Requesting GPS data")
    gps_data = await gps_interface.read_gps_history_length(length = length, active=True)
    return gps_data
