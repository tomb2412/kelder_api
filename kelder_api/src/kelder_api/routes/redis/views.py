import logging

from fastapi import APIRouter, Depends, Request

from src.kelder_api.app.getters import get_redis_client
from src.kelder_api.components.redis_client.redis_client import RedisClient

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Redis management"])


def get_dependancy(request: Request) -> RedisClient:
    return get_redis_client(request.app)


@router.get("/clear_redis_set")
async def clearRedisSet(
    sensor: str, redis_client: RedisClient = Depends(get_dependancy)
):
    logger.info("Clearing the redis data")
    async with redis_client.get_connection() as redis:
        await redis.delete(f"sensor:ts:{sensor}")
    logger.info("Successfully read cleared redis data")
    return {"status": "cleared"}


@router.get("/get_redis_set_size")
async def getRedisSetSize(
    sensor: str, redis_client: RedisClient = Depends(get_dependancy)
):
    logger.info("Sizing the redis data")
    async with redis_client.get_connection() as redis:
        size = await redis.zcard(f"sensor:ts:{sensor}")
        list_gps = await redis.zrevrangebyscore(
            "sensor:ts:{sensor}",
            max="+inf",
            min="-inf",
            withscores=True,
        )

    logger.info(f"the length of the set is: {len(list_gps)}")
    logger.info(f"Redis set {sensor} has length {size}")
    return {sensor: size, "list_length": len(list_gps)}
