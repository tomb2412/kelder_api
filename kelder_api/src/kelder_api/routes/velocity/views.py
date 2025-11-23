import logging
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, Request

from src.kelder_api.app.getters import get_velocity_calculator
from src.kelder_api.components.velocity.service import VelocityCalculator
from src.kelder_api.configuration.settings import get_settings

logger = logging.getLogger("api.routes.velocity")

router = APIRouter(tags=["Core Sensing"])


def get_dependancy(request: Request) -> VelocityCalculator:
    return get_velocity_calculator(request.app)


@router.get("/velocity")
async def getVelocityLatest(
    velocity_calculator: VelocityCalculator = Depends(get_dependancy),
):
    logger.info("Requesting velocity data")
    velocity_data = await velocity_calculator.read_velocity_latest(active=True)
    logger.info(f"Successfully read velocity data: {velocity_data}")
    return velocity_data

@router.get("/velocity_all")
async def getVelocityAll(
    velocity_calculator: VelocityCalculator = Depends(get_dependancy),
):
    logger.info("Requesting velocity data")
    velocity_data = await velocity_calculator.read_velocity_all(active=True)
    logger.info("Successfully read all velocity data.")
    return velocity_data

@router.get("/velocity_timeseries")
async def getVelocityTimeSeries(
    start_datetime: datetime = datetime.now(timezone.utc)
    - timedelta(seconds=get_settings().velocity.gps_velocity_history),
    end_datetime: datetime = datetime.now(timezone.utc),
    velocity_calculator: VelocityCalculator = Depends(get_dependancy),
):
    logger.info("Requesting velocity data")
    velocity_data = await velocity_calculator.read_velocity_timeseries(
        start_datetime=start_datetime,
        end_datetime=end_datetime,
        active=True)
    logger.info("Successfully read all velocity data.")
    return velocity_data




# TODO unify this logging and error catching for the front
