import logging

from fastapi import APIRouter

from src.kelder_api.components.compass.service import CompassSensor

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Core Sensing"])


@router.get("/compass_heading")
async def getCompassHeading():
    logger.info("Request recieved for compass heading")
    heading = await CompassSensor.readCompassHeading()
    return {"heading": heading}
