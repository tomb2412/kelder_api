from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from typing import Any

import pytest

from src.kelder_api.components.gps_new.models import GPSRedisData
from src.kelder_api.components.gps_new.types import GPSStatus
from src.kelder_api.components.velocity import utils as velocity_utils
from src.kelder_api.components.velocity.models import CalculationType, GPSVelocity
from src.kelder_api.components.velocity.service import VelocityCalculator


class RecordingRedisClient:
    """In-memory redis stub that mimics the velocity sorted set."""

    def __init__(self, seed: list[dict[str, Any]] | None = None) -> None:
        self._storage: dict[str, list[dict[str, Any]]] = {"VELOCITY": seed or []}
        self.writes: list[tuple[str, GPSVelocity]] = []

    async def write_set(self, sensor_id: str, gps_velocity: GPSVelocity) -> None:
        payload = gps_velocity.model_dump(mode="json")
        # Persist newest first to match zrevrangebyscore ordering
        self._storage.setdefault(sensor_id, [])
        self._storage[sensor_id].insert(0, payload)
        self.writes.append((sensor_id, gps_velocity))

    async def read_set(
        self, sensor_id: str, datetime_range: list[datetime] | None = None
    ) -> list[dict[str, Any]]:
        return list(self._storage.get(sensor_id, []))


@dataclass
class RecordingGPSInterface:
    history: list[GPSRedisData]
    calls: list[tuple[str, Any]] = field(default_factory=list)

    async def read_gps_history_length(
        self, length: int, active: bool = False
    ) -> tuple[list[GPSRedisData], datetime]:
        self.calls.append(("length", length, active))
        return self.history[:length], datetime.now(timezone.utc)

    async def read_gps_history_time_series(
        self,
        start_datetime: datetime,
        end_datetime: datetime,
        active: bool = False,
    ) -> list[GPSRedisData]:
        self.calls.append(("timeseries", start_datetime, end_datetime, active))
        return list(self.history)


@pytest.fixture
def configure_velocity_settings(monkeypatch: pytest.MonkeyPatch):
    """Allow tests to override VelocityCalculator settings per scenario."""

    def _configure(
        calculation_type: CalculationType = CalculationType.TIMESERIES,
        history: int = 3,
    ) -> None:
        settings = SimpleNamespace(
            velocity=SimpleNamespace(
                velocity_calculation_type=calculation_type,
                gps_velocity_history=history,
            )
        )
        monkeypatch.setattr(
            "src.kelder_api.components.velocity.service.get_settings",
            lambda: settings,
        )

    return _configure


def _make_gps_point(
    timestamp: datetime,
    latitude_nmea: str,
    longitude_nmea: str,
    status: GPSStatus = GPSStatus.ACTIVE,
) -> GPSRedisData:
    return GPSRedisData(
        timestamp=timestamp,
        status=status,
        latitude_nmea=latitude_nmea,
        longitude_nmea=longitude_nmea,
    )


def _expected_aggregates(
    history: list[GPSRedisData],
) -> tuple[float | None, float | None]:
    if len(history) <= 1:
        return None, None

    speeds: list[float] = []
    bearings: list[float] = []
    for index in range(len(history) - 1):
        current = history[index]
        nxt = history[index + 1]
        lat_start = velocity_utils.convert_to_decimal_degrees(
            current.latitude_nmea, lon=False
        )
        lat_end = velocity_utils.convert_to_decimal_degrees(
            nxt.latitude_nmea, lon=False
        )
        lon_start = velocity_utils.convert_to_decimal_degrees(current.longitude_nmea)
        lon_end = velocity_utils.convert_to_decimal_degrees(nxt.longitude_nmea)
        distance = velocity_utils.haversine(lat_start, lat_end, lon_start, lon_end)
        time_delta = velocity_utils.time_difference_seconds(
            time_end=current.timestamp,
            time_start=nxt.timestamp,
        )
        bearings.append(
            velocity_utils.bearing_degrees(lat_start, lon_start, lat_end, lon_end)
        )
        if time_delta == 0:
            speeds.append(0.0)
        else:
            speeds.append(distance / time_delta)

    course = velocity_utils.average_bearing(bearings)
    average_speed = sum(speeds) / len(speeds)
    return average_speed, course


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "history_builder, expectation",
    [
        pytest.param(lambda base_time: [], "no-data", id="no-gps-history"),
        pytest.param(
            lambda base_time: [_make_gps_point(base_time, "5123.0000", "00123.0000")],
            "single-point",
            id="single-gps-measurement",
        ),
        pytest.param(
            lambda base_time: [
                _make_gps_point(base_time, "5123.0300", "00123.0500"),
                _make_gps_point(
                    base_time - timedelta(seconds=5),
                    "5123.0000",
                    "00123.0000",
                ),
            ],
            "valid",
            id="multiple-gps-measurements",
        ),
        pytest.param(
            lambda base_time: [
                _make_gps_point(base_time, "5123.0300", "00123.0500"),
                _make_gps_point(base_time, "5123.0000", "00123.0000"),
            ],
            "zero-time-difference",
            id="zero-time-difference",
        ),
    ],
)
async def test_calculate_gps_velocity_writes_expected_payload(
    configure_velocity_settings,
    history_builder,
    expectation,
):
    configure_velocity_settings(CalculationType.TIMESERIES, history=5)
    now = datetime(2024, 1, 1, 12, 0, 10, tzinfo=timezone.utc)
    history = history_builder(now)
    gps_interface = RecordingGPSInterface(history=history)
    redis_client = RecordingRedisClient()

    calculator = VelocityCalculator(gps_interface, redis_client)
    await calculator.calculate_gps_velocity(datetime_now=now)

    assert redis_client.writes, "VelocityCalculator.write_velocity was not invoked"
    redis_key, payload = redis_client.writes[0]
    assert redis_key == "VELOCITY"
    assert payload.timestamp == now
    assert payload.number_of_measurements == len(history)

    if expectation == "valid":
        expected_speed, expected_course = _expected_aggregates(history)
        assert payload.speed_over_ground == pytest.approx(expected_speed)
        assert payload.course_over_ground == pytest.approx(expected_course)
    elif expectation == "zero-time-difference":
        expected_speed, expected_course = _expected_aggregates(history)
        assert payload.speed_over_ground == pytest.approx(0.0)
        assert payload.course_over_ground == pytest.approx(expected_course)
    else:
        assert payload.speed_over_ground is None
        assert payload.course_over_ground is None


@pytest.mark.asyncio
async def test_calculate_gps_velocity_uses_length_strategy(configure_velocity_settings):
    configure_velocity_settings(CalculationType.LENGTH, history=4)
    now = datetime(2024, 1, 1, 12, tzinfo=timezone.utc)
    history = [
        _make_gps_point(now - timedelta(seconds=idx), "5123.0000", "00123.0000")
        for idx in range(3)
    ]
    gps_interface = RecordingGPSInterface(history=history)
    redis_client = RecordingRedisClient()

    calculator = VelocityCalculator(gps_interface, redis_client)
    await calculator.calculate_gps_velocity(datetime_now=now)

    assert ("length", 4, True) in gps_interface.calls


@pytest.mark.asyncio
async def test_write_velocity_delegates_to_redis():
    now = datetime(2024, 1, 1, 12, tzinfo=timezone.utc)
    velocity = GPSVelocity(
        timestamp=now,
        speed_over_ground=4.2,
        course_over_ground=182.5,
        number_of_measurements=3,
    )
    redis_client = RecordingRedisClient()
    gps_interface = RecordingGPSInterface(history=[])

    calculator = VelocityCalculator(gps_interface, redis_client)
    await calculator.write_velocity(velocity)

    assert redis_client.writes == [("VELOCITY", velocity)]


@pytest.mark.asyncio
async def test_read_velocity_latest_returns_active_sample(
    monkeypatch: pytest.MonkeyPatch,
):
    data = [
        {
            "timestamp": datetime(2024, 1, 1, 11, tzinfo=timezone.utc),
            "speed_over_ground": None,
            "course_over_ground": None,
            "number_of_measurements": 0,
        },
        {
            "timestamp": datetime(2024, 1, 1, 12, tzinfo=timezone.utc),
            "speed_over_ground": 3.5,
            "course_over_ground": 90.0,
            "number_of_measurements": 2,
        },
    ]
    redis_client = RecordingRedisClient(seed=data)
    gps_interface = RecordingGPSInterface(history=[])
    calculator = VelocityCalculator(gps_interface, redis_client)

    latest = await calculator.read_velocity_latest(active=True)
    assert latest.speed_over_ground == 3.5
    assert latest.course_over_ground == 90.0


@pytest.mark.asyncio
async def test_read_velocity_latest_returns_fallback_when_empty():
    redis_client = RecordingRedisClient(seed=[])
    gps_interface = RecordingGPSInterface(history=[])
    calculator = VelocityCalculator(gps_interface, redis_client)

    latest = await calculator.read_velocity_latest(active=True)
    assert latest.speed_over_ground is None
    assert latest.number_of_measurements == 0


@pytest.mark.asyncio
async def test_read_velocity_all_filters_none_when_active():
    data = [
        {
            "timestamp": datetime(2024, 1, 1, 12, tzinfo=timezone.utc),
            "speed_over_ground": 3.5,
            "course_over_ground": 90.0,
            "number_of_measurements": 2,
        },
        {
            "timestamp": datetime(2024, 1, 1, 11, tzinfo=timezone.utc),
            "speed_over_ground": None,
            "course_over_ground": 270.0,
            "number_of_measurements": 1,
        },
    ]
    redis_client = RecordingRedisClient(seed=data)
    gps_interface = RecordingGPSInterface(history=[])
    calculator = VelocityCalculator(gps_interface, redis_client)

    active_only = await calculator.read_velocity_all(active=True)
    assert len(active_only) == 1
    assert active_only[0].speed_over_ground == 3.5


@pytest.mark.asyncio
async def test_read_velocity_all_returns_all_when_not_active():
    data = [
        {
            "timestamp": datetime(2024, 1, 1, 12, tzinfo=timezone.utc),
            "speed_over_ground": 3.5,
            "course_over_ground": 90.0,
            "number_of_measurements": 2,
        },
        {
            "timestamp": datetime(2024, 1, 1, 11, tzinfo=timezone.utc),
            "speed_over_ground": None,
            "course_over_ground": 270.0,
            "number_of_measurements": 1,
        },
    ]
    redis_client = RecordingRedisClient(seed=data)
    gps_interface = RecordingGPSInterface(history=[])
    calculator = VelocityCalculator(gps_interface, redis_client)

    all_data = await calculator.read_velocity_all(active=False)
    assert len(all_data) == 2
