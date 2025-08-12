from redis.asyncio import Redis, ConnectionPool
from typing import AsyncGenerator, Optional
from contextlib import asynccontextmanager
from pydantic import BaseModel
from datetime import datetime
from typing import List

from src.kelder_api.configuration.settings import Settings

from logging import getLogger

logger = getLogger(__name__)

class RedisClient:
    def __init__(self):
        self._connection_pool: Optional[ConnectionPool] = None
        self.settings = Settings().redis

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
            logger.debug("Connected to redis through the pool")
            yield redis
        except Exception as error:
            logger.error(f"Redis connection error: {error}")
            raise error
        finally:
            await redis.close()
            logger.debug("Closed redis connection")


    async def write_value(self, key: str, value: str, expiration: Optional[int] = None):
        async with self.get_connection() as redis:
            try:
                await redis.set(key, value)
            except Exception as error:
                logger.error(f"Redis exception raised setting the key-value pair: {key}:{value}, with {error}")
                raise error

    async def read_value(self, key: str) -> Optional[str]:
        async with self.get_connection() as redis:
            try:
                return await redis.get(key)
            except Exception as error:
                logger.error(f"Redis exception raised reading the value: {value}, because of: {error}")
                raise error

    async def write_set(self, key: str, reading: BaseModel) -> None:
        async with self.get_connection() as redis:
            try:
                await redis.zadd(key, {reading.json(): reading.timestamp.timestamp()})
            except Exception as error:
                logger.error(f"Redis exception raised writing to sorted set, with {error}")
                raise error
    
    async def read_set(self, sensor_id: str, datetime_range: Optional[datetime] = None) -> List[BaseModel]:
        async with self.get_connection() as redis:
            """Get time-range data from sorted set."""
            key = f"sensor:ts:{sensor_id}"
            
            end_time = datetime_to or time.time()
            
            # Get data in time range with scores (timestamps)
            if datetime_range:
                data = await self.redis.zrevrangebyscore(key, end_time, start_time, 
                                                    withscores=True, start=0, num=limit)
            else:
                data = await self.redis.zrangebyscore(key, start_time, end_time, withscores=True)
            
            results = []
            for value_ts, timestamp in data:
                value = value_ts.split(':')[0]  # Extract value from "value:timestamp"
                results.append({
                    'timestamp': timestamp,
                    'value': float(value),
                    'sensor_id': sensor_id
                })
            
            return results