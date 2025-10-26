import logging
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import ValidationError

from src.kelder_api.app.getters import get_redis_client
from src.kelder_api.components.redis_client.redis_client import RedisClient
from src.kelder_api.components.ultrasound.models import BilgeDepth
from src.kelder_api.configuration.settings import get_settings

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Core Sensing"])


def get_dependency(request: Request) -> RedisClient:
    return get_redis_client(request.app)


@router.get("/bilge_depth")
async def get_bilge_depth(
    redis_client: RedisClient = Depends(get_dependency),
) -> BilgeDepth:
    logger.info("Requesting latest bilge depth reading")

    readings = await redis_client.read_set("BILGE_DEPTH")
    if not readings:
        raise HTTPException(status_code=404, detail="No bilge depth data available")

    latest_reading = readings[0]
    try:
        bilge_depth = BilgeDepth(**latest_reading)
    except ValidationError as exc:
        logger.exception("Unable to parse bilge depth reading: %s", exc)
        raise HTTPException(
            status_code=500, detail="Bilge depth data is unavailable"
        ) from exc

    settings = get_settings().bilge_depth
    max_age = timedelta(minutes=settings.max_data_age_minutes)
    bilge_depth = _validate_freshness(bilge_depth, max_age)

    logger.debug("Returning bilge depth reading at %s", bilge_depth.timestamp)
    return bilge_depth


def _validate_freshness(reading: BilgeDepth, max_age: timedelta) -> BilgeDepth:
    """
    Ensure the reading timestamp is within the allowed freshness window.
    When stale, the distance is cleared to signal invalid data to clients.
    """

    timestamp = reading.timestamp
    if timestamp.tzinfo is None:
        timestamp = timestamp.replace(tzinfo=timezone.utc)
    else:
        timestamp = timestamp.astimezone(timezone.utc)

    age = datetime.now(timezone.utc) - timestamp
    if age > max_age:
        logger.warning(
            "Bilge depth reading is stale (%s old); returning null distance", age
        )
        return reading.model_copy(update={"bilge_depth": None})

    return reading
