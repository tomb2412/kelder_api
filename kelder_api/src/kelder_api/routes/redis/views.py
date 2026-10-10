import logging

from fastapi import APIRouter, Depends, Request

from src.kelder_api.app.getters import get_redis_client
from src.kelder_api.components.redis_client.redis_client import RedisClient

logger = logging.getLogger("api.routes.redis")

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
        key = f"sensor:ts:{sensor}"
        size = await redis.zcard(key)
        list_gps = await redis.zrevrangebyscore(
            key,
            max="+inf",
            min="-inf",
            start=0,
            num=redis_client.settings.redis_max_history_points,
            withscores=True,
        )

    logger.info(f"the length of the set is: {len(list_gps)}")
    logger.info(f"Redis set {sensor} has length {size}")
    return {sensor: size, "list_length": len(list_gps)}
