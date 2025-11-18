import asyncio
import logging

from src.kelder_api.components.agentic_workflow.agents.models import PassagePlan
from src.kelder_api.components.redis_client.redis_client import RedisClient

logger = logging.getLogger(__name__)


async def save_passage_plan(
    passage_plan: PassagePlan, redis_client: "RedisClient"
) -> bool:
    """
    Save a full passage plan with all navigational details.
    """

    try:
        async with asyncio.timeout(2):
            await redis_client.write_set("PASSAGE_PLAN", passage_plan)
            logger.debug("Passage plan created and saved")
        return True

    except TimeoutError:
        logger.error("The passage plan failed to save within the timeperiod")
    except Exception:
        logger.error("Passage plan failed to save")
        raise
