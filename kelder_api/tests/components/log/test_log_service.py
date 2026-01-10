from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from typing import Any

import pytest

from src.kelder_api.components.gps_new.models import GPSRedisData
from src.kelder_api.components.gps_new.types import GPSStatus
from src.kelder_api.components.log.exceptions import DataValidationError
from src.kelder_api.components.log.models import JourneyData, LegData
from src.kelder_api.components.log.service import LogTracker
from src.kelder_api.components.velocity.models import GPSVelocity
from tests.conftest import make_settings


class RecordingRedisClient:
    def __init__(self) -> None:
        self.hash_writes: list[tuple[str, Any]] = []
        self.storage: dict[str, dict[str, Any]] = {}

    async def write_hashed_set(
        self, key: str, data: Any, datetime: datetime | None = None
    ) -> None:
        self.hash_writes.append((key, data))
        self.storage[key] = data.model_dump(mode="json")

    async def read_hashed_set(
        self, key: str, datetime: datetime | None = None
    ) -> dict[str, Any]:
        return self.storage.get(key, {})


class RecordingDBManager:
    def __init__(self) -> None:
        self.saved: list[JourneyData] = []

    def save_from_journey_data(self, journey_data: JourneyData) -> None:
        self.saved.append(journey_data)


@dataclass
class StubGPSInterface:
    gps_data: GPSRedisData
    raise_index: bool = False

    async def read_gps_latest(self, active: bool = False) -> GPSRedisData:
        if self.raise_index:
            raise IndexError
        return self.gps_data


@dataclass
class StubVelocityCalculator:
    velocity: GPSVelocity
    raise_index: bool = False

    async def read_velocity_latest(self, active: bool = False) -> GPSVelocity:
        if self.raise_index:
            raise IndexError
        return self.velocity


@pytest.fixture
def configure_log_settings(monkeypatch: pytest.MonkeyPatch):
    def _configure(
        time_window_length: int = 60, tack_bearing_tolerance: int = 15
    ) -> None:
        settings = make_settings(
            log_tracker=SimpleNamespace(
                time_window_length=time_window_length,
                tack_bearing_tolerance=tack_bearing_tolerance,
            )
        )
        monkeypatch.setattr(
            "src.kelder_api.components.log.service.get_settings",
            lambda: settings,
        )

    return _configure


def _make_gps(
    timestamp: datetime,
    latitude: str = "00123.0000",
    longitude: str = "00123.0000",
) -> GPSRedisData:
    return GPSRedisData(
        timestamp=timestamp,
        status=GPSStatus.ACTIVE,
        latitude_nmea=latitude,
        longitude_nmea=longitude,
    )


def _make_velocity(
    timestamp: datetime,
    speed: float = 5.0,
    course: float = 120.0,
) -> GPSVelocity:
    return GPSVelocity(
        timestamp=timestamp,
        speed_over_ground=speed,
        course_over_ground=course,
        number_of_measurements=2,
    )


@pytest.fixture
def db_manager_stub():
    return RecordingDBManager()


@pytest.mark.asyncio
async def test_get_sensor_data_returns_latest_values(
    configure_log_settings, db_manager_stub
):
    configure_log_settings(time_window_length=120)
    timestamp = datetime(2024, 1, 1, 12, tzinfo=timezone.utc)
    gps = StubGPSInterface(_make_gps(timestamp))
    velocity = StubVelocityCalculator(_make_velocity(timestamp))
    tracker = LogTracker(gps, RecordingRedisClient(), velocity, db_manager_stub)

    gps_data, velocity_data = await tracker._get_sensor_data(now=timestamp)

    assert gps_data.timestamp == timestamp
    assert velocity_data.course_over_ground == 120.0


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "gps_raises, velocity_raises",
    [
        (True, False),
        (False, True),
    ],
)
async def test_get_sensor_data_missing_sources_raise_validation(
    configure_log_settings, gps_raises: bool, velocity_raises: bool, db_manager_stub
):
    configure_log_settings()
    timestamp = datetime(2024, 1, 1, 12, tzinfo=timezone.utc)
    gps = StubGPSInterface(_make_gps(timestamp), raise_index=gps_raises)
    velocity = StubVelocityCalculator(
        _make_velocity(timestamp), raise_index=velocity_raises
    )
    tracker = LogTracker(gps, RecordingRedisClient(), velocity, db_manager_stub)

    with pytest.raises(DataValidationError):
        await tracker._get_sensor_data(now=timestamp)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "gps_offset, velocity_offset",
    [
        (timedelta(seconds=120), timedelta(seconds=0)),
        (timedelta(seconds=0), timedelta(seconds=120)),
    ],
)
async def test_get_sensor_data_latency_violation_raises(
    configure_log_settings,
    gps_offset: timedelta,
    velocity_offset: timedelta,
    db_manager_stub,
):
    configure_log_settings(time_window_length=60)
    base_time = datetime(2024, 1, 1, 12, tzinfo=timezone.utc)
    gps_timestamp = base_time - gps_offset
    velocity_timestamp = base_time - velocity_offset

    gps = StubGPSInterface(_make_gps(gps_timestamp))
    velocity = StubVelocityCalculator(_make_velocity(velocity_timestamp))
    tracker = LogTracker(gps, RecordingRedisClient(), velocity, db_manager_stub)

    with pytest.raises(DataValidationError):
        await tracker._get_sensor_data(now=base_time)


@pytest.mark.asyncio
async def test_increment_log_initialises_journey_and_leg(
    configure_log_settings, db_manager_stub
):
    configure_log_settings()
    timestamp = datetime(2024, 1, 1, 12, tzinfo=timezone.utc)
    gps = StubGPSInterface(_make_gps(timestamp))
    velocity = StubVelocityCalculator(_make_velocity(timestamp, course=90.0))
    redis_client = RecordingRedisClient()
    tracker = LogTracker(gps, redis_client, velocity, db_manager_stub)

    await tracker.increment_log(now=timestamp)

    assert tracker.start_journey is False
    assert redis_client.hash_writes == [
        ("JOURNEY", tracker.journey_data),
        ("LEG", tracker.leg_data),
    ]
    assert tracker.leg_data.course_over_ground == 90.0


@pytest.mark.asyncio
async def test_increment_log_resets_leg_on_bearing_change(
    configure_log_settings, db_manager_stub
):
    configure_log_settings(tack_bearing_tolerance=10)
    timestamp = datetime(2024, 1, 1, 12, tzinfo=timezone.utc)
    gps = StubGPSInterface(_make_gps(timestamp))
    velocity = StubVelocityCalculator(_make_velocity(timestamp, course=100.0))
    redis_client = RecordingRedisClient()
    tracker = LogTracker(gps, redis_client, velocity, db_manager_stub)

    await tracker.increment_log(now=timestamp)

    second_time = timestamp + timedelta(seconds=5)
    gps.gps_data = _make_gps(second_time, latitude="00123.5000")
    velocity.velocity = _make_velocity(second_time, course=130.0)

    await tracker.increment_log(now=second_time)

    assert tracker.leg_data.start_datetime == second_time
    assert tracker.leg_data.course_over_ground == 130.0


@pytest.mark.asyncio
async def test_increment_log_updates_leg_when_within_tolerance(
    configure_log_settings, db_manager_stub
):
    configure_log_settings(tack_bearing_tolerance=40)
    timestamp = datetime(2024, 1, 1, 12, tzinfo=timezone.utc)
    gps = StubGPSInterface(_make_gps(timestamp))
    velocity = StubVelocityCalculator(_make_velocity(timestamp, course=200.0))
    tracker = LogTracker(gps, RecordingRedisClient(), velocity, db_manager_stub)

    await tracker.increment_log(now=timestamp)

    later = timestamp + timedelta(seconds=15)
    gps.gps_data = _make_gps(later)
    velocity.velocity = _make_velocity(later, course=220.0)

    await tracker.increment_log(now=later)

    assert tracker.leg_data.start_datetime == timestamp
    assert tracker.leg_data.course_over_ground == 220.0


@pytest.mark.asyncio
async def test_finish_journey_persists_and_resets_state(
    configure_log_settings, db_manager_stub
):
    configure_log_settings()
    timestamp = datetime(2024, 1, 1, 12, tzinfo=timezone.utc)
    gps = StubGPSInterface(_make_gps(timestamp))
    velocity = StubVelocityCalculator(_make_velocity(timestamp))
    tracker = LogTracker(gps, RecordingRedisClient(), velocity, db_manager_stub)

    await tracker.increment_log(now=timestamp)
    journey_snapshot = tracker.journey_data
    await tracker.finish_jouney()

    assert tracker.start_journey is True
    assert tracker.journey_data is None
    assert not hasattr(tracker, "leg_data")
    assert db_manager_stub.saved == [journey_snapshot]


@pytest.mark.asyncio
async def test_get_journey_set_returns_model_instance(
    configure_log_settings, db_manager_stub
):
    configure_log_settings()
    timestamp = datetime(2024, 1, 1, 12, tzinfo=timezone.utc)
    gps = StubGPSInterface(_make_gps(timestamp))
    velocity = StubVelocityCalculator(_make_velocity(timestamp))
    redis_client = RecordingRedisClient()
    tracker = LogTracker(gps, redis_client, velocity, db_manager_stub)

    await tracker.increment_log(now=timestamp)

    journey = await tracker.get_journey_set()
    assert isinstance(journey, JourneyData)

    leg = await tracker.get_leg_set()
    assert isinstance(leg, LegData)


@pytest.mark.asyncio
async def test_get_sets_return_none_when_validation_fails(
    configure_log_settings, db_manager_stub
):
    configure_log_settings()
    tracker = LogTracker(
        StubGPSInterface(_make_gps(datetime(2024, 1, 1, tzinfo=timezone.utc))),
        RecordingRedisClient(),
        StubVelocityCalculator(
            _make_velocity(datetime(2024, 1, 1, tzinfo=timezone.utc))
        ),
        db_manager_stub,
    )

    assert await tracker.get_journey_set() is None
    assert await tracker.get_leg_set() is None
