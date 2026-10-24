import json
import logging
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from typing import AsyncGenerator, List, Optional

from pydantic import BaseModel
from redis.asyncio import ConnectionPool, Redis
from redis.exceptions import ConnectionError, TimeoutError
from tenacity import (
    before_sleep_log,
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_random_exponential,
)

from src.kelder_api.components.redis_client.types import RedisSetNames
from src.kelder_api.configuration.logging_controller import get_logger
from src.kelder_api.configuration.settings import get_settings

logger = get_logger(__name__, "redis_client")


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
                ttl = (
                    expiration
                    if expiration is not None
                    else self.settings.redis_value_ttl_seconds
                )
                await redis.set(key, value, ex=ttl)
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

    @staticmethod
    def sensor_key(sensor_id: str) -> str:
        """Redis key of the sorted set holding a sensor's time series."""
        return f"sensor:ts:{sensor_id}"

    async def delete_sets(self, *sensor_ids: str) -> None:
        """Deletes whole sensor sets, freeing the memory in the background."""
        async with self.get_connection() as redis:
            await redis.unlink(
                *[self.sensor_key(sensor_id) for sensor_id in sensor_ids]
            )

    async def write_set(self, sensor_id: str, reading: BaseModel) -> None:
        async with self.get_connection() as redis:
            key = self.sensor_key(sensor_id)
            try:
                max_points = self.settings.redis_max_history_points
                async with redis.pipeline(transaction=True) as pipeline:
                    pipeline.zadd(key, {reading.json(): reading.timestamp.timestamp()})
                    pipeline.zremrangebyrank(key, 0, -max_points - 1)
                    await pipeline.execute()
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
            key = self.sensor_key(sensor_id)

            # Get data in time range with scores (timestamps)
            sensor_data = await redis.zrevrangebyscore(
                key,
                max=datetime_range[1].timestamp() if datetime_range else "+inf",
                min=datetime_range[0].timestamp() if datetime_range else "-inf",
                start=0,
                num=self.settings.redis_max_history_points,
                withscores=True,
            )

            return [json.loads(measurement) for measurement, _ in sensor_data]

    @staticmethod
    def _daily_key(key: str, timestamp: datetime | None = None) -> str:
        timestamp = timestamp or datetime.now(timezone.utc)
        return f"{key}{timestamp.date().strftime('%d%m%Y')}"

    async def write_hashed_set(
        self, key: str, data: BaseModel, timestamp: datetime | None = None
    ):
        key = self._daily_key(key, timestamp)

        async with self.get_connection() as redis:
            try:
                async with redis.pipeline(transaction=True) as pipeline:
                    pipeline.hset(key, mapping=data.model_dump(mode="json"))
                    pipeline.expire(key, self.settings.redis_daily_hash_ttl_seconds)
                    await pipeline.execute()
            except Exception as error:
                logger.error(
                    f"Redis exception raised writing to stream {key}, with {error}"
                )
                raise error

    async def read_hashed_set(self, key: str, timestamp: datetime | None = None):
        """Method to read the current days stream."""
        key = self._daily_key(key, timestamp)

        async with self.get_connection() as redis:
            try:
                return await redis.hgetall(key)
            except Exception as error:
                logger.error(
                    f"Redis exception raised reading from stream {key}, with {error}"
                )
                raise error

    async def clear_set(
        self,
        set_name: RedisSetNames | None = None,
        end_datetime: datetime | None = None,
    ) -> None:
        """
        Method to clear the redis data, of a particular set.

        None will delete all sets
        """
        end_datetime = end_datetime or datetime.now(timezone.utc)

        if set_name:
            async with self.get_connection() as redis:
                await redis.zremrangebyscore(
                    self.sensor_key(set_name.value), "-inf", end_datetime.timestamp()
                )

            logger.info(
                "Cleared %s redis sets before: %s" % (set_name.value, end_datetime)
            )

        else:
            async with self.get_connection() as redis:
                for set_name in RedisSetNames:
                    if set_name in (
                        RedisSetNames.VESSEL_STATE,
                        RedisSetNames.PASSAGE_PLAN,
                    ):
                        continue

                    await redis.zremrangebyscore(
                        self.sensor_key(set_name.value),
                        "-inf",
                        end_datetime.timestamp(),
                    )

            logger.info("Cleared all redis sets before: %s", end_datetime)

    @retry(
        retry=retry_if_exception_type((ConnectionError, TimeoutError)),
        wait=wait_random_exponential(multiplier=1, max=60),
        stop=stop_after_attempt(3),
        before_sleep=before_sleep_log(logger, logging.WARNING),
        reraise=True,
    )
    async def flush_all(self):
        async with self.get_connection() as redis:
            await redis.flushall(asynchronous=True)
            logger.info("Flushed all redis data.")
