from fastapi import APIRouter

from src.kelder_api.components.gps.models import GpsMeasurementData
from src.kelder_api.components.gps.service import getGpCoords

router = APIRouter(tags=["Core Sensing"])

@router.get("/gps_coords")
def getGpCoords():
    return getGpCoords()
    