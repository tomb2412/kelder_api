from http import HTTPStatus

from fastapi import APIRouter, Depends, HTTPException, Request

from src.kelder_api.app.getters import get_redis_client
from src.kelder_api.components.redis_client.redis_client import RedisClient
from src.kelder_api.configuration.logging_controller import get_logger
from src.kelder_api.configuration.settings import get_settings

logger = get_logger(__name__, "routes.redis")

router = APIRouter(tags=["Redis management"])


def get_dependancy(request: Request) -> RedisClient:
    return get_redis_client(request.app)


@router.get("/clear_redis_set")
async def clearRedisSet(
    sensor: str, redis_client: RedisClient = Depends(get_dependancy)
):
    logger.info("Clearing the redis data")
    await redis_client.delete_sets(sensor)
    logger.info("Successfully read cleared redis data")
    return {"status": "cleared"}


@router.post("/flush_redis")
async def flushRedis(redis_client: RedisClient = Depends(get_dependancy)):
    """Deletes every key on the redis server, including chat history.

    Only available while running the simulator, as the API is unauthenticated.
    """
    if not get_settings().orchestrator.run_simulator:
        raise HTTPException(
            status_code=HTTPStatus.FORBIDDEN,
            detail="Flushing redis is only allowed when running the simulator",
        )

    logger.warning("Flushing all redis data")
    await redis_client.flush_all()
    return {"status": "flushed"}


@router.get("/get_redis_set_size")
async def getRedisSetSize(
    sensor: str, redis_client: RedisClient = Depends(get_dependancy)
):
    logger.info("Sizing the redis data")
    async with redis_client.get_connection() as redis:
        key = redis_client.sensor_key(sensor)
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
