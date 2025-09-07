import logging

from agents import function_tool

from src.kelder_api.components.redis_client.redis_client import RedisClient
from src.kelder_api.components.passage_plan.models import PassagePlan

logger = logging.getLogger(__name__)

@function_tool
async def save_passage_plan(passage_plan: PassagePlan):
    """
    Save a full passage plan with all navigational details.
    """
    redis_client = RedisClient()
    await redis_client.write_set("PASSAGE_PLAN", passage_plan)

    logger.debug("Passage plan created and saved")
