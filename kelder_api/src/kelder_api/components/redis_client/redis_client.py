import json
import logging
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from typing import AsyncGenerator, List, Optional

from pydantic import BaseModel
from redis.asyncio import ConnectionPool, Redis

from src.kelder_api.configuration.logging_config import setup_logging
from src.kelder_api.configuration.settings import get_settings

setup_logging(component="redis_client")
logger = logging.getLogger("redis_client")


class RedisClient:
    def __init__(self):
        self._connection_pool: Optional[ConnectionPool] = None
        self.settings = get_settings().redis

    async def _ensure_connection_pool(self):
        if not self._connection_pool:
            self._connection_pool = ConnectionPool(
                host=self.settings.redis_host,
                port=self.settings.redis_port,
                decode_responses=True,
                max_connections=10,
                retry_on_timeout=True,
                socket_timeout=5.0,
                socket_connect_timeout=5.0,
                health_check_interval=30,
            )
        return self._connection_pool

    async def _close_connection_pool(self):
        if self._connection_pool:
            await self._connection_pool.disconnect()
            self._connection_pool = None

    @asynccontextmanager
    async def get_connection(self) -> AsyncGenerator[Redis, None]:
        connection_pool = await self._ensure_connection_pool()
        redis = Redis(connection_pool=connection_pool)
        try:
            yield redis
        except Exception as error:
            logger.error("Redis connection error: %s", error)
            raise error
        finally:
            await redis.close()

    async def write_value(self, key: str, value: str, expiration: Optional[int] = None):
        async with self.get_connection() as redis:
            try:
                await redis.set(key, value)
            except Exception as error:
                logger.error(
                    "Redis exception raised setting key %s with value %s: %s",
                    key,
                    value,
                    error,
                )
                raise error

    async def read_value(self, key: str) -> Optional[str]:
        async with self.get_connection() as redis:
            try:
                return await redis.get(key)
            except Exception as error:
                logger.error(
                    "Redis exception raised reading the value for key %s: %s",
                    key,
                    error,
                )
                raise error

    async def write_set(self, sensor_id: str, reading: BaseModel) -> None:
        async with self.get_connection() as redis:
            key = f"sensor:ts:{sensor_id}"
            try:
                await redis.zadd(key, {reading.json(): reading.timestamp.timestamp()})
            except Exception as error:
                logger.error(
                    f"Redis exception raised writing to sorted set, with {error}"
                )
                raise error

    async def read_set(
        self, sensor_id: str, datetime_range: Optional[datetime | str] = None
    ) -> List[BaseModel]:
        async with self.get_connection() as redis:
            """Get time-range data from sorted set."""
            key = f"sensor:ts:{sensor_id}"

            # Get data in time range with scores (timestamps)
            sensor_data = await redis.zrevrangebyscore(
                key,
                max=datetime_range[1].timestamp() if datetime_range else "+inf",
                min=datetime_range[0].timestamp() if datetime_range else "-inf",
                withscores=True,
            )

            return [json.loads(measurement) for measurement, _ in sensor_data]

    async def write_hashed_set(
        self, key: str, data: BaseModel, datetime: datetime = datetime.now(timezone.utc)
    ):
        key = f"{key}{datetime.date().strftime('%d%m%Y')}"

        async with self.get_connection() as redis:
            try:
                await redis.hset(key, mapping=data.model_dump(mode="json"))
            except Exception as error:
                logger.error(
                    f"Redis exception raised writing to stream {key}, with {error}"
                )
                raise error

    async def read_hashed_set(
        self, key: str, datetime: datetime = datetime.now(timezone.utc)
    ):
        """Method to read the current days stream."""
        key = f"{key}{datetime.date().strftime('%d%m%Y')}"

        async with self.get_connection() as redis:
            try:
                return await redis.hgetall(key)
            except Exception as error:
                logger.error(
                    f"Redis exception raised reading from stream {key}, with {error}"
                )
                raise error
