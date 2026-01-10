import logging

from fastapi import APIRouter, Depends, Request

from src.kelder_api.app.getters import get_redis_client
from src.kelder_api.components.redis_client.redis_client import RedisClient
from src.kelder_api.components.redis_client.types import RedisSetNames

logger = logging.getLogger("api.routes.passage_plan")

router = APIRouter(tags=["Agentic"])


def get_dependancy(request: Request) -> RedisClient:
    return get_redis_client(request.app)


@router.get("/passage_plan")
async def GetPassagePlan(redis_client: RedisClient = Depends(get_dependancy)):
    logger.info("Requesting a passage plan")
    try:
        plan = (await redis_client.read_set(RedisSetNames.PASSAGE_PLAN))[0]
    except IndexError:
        plan = ""

    return {"passage_plan": plan}
