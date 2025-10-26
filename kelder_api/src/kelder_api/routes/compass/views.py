import logging

from fastapi import APIRouter, Depends, Request

from src.kelder_api.app.getters import get_compass_interface
from src.kelder_api.components.compass_new.interface import CompassInterface

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Core Sensing"])


def get_dependancy(request: Request) -> CompassInterface:
    return get_compass_interface(request.app)


@router.get("/compass_heading")
async def getCompassHeading(
    compass_interface: CompassInterface = Depends(get_dependancy),
):
    logger.info("Request recieved for compass heading")
    heading = await compass_interface.read_heading_history_length(length=1, active=True)
    return heading[0]
