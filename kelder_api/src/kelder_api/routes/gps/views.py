import logging
from datetime import datetime, timedelta, timezone
from typing import Tuple

from fastapi import APIRouter, Depends, Request

from src.kelder_api.app.getters import (
    get_gps_interface,
    get_log_tracker,
    get_velocity_calculator,
)
from src.kelder_api.components.gps_new.interface import GPSInterface
from src.kelder_api.components.log.service import LogTracker
from src.kelder_api.components.velocity.service import VelocityCalculator
from src.kelder_api.configuration.settings import get_settings
from src.kelder_api.routes.gps.models import GPSCard

logger = logging.getLogger(__name__)

router = APIRouter(tags=["GPS"])
router_card = APIRouter(tags=["Card routes"])

def get_dependancy(request: Request) -> GPSInterface:
    return get_gps_interface(request.app)

def get_card_dependancies(request: Request) -> Tuple[GPSInterface, VelocityCalculator, LogTracker]:
    gps_interface = get_gps_interface(request.app)
    velocity_calculator = get_velocity_calculator(request.app)
    log_tracker = get_log_tracker(request.app)

    return gps_interface, velocity_calculator, log_tracker

@router.get("/gps_coords_latest")
async def getGpsCoords(gps_interface: GPSInterface = Depends(get_dependancy)):
    logger.info("Requesting GPS data")
    gps_data = await gps_interface.read_gps_latest(active=True)
    return gps_data


@router.get("/gps_coords_all")
async def getGpsCoords(gps_interface: GPSInterface = Depends(get_dependancy)):
    logger.info("Requesting GPS data")
    gps_data = await gps_interface.read_gps_all_history(active=True)
    return gps_data


@router.get("/gps_coords_timeseries")
async def getGpsCoords(
    start_datetime: datetime = datetime.now(timezone.utc)
    - timedelta(seconds=get_settings().velocity.gps_velocity_history),
    end_datetime: datetime = datetime.now(timezone.utc),
    gps_interface: GPSInterface = Depends(get_dependancy),
):
    """Defualts to velocity history params"""
    logger.info("Requesting GPS data")
    gps_data = await gps_interface.read_gps_history_time_series(
        start_datetime=start_datetime, end_datetime=end_datetime, active=True
    )
    return gps_data


@router.get("/gps_coords_length")
async def getGpsCoords(
    length: int = get_settings().velocity.gps_velocity_history,
    gps_interface: GPSInterface = Depends(get_dependancy),
):
    logger.info("Requesting GPS data")
    gps_data = await gps_interface.read_gps_history_length(length=length, active=True)
    return gps_data

@router_card.get("/gps_card_data")
async def getGpsCard(
    components: Tuple[GPSInterface, VelocityCalculator, LogTracker] = Depends(get_card_dependancies)
) -> GPSCard:
    gps_interface = components[0]
    velocity_calculator = components[1]
    log_tracker = components[2]

    # TODO: This should be a time window, so the latest gps within say 1 hour
    gps_data = await gps_interface.read_gps_latest(active=True)
    velocity_data = await velocity_calculator.read_velocity_latest(active=True)
    journey_data = await log_tracker.get_journey_set()

    # TODO will this return the previous journeys stats?
    if journey_data:
        log = journey_data.distance_travelled
    else:
        log = "error"


    return GPSCard(
        # TODO implement an error handling + add drift and DTW
        timestamp = gps_data.timestamp.time(),
        latitude = gps_data.latitude_nmea,
        longitude = gps_data.longitude_nmea,
        speed_over_ground = velocity_data.speed_over_ground if velocity_data.speed_over_ground else "error",
        log = log
    )
