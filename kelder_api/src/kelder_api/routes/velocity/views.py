import logging

from fastapi import APIRouter, Depends, Request

from src.kelder_api.app.getters import get_velocity_calculator
from src.kelder_api.components.velocity.service import VelocityCalculator

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Core Sensing"])

def get_dependancy(request: Request) -> VelocityCalculator:
    return get_velocity_calculator(request.app)

@router.get("/velocity")
async def getGpCoords(velocity_calculator: VelocityCalculator = Depends(get_dependancy)):
    logger.info("Requesting velocity data")
    velocity_data = await velocity_calculator.read_velocity_latest(active=True)
    logger.info(f"Successfully read velocity data: {velocity_data}")
    return velocity_data
