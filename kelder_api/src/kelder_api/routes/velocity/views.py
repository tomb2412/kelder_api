from datetime import datetime

from fastapi import APIRouter, Depends, Request

from src.kelder_api.app.getters import get_velocity_calculator
from src.kelder_api.components.velocity.service import VelocityCalculator
from src.kelder_api.components.velocity.utils import velocity_time_window
from src.kelder_api.configuration.logging_controller import get_logger

logger = get_logger(__name__, "routes.velocity")

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
    start_datetime: datetime | None = None,
    end_datetime: datetime | None = None,
    velocity_calculator: VelocityCalculator = Depends(get_dependancy),
):
    """Defaults to velocity history params"""
    start_datetime, end_datetime = velocity_time_window(start_datetime, end_datetime)
    logger.info("Requesting velocity data")
    velocity_data = await velocity_calculator.read_velocity_timeseries(
        start_datetime=start_datetime, end_datetime=end_datetime, active=True
    )
    logger.info("Successfully read all velocity data.")
    return velocity_data


# TODO unify this logging and error catching for the front
