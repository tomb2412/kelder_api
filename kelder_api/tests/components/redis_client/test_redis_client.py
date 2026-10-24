from datetime import datetime, timedelta, timezone

import pytest
from pydantic import BaseModel, Field

from src.kelder_api.components.redis_client.redis_client import RedisClient


class GPSReading(BaseModel):
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    coordinate: str


class StatusReading(BaseModel):
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    status: str
    value: int


@pytest.mark.asyncio
async def test_write_and_read_scalar_value(redis_server) -> None:
    """Store a plain value and ensure it can be retrieved unchanged."""
    client = RedisClient()

    # Act: write and immediately read the value back.
    await client.write_value("hello", "world")
    read_value = await client.read_value("hello")

    assert read_value == "world"


@pytest.mark.asyncio
async def test_sorted_set_roundtrip(redis_server) -> None:
    """Verify sorted-set writes are stored and returned in reverse timestamp order."""
    client = RedisClient()

    readings = [
        GPSReading(timestamp=datetime(2024, 1, 1, tzinfo=timezone.utc), coordinate="A"),
        GPSReading(timestamp=datetime(2024, 1, 2, tzinfo=timezone.utc), coordinate="B"),
        GPSReading(timestamp=datetime(2024, 1, 3, tzinfo=timezone.utc), coordinate="C"),
    ]

    for reading in readings:
        await client.write_set("gps", reading)

    # Act: pull the readings back without a range filter.
    raw_results = await client.read_set("gps")
    parsed_results = [GPSReading(**item) for item in raw_results]

    assert [result.coordinate for result in parsed_results] == ["C", "B", "A"]


@pytest.mark.asyncio
async def test_sorted_set_datetime_range(redis_server) -> None:
    """Respect a provided datetime window when reading sorted-set data."""
    client = RedisClient()

    base_time = datetime(2024, 6, 1, tzinfo=timezone.utc)
    readings = [
        GPSReading(timestamp=base_time - timedelta(days=1), coordinate="before"),
        GPSReading(timestamp=base_time, coordinate="inside"),
        GPSReading(timestamp=base_time + timedelta(days=1), coordinate="after"),
    ]

    for reading in readings:
        await client.write_set("gps", reading)

    start = base_time - timedelta(hours=12)
    end = base_time + timedelta(hours=12)

    # Act: only the reading inside the window should be returned.
    raw_results = await client.read_set("gps", [start, end])
    parsed_results = [GPSReading(**item) for item in raw_results]

    assert [result.coordinate for result in parsed_results] == ["inside"]


@pytest.mark.asyncio
async def test_hashed_set_roundtrip(redis_server) -> None:
    """Ensure hash writes round-trip and retain serialized payloads."""
    client = RedisClient()

    timestamp = datetime(2024, 5, 20, 15, 30, tzinfo=timezone.utc)
    reading = StatusReading(timestamp=timestamp, status="ok", value=184)

    # Persist to the hash that matches the same day as the timestamp.
    await client.write_hashed_set("journey:", reading, timestamp=timestamp)
    hashed_values = await client.read_hashed_set("journey:", timestamp=timestamp)

    assert hashed_values == reading.model_dump(mode="json")


@pytest.mark.asyncio
async def test_hashed_set_expires(redis_server) -> None:
    """Daily hashes get a TTL so old days do not accumulate in redis."""
    client = RedisClient()

    timestamp = datetime(2024, 5, 20, 15, 30, tzinfo=timezone.utc)
    reading = StatusReading(timestamp=timestamp, status="ok", value=184)

    await client.write_hashed_set("journey:", reading, timestamp=timestamp)

    assert (
        redis_server._ttls["journey:20052024"]
        == client.settings.redis_daily_hash_ttl_seconds
    )


@pytest.mark.asyncio
async def test_clear_set_preserves_passage_plan(redis_server) -> None:
    """Clearing all sets removes old sensor history but keeps the passage plan."""
    client = RedisClient()

    old = datetime(2024, 1, 1, tzinfo=timezone.utc)
    await client.write_set("GPS", GPSReading(timestamp=old, coordinate="A"))
    await client.write_set("PASSAGE_PLAN", GPSReading(timestamp=old, coordinate="B"))

    await client.clear_set(end_datetime=old + timedelta(days=1))

    assert await client.read_set("GPS") == []
    assert len(await client.read_set("PASSAGE_PLAN")) == 1


@pytest.mark.asyncio
async def test_close_connection_pool_resets_state(redis_server) -> None:
    """Closing the client clears the cached pool and signals the fake pool shutdown."""
    client = RedisClient()
    await client.write_value("temporary", "value")

    connection_pool = client._connection_pool
    assert connection_pool is not None

    await client._close_connection_pool()

    assert getattr(connection_pool, "disconnected", False) is True
    assert client._connection_pool is None
