from __future__ import annotations

import json
import math
import os
from collections import defaultdict
from contextlib import asynccontextmanager
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from typing import Any, Dict, Iterable, Tuple

import pytest
from fastapi.testclient import TestClient

os.environ.setdefault("OPENAI_API_KEY", "test-key")

from src.kelder_api.components.compass_new.models import CompassRedisData
from src.kelder_api.components.gps_new.models import GPSRedisData
from src.kelder_api.components.gps_new.types import GPSStatus
from src.kelder_api.components.log.models import JourneyData
from src.kelder_api.components.redis_client import redis_client as redis_client_module
from src.kelder_api.components.velocity.models import GPSVelocity


class _InMemoryRedisServer:
    def __init__(self) -> None:
        self._strings: Dict[str, str] = {}
        self._sorted_sets: Dict[str, Dict[str, float]] = defaultdict(dict)
        self._hashes: Dict[str, Dict[str, Any]] = defaultdict(dict)

    def reset(self) -> None:
        self._strings.clear()
        self._sorted_sets.clear()
        self._hashes.clear()


@dataclass
class _FakeConnectionPool:
    server: _InMemoryRedisServer
    disconnected: bool = False

    async def disconnect(self) -> None:
        self.disconnected = True


class _FakeRedis:
    def __init__(
        self, connection_pool: _FakeConnectionPool | None = None, **_: Any
    ) -> None:
        if connection_pool is None:
            raise ValueError("connection_pool must be provided for FakeRedis")
        self._server = connection_pool.server

    async def close(self) -> None:
        return None

    async def ping(self) -> bool:
        return True

    async def set(self, key: str, value: str) -> None:
        self._server._strings[key] = value

    async def get(self, key: str) -> str | None:
        return self._server._strings.get(key)

    async def zadd(self, key: str, mapping: Dict[str, float]) -> None:
        self._server._sorted_sets[key].update(mapping)

    async def zrevrangebyscore(
        self,
        key: str,
        max: float | str = "+inf",
        min: float | str = "-inf",
        withscores: bool = False,
    ) -> Iterable[Tuple[str, float]]:
        sorted_set = self._server._sorted_sets.get(key, {})
        max_score = _normalise_score(max, default=math.inf)
        min_score = _normalise_score(min, default=-math.inf)

        items = [
            (member, score)
            for member, score in sorted_set.items()
            if min_score <= score <= max_score
        ]
        items.sort(key=lambda item: item[1], reverse=True)
        if withscores:
            return items
        return [member for member, _ in items]

    async def hset(self, key: str, mapping: Dict[str, Any]) -> None:
        self._server._hashes[key].update(mapping)

    async def hgetall(self, key: str) -> Dict[str, Any]:
        return dict(self._server._hashes.get(key, {}))


def _normalise_score(value: float | str, default: float) -> float:
    if isinstance(value, (int, float)):
        return float(value)
    if value in {"+inf", "+infinity", "inf", "infinity"}:
        return math.inf
    if value in {"-inf", "-infinity"}:
        return -math.inf
    return float(value)


@pytest.fixture()
def redis_server(monkeypatch: pytest.MonkeyPatch) -> _InMemoryRedisServer:
    server = _InMemoryRedisServer()

    def _connection_pool_factory(*args: Any, **kwargs: Any) -> _FakeConnectionPool:
        return _FakeConnectionPool(server=server)

    def _redis_factory(*args: Any, **kwargs: Any) -> _FakeRedis:
        connection_pool = kwargs.get("connection_pool")
        if connection_pool is None and args:
            connection_pool = args[0]
        return _FakeRedis(connection_pool=connection_pool)

    monkeypatch.setattr(redis_client_module, "ConnectionPool", _connection_pool_factory)
    monkeypatch.setattr(redis_client_module, "Redis", _redis_factory)

    return server


class DummyRedisClient:
    """Minimal stub that mimics the Redis client lifecycle."""

    def __init__(self) -> None:
        self.closed = False
        gps_record = GPSRedisData(
            timestamp=datetime(2024, 1, 1, 12, tzinfo=timezone.utc),
            status=GPSStatus.ACTIVE,
            latitude_nmea="5123.46",
            longitude_nmea="00123.99",
        ).model_dump(mode="json")
        payload = json.dumps(gps_record)
        self.sorted_sets: Dict[str, list[tuple[str, float]]] = {
            "sensor:ts:GPS": [(payload, 1.0)]
        }
        self.named_sets: Dict[str, list[dict[str, Any]]] = {
            "PASSAGE_PLAN": [{"summary": "Sample passage"}],
            "GPS": [gps_record],
        }

    async def _close_connection_pool(self) -> None:  # pragma: no cover - defensive
        self.closed = True

    async def read_set(
        self, sensor_id: str, datetime_range: Any | None = None
    ) -> list[dict[str, Any]]:
        return self.named_sets.get(sensor_id, [])

    async def write_set(self, sensor_id: str, payload: dict[str, Any]) -> None:
        self.named_sets.setdefault(sensor_id, []).append(payload)

    async def read_hashed_set(
        self, key: str, datetime_value: datetime | None = None
    ) -> dict[str, Any]:
        if key == "JOURNEY":
            data = JourneyData(
                timestamp=datetime(2024, 1, 1, 12, tzinfo=timezone.utc),
                end_datetime=datetime(2024, 1, 1, 12, tzinfo=timezone.utc),
                start_latitude="5123.46",
                start_longitude="00123.99",
                end_latitude="5123.50",
                end_longitude="00124.01",
            )
            return data.model_dump(mode="json")
        return {}

    @asynccontextmanager
    async def get_connection(self):
        try:
            yield self
        finally:
            return

    async def delete(self, key: str) -> None:
        self.sorted_sets.pop(key, None)

    async def zcard(self, key: str) -> int:
        return len(self.sorted_sets.get(key, []))

    async def zrevrangebyscore(
        self,
        key: str,
        max: str | float = "+inf",
        min: str | float = "-inf",
        withscores: bool = False,
    ) -> list[Any]:
        entries = self.sorted_sets.get(key, [])
        if withscores:
            return entries
        return [value for value, _ in entries]


class DummyGPSInterface:
    """Stubbed GPS interface exposing deterministic responses for tests."""

    def __init__(self, _redis_client: DummyRedisClient) -> None:
        reference_time = datetime(2024, 1, 1, 12, tzinfo=timezone.utc)
        self.raise_latest = False
        self.latest_model = GPSRedisData(
            timestamp=reference_time,
            status=GPSStatus.ACTIVE,
            latitude_nmea="5123.46",
            longitude_nmea="00123.99",
        )
        self.history_payload = [self.latest_model.model_dump(mode="json")]

    async def read_gps_latest(self, active: bool = False) -> GPSRedisData:
        if self.raise_latest:
            raise RuntimeError("GPS unavailable")
        return self.latest_model

    async def read_gps_all_history(self, active: bool = False) -> list[dict[str, Any]]:
        return self.history_payload

    async def read_gps_history_time_series(
        self,
        start_datetime: datetime,
        end_datetime: datetime,
        active: bool = False,
    ) -> list[dict[str, Any]]:
        return self.history_payload

    async def read_gps_history_length(
        self, length: int, active: bool = False
    ) -> list[dict[str, Any]]:
        return self.history_payload[:length]


class DummyCompassInterface:
    def __init__(self, _redis_client: DummyRedisClient) -> None:
        self.calls = 0
        self.history = [
            CompassRedisData(
                timestamp=datetime(2024, 1, 1, 12, tzinfo=timezone.utc),
                heading=123,
            ).model_dump(mode="json")
        ]

    async def read_heading_history_length(
        self, length: int, active: bool = False
    ) -> list[dict[str, Any]]:
        return self.history[:length]

    async def read_heading_history_all(
        self, active: bool = False
    ) -> list[dict[str, Any]]:
        return self.history


class DummyVelocityCalculator:
    def __init__(
        self, gps_interface: DummyGPSInterface, redis_client: DummyRedisClient
    ) -> None:
        self.gps_interface = gps_interface
        self.redis_client = redis_client
        self.velocity = GPSVelocity(
            timestamp=datetime(2024, 1, 1, 12, tzinfo=timezone.utc),
            speed_over_ground=7.2,
            course_over_ground=182.0,
            number_of_measurements=2,
        )

    async def read_velocity_latest(self, active: bool = False) -> GPSVelocity:
        return self.velocity


class DummyLogTracker:
    def __init__(
        self,
        gps_interface: DummyGPSInterface,
        redis_client: DummyRedisClient,
        velocity_calculator: DummyVelocityCalculator,
    ) -> None:
        timestamp = datetime(2024, 1, 1, 12, tzinfo=timezone.utc)

        class _JourneyRecord(dict):
            def __init__(self) -> None:
                super().__init__(
                    {
                        "timestamp": timestamp.isoformat().replace("+00:00", "Z"),
                        "end_datetime": timestamp.isoformat().replace("+00:00", "Z"),
                        "start_latitude": "5123.46",
                        "start_longitude": "00123.99",
                        "end_latitude": "5123.50",
                        "end_longitude": "00124.01",
                    }
                )
                self.distance_travelled = 12.5

        self.journey = _JourneyRecord()

    async def get_journey_set(self, _datetime: datetime | None = None) -> Any:
        return self.journey

    async def get_leg_set(self, _datetime: datetime | None = None) -> SimpleNamespace:
        return SimpleNamespace(course_over_ground=182.0)


class FakeStream:
    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False

    async def stream_text(self, delta: bool = True):
        yield "Hello"
        yield "World"


class FakeAgentWorkflow:
    def __init__(self, *_, **__):
        self.state = SimpleNamespace(
            message_history=[], workflow_plan=[], job_count=0, passage_plan=None
        )

    async def run(self, user_message: str, progress_callback=None):
        if progress_callback is not None:
            await progress_callback("chat")
        return f"Echo: {user_message}"


@pytest.fixture()
def app_client(monkeypatch: pytest.MonkeyPatch):
    """Provide a FastAPI test client with core dependencies stubbed out."""
    from src.kelder_api.app import main

    monkeypatch.setattr(main, "RedisClient", DummyRedisClient)
    monkeypatch.setattr(main, "GPSInterface", DummyGPSInterface)
    monkeypatch.setattr(main, "CompassInterface", DummyCompassInterface)
    monkeypatch.setattr(main, "VelocityCalculator", DummyVelocityCalculator)
    monkeypatch.setattr(main, "LogTracker", DummyLogTracker)
    from src.kelder_api.components.agentic_workflow import graph as graph_module

    monkeypatch.setattr(graph_module, "AgentWorkflow", FakeAgentWorkflow)
    monkeypatch.setattr(main, "AgentWorkflow", FakeAgentWorkflow)

    async def fake_height_of_tide():
        event_time = datetime.now(timezone.utc)
        return {
            "datetime_stamp": event_time.isoformat().replace("+00:00", "Z"),
            "event": "High Water",
            "height_of_tide": 1.2,
        }

    async def fake_tide_predictions(_date):
        event_time = datetime.now(timezone.utc) + timedelta(hours=1)

        @dataclass
        class _TideEvent:
            datetime_stamp: datetime
            event: str = "High Water"
            height_of_tide: float = 1.2

        return [_TideEvent(event_time)]

    monkeypatch.setattr(
        "src.kelder_api.routes.tidal_measurements.tidal_clients.get_height_of_tide_now",
        fake_height_of_tide,
    )
    monkeypatch.setattr(
        "src.kelder_api.routes.tidal_measurements.tidal_clients.get_tide_predictions",
        fake_tide_predictions,
    )
    monkeypatch.setattr(
        "src.kelder_api.routes.tidal_measurements.views.get_height_of_tide_now",
        fake_height_of_tide,
    )
    monkeypatch.setattr(
        "src.kelder_api.routes.tidal_measurements.views.get_tide_predictions",
        fake_tide_predictions,
    )

    class _AwareDatetime(datetime):
        def __new__(cls, *args, **kwargs):
            return datetime.__new__(cls, *args, **kwargs)

        def date(self, tzinfo=None):  # type: ignore[override]
            return datetime.date(self)

    class _DatetimeModule:
        @staticmethod
        def now(tz=None):
            return _AwareDatetime(2024, 1, 1, 12, 0, 0, tzinfo=tz or timezone.utc)

    monkeypatch.setattr(
        "src.kelder_api.routes.tidal_measurements.views.datetime",
        _DatetimeModule,
    )

    with TestClient(main.app, raise_server_exceptions=False) as client:
        yield client, main.app
