import json
import logging
from datetime import datetime, timedelta, timezone
from http import HTTPStatus
from typing import List, Tuple

from fastapi import APIRouter, Depends, HTTPException, Request

from src.kelder_api.app.getters import (
    get_drift_calculator,
    get_gps_interface,
    get_log_tracker,
    get_redis_client,
    get_velocity_calculator,
)
from src.kelder_api.components.drift_calculator.serivce import DriftCalculator
from src.kelder_api.components.gps_new.interface import GPSInterface
from src.kelder_api.components.gps_new.models import GPSRedisData
from src.kelder_api.components.log.service import LogTracker
from src.kelder_api.components.passage_plan_tracker.service import PassagePlanTracker
from src.kelder_api.components.redis_client.redis_client import RedisClient
from src.kelder_api.components.velocity.service import VelocityCalculator
from src.kelder_api.configuration.settings import get_settings
from src.kelder_api.routes.gps.models import GPSCard, GPSMap
from src.kelder_api.components.velocity.utils import convert_to_decimal_degrees

logger = logging.getLogger("api.routes.gps")

router = APIRouter(tags=["GPS"])
router_card = APIRouter(tags=["Card routes"])


def _format_gps_payload(
    gps_payload: GPSRedisData | List[GPSRedisData] | None,
) -> GPSRedisData | List[GPSRedisData] | None:
    """Apply frontend-specific rounding to gps payloads."""
    if gps_payload is None:
        return None
    if isinstance(gps_payload, list):
        return [payload.round_coordinates() for payload in gps_payload]
    return gps_payload.round_coordinates()


def get_dependancy(request: Request) -> GPSInterface:
    return get_gps_interface(request.app)

def get_velocity_dependancy(request: Request) -> VelocityCalculator:
    return get_velocity_calculator(request.app)

def get_log_dependancy(request: Request) -> LogTracker:
    return get_log_tracker(request.app)

def get_card_dependancies(
    request: Request,
) -> Tuple[GPSInterface, VelocityCalculator, LogTracker, DriftCalculator, RedisClient]:
    gps_interface = get_gps_interface(request.app)
    velocity_calculator = get_velocity_calculator(request.app)
    log_tracker = get_log_tracker(request.app)
    drift_calculator = get_drift_calculator(request.app)
    redis_client = get_redis_client(request.app)

    return gps_interface, velocity_calculator, log_tracker, drift_calculator, redis_client


@router.get("/gps_coords_latest")
async def get_gps_coords_latest(gps_interface: GPSInterface = Depends(get_dependancy)):
    logger.info("Requesting GPS data")
    gps_data = await gps_interface.read_gps_latest(active=True)
    return _format_gps_payload(gps_data)


@router.get("/gps_coords_all")
async def get_gps_coords_all(gps_interface: GPSInterface = Depends(get_dependancy)):
    logger.info("Requesting GPS data")
    gps_data = await gps_interface.read_gps_all_history(active=True)
    return _format_gps_payload(gps_data)


@router.get("/gps_coords_timeseries")
async def get_gps_coords_timeseries(
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
    return _format_gps_payload(gps_data)


@router.get("/gps_coords_length")
async def get_gps_coords_length(
    length: int = get_settings().velocity.gps_velocity_history,
    gps_interface: GPSInterface = Depends(get_dependancy),
):
    logger.info("Requesting GPS data")
    gps_data = await gps_interface.read_gps_history_length(length=length, active=True)
    return _format_gps_payload(gps_data)


@router_card.get("/gps_card_data")
async def get_gps_card(
    components: Tuple[
        GPSInterface, VelocityCalculator, LogTracker, DriftCalculator, RedisClient
    ] = Depends(get_card_dependancies),
) -> GPSCard:
    gps_interface = components[0]
    velocity_calculator = components[1]
    log_tracker = components[2]
    drift_calculator = components[3]
    redis_client = components[4]

    # TODO: This should be a time window, so the latest gps within say 1 hour
    gps_data = await gps_interface.read_gps_latest(active=True)
    velocity_data = await velocity_calculator.read_velocity_latest(active=True)
    journey_data = await log_tracker.get_journey_set()
    drift_data = await drift_calculator.read_drift_latest(active=True)

    # Read passage plan progress for DTW
    tracker = PassagePlanTracker(redis_client, gps_interface)
    progress = await tracker.read_progress_latest()
    dtw = progress.distance_to_waypoint if progress else None

    # TODO will this return the previous journeys stats?
    if journey_data and velocity_data.speed_over_ground:
        log = journey_data.distance_travelled
    else:
        log = "error"
    gps_data = _format_gps_payload(gps_data)

    if gps_data:
        return GPSCard(
            timestamp=gps_data.timestamp.time(),
            latitude=gps_data.latitude_nmea,
            longitude=gps_data.longitude_nmea,
            speed_over_ground=velocity_data.speed_over_ground
            if velocity_data.speed_over_ground
            else "error",
            log=log,
            drift=drift_data.drift_speed,
            dtw=dtw,
        )
    else:
        raise HTTPException(
            status_code=HTTPStatus.NOT_FOUND, detail="No GPS data available"
        )


@router_card.get("/gps_map_position")
async def get_gps_card(
    gps_interface: GPSInterface = Depends(get_dependancy),
    velocity_calculator: VelocityCalculator = Depends(get_velocity_dependancy),
    log_tracker: LogTracker = Depends(get_log_dependancy),
) -> GPSMap:
    """Decimal degree gps position with compass orientation (to be implementent)."""

    # TODO: This should be a time window, so the latest gps within say 1 hour
    gps_data = await gps_interface.read_gps_latest(active=True)
    velocity_data = await velocity_calculator.read_velocity_latest(active=True)
    journey_data = await log_tracker.get_journey_set()

    track = None
    if journey_data and journey_data.gps_data:
        try:
            track = json.loads(journey_data.gps_data)
        except json.JSONDecodeError:
            logger.warning("Failed to parse journey gps_data track; returning None")

    if gps_data:
        return GPSMap(
            longitude=str(convert_to_decimal_degrees(gps_data.longitude_nmea)),
            latitude=str(convert_to_decimal_degrees(gps_data.latitude_nmea)),
            cog=str(velocity_data.course_over_ground)
            if velocity_data.course_over_ground
            else "0",
            track=track,
        )
    else:
        raise HTTPException(
            status_code=HTTPStatus.NOT_FOUND, detail="No GPS data available"
        )
