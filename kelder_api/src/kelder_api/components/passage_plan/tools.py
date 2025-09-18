import logging

from pydantic import BaseModel

from src.kelder_api.components.redis_client.redis_client import RedisClient
from src.kelder_api.components.passage_plan.models import PassagePlan

logger = logging.getLogger(__name__)


async def save_passage_plan(
    passage_plan: PassagePlan, redis_client: "RedisClient"
) -> bool:
    """
    Save a full passage plan with all navigational details.
    """
    try:
        await redis_client.write_set("PASSAGE_PLAN", passage_plan)
        logger.debug("Passage plan created and saved")

        return True

    except Exception as error:
        return False
