from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace

import pytest

from src.kelder_api.components.background_orchestrator.enums import VesselState
from src.kelder_api.components.background_orchestrator.orchestrator import (
    BackgroundTaskManager,
)
from src.kelder_api.components.background_orchestrator.stationary_strategy import (
    StationaryStrategy,
)
from src.kelder_api.components.background_orchestrator.underway_strategy import (
    UnderwayStrategy,
)
from tests.conftest import make_settings


class _ComponentStub:
    def __init__(
        self,
        label: str,
        method_name: str,
        call_sequence: list[str],
        raise_error: bool = False,
    ) -> None:
        self.label = label
        self.raise_error = raise_error
        self._call_sequence = call_sequence

        async def _method():
            self._call_sequence.append(f"{label}.{method_name}")
            if self.raise_error:
                raise RuntimeError(f"{label} failure")

        setattr(self, method_name, _method)


class _LogStub:
    def __init__(
        self,
        call_sequence: list[str],
        raise_error: bool = False,
        db_manager: object | None = None,
    ) -> None:
        self._call_sequence = call_sequence
        self.raise_error = raise_error
        self.finish_calls = 0

    async def increment_log(self) -> None:
        self._call_sequence.append("LOG.increment_log")
        if self.raise_error:
            raise RuntimeError("LOG failure")

    async def finish_journey(self) -> None:
        self.finish_calls += 1


class _VelocityReaderStub:
    def __init__(self, speed: float | None, raise_error: bool = False) -> None:
        self.speed = speed
        self.raise_error = raise_error

    async def read_velocity_latest(self, active: bool = True):
        if self.raise_error:
            raise RuntimeError("velocity unavailable")
        return SimpleNamespace(
            speed_over_ground=self.speed,
            timestamp=datetime(2024, 1, 1, 12, tzinfo=timezone.utc),
        )


@pytest.fixture
def configure_orchestrator_settings(monkeypatch: pytest.MonkeyPatch):
    def _configure(sog_threshold: float = 5.0) -> None:
        settings = make_settings(
            orchestrator=SimpleNamespace(sog_threshold=sog_threshold)
        )
        monkeypatch.setattr(
            "src.kelder_api.components.background_orchestrator.orchestrator.get_settings",
            lambda: settings,
        )

    return _configure


def test_register_components_initialises_dependencies(
    monkeypatch: pytest.MonkeyPatch, configure_orchestrator_settings
):
    configure_orchestrator_settings()

    class RedisStub:
        def __init__(self) -> None:
            pass

    class GPSStub:
        def __init__(self, redis_client) -> None:
            self.redis_client = redis_client

        async def stream_serial_data(self):
            return None

    class CompassStub:
        def __init__(self, redis_client) -> None:
            self.redis_client = redis_client

        async def read_heading_from_compass(self):
            return None

    class VelocityStub:
        def __init__(self, gps_interface, redis_client) -> None:
            self.gps_interface = gps_interface
            self.redis_client = redis_client

        async def calculate_gps_velocity(self):
            return None

        async def read_velocity_latest(self, active: bool = False):
            return SimpleNamespace(speed_over_ground=0.0)

    class LogStub:
        def __init__(
            self, gps_interface, redis_client, velocity_calculator, db_manager=None
        ) -> None:
            self.gps_interface = gps_interface
            self.redis_client = redis_client
            self.velocity_calculator = velocity_calculator

        async def increment_log(self):
            return None

        async def finish_journey(self):
            return None

    class DBStub:
        def save_from_journey_data(self, journey):
            return None

    class BilgeStub:
        def __init__(self, redis_client) -> None:
            self.redis_client = redis_client

        async def record_bilge_depth(self):
            return None

    monkeypatch.setattr(
        "src.kelder_api.components.background_orchestrator.orchestrator.RedisClient",
        RedisStub,
    )
    monkeypatch.setattr(
        "src.kelder_api.components.background_orchestrator.orchestrator.GPSInterface",
        GPSStub,
    )
    monkeypatch.setattr(
        "src.kelder_api.components.background_orchestrator.orchestrator.DBManager",
        DBStub,
    )
    monkeypatch.setattr(
        "src.kelder_api.components.background_orchestrator.orchestrator.CompassInterface",
        CompassStub,
    )
    monkeypatch.setattr(
        "src.kelder_api.components.background_orchestrator.orchestrator.VelocityCalculator",
        VelocityStub,
    )
    monkeypatch.setattr(
        "src.kelder_api.components.background_orchestrator.orchestrator.BilgeDepthSensor",
        BilgeStub,
    )
    monkeypatch.setattr(
        "src.kelder_api.components.background_orchestrator.orchestrator.LogTracker",
        LogStub,
    )

    manager = BackgroundTaskManager()

    components = manager.components

    assert set(components.keys()) == {
        "GPS",
        "COMPASS",
        "BILGE_DEPTH",
        "VELOCITY",
        "LOG",
        "DRIFT",
    }
    gps_instance = components["GPS"]["instance"]
    compass_instance = components["COMPASS"]["instance"]
    velocity_instance = components["VELOCITY"]["instance"]
    log_instance = components["LOG"]["instance"]

    assert isinstance(gps_instance, GPSStub)
    assert isinstance(compass_instance, CompassStub)
    assert isinstance(velocity_instance, VelocityStub)
    assert isinstance(log_instance, LogStub)

    assert velocity_instance.gps_interface is gps_instance
    assert velocity_instance.redis_client is manager.redis_client
    assert log_instance.gps_interface is gps_instance
    assert log_instance.velocity_calculator is velocity_instance

    assert components["GPS"]["method"] == "stream_serial_data"
    assert components["COMPASS"]["method"] == "read_heading_from_compass"
    assert components["BILGE_DEPTH"]["method"] == "record_bilge_depth"
    assert components["VELOCITY"]["method"] == "calculate_gps_velocity"
    assert components["LOG"]["method"] == "increment_log"
    assert components["DRIFT"]["method"] == "instantaneous_drift_calculator"


@pytest.mark.asyncio
async def test_underway_strategy_executes_all_components(
    monkeypatch: pytest.MonkeyPatch,
):
    call_sequence: list[str] = []
    components = {
        "GPS": {
            "instance": _ComponentStub("GPS", "stream_serial_data", call_sequence),
            "method": "stream_serial_data",
        },
        "COMPASS": {
            "instance": _ComponentStub(
                "COMPASS", "read_heading_from_compass", call_sequence
            ),
            "method": "read_heading_from_compass",
        },
        "VELOCITY": {
            "instance": _ComponentStub(
                "VELOCITY", "calculate_gps_velocity", call_sequence
            ),
            "method": "calculate_gps_velocity",
        },
        "LOG": {"instance": _LogStub(call_sequence), "method": "increment_log"},
    }

    sleep_calls: list[float] = []

    async def fake_sleep(delay: float) -> None:
        sleep_calls.append(delay)

    monkeypatch.setattr(
        "src.kelder_api.components.background_orchestrator.underway_strategy.asyncio.sleep",
        fake_sleep,
    )

    await UnderwayStrategy.execute(
        components=components, previous_vessel_state=VesselState.UNDERWAY
    )

    assert call_sequence == [
        "GPS.stream_serial_data",
        "COMPASS.read_heading_from_compass",
        "VELOCITY.calculate_gps_velocity",
        "LOG.increment_log",
    ]
    assert sleep_calls == [5]
    assert components["LOG"]["instance"].finish_calls == 0


@pytest.mark.asyncio
async def test_underway_strategy_handles_errors_and_finishes_journey(
    monkeypatch: pytest.MonkeyPatch,
):
    call_sequence: list[str] = []
    components = {
        "GPS": {
            "instance": _ComponentStub(
                "GPS", "stream_serial_data", call_sequence, raise_error=True
            ),
            "method": "stream_serial_data",
        },
        "COMPASS": {
            "instance": _ComponentStub(
                "COMPASS", "read_heading_from_compass", call_sequence
            ),
            "method": "read_heading_from_compass",
        },
        "BILGE_DEPTH": {
            "instance": _ComponentStub(
                "BILGE_DEPTH", "record_bilge_depth", call_sequence
            ),
            "method": "record_bilge_depth",
        },
        "VELOCITY": {
            "instance": _ComponentStub(
                "VELOCITY", "calculate_gps_velocity", call_sequence
            ),
            "method": "calculate_gps_velocity",
        },
        "DRIFT": {
            "instance": _ComponentStub(
                "DRIFT", "instantaneous_drift_calculator", call_sequence
            ),
            "method": "instantaneous_drift_calculator",
        },
        "LOG": {"instance": _LogStub(call_sequence), "method": "increment_log"},
    }

    async def fake_sleep(_: float) -> None:
        return None

    monkeypatch.setattr(
        "src.kelder_api.components.background_orchestrator.underway_strategy.asyncio.sleep",
        fake_sleep,
    )

    await UnderwayStrategy.execute(
        components=components, previous_vessel_state=VesselState.STATIONARY
    )

    assert "COMPASS.read_heading_from_compass" in call_sequence
    assert "VELOCITY.calculate_gps_velocity" in call_sequence
    assert "LOG.increment_log" in call_sequence
    assert components["LOG"]["instance"].finish_calls == 0


@pytest.mark.asyncio
async def test_stationary_strategy_executes_expected_components(
    monkeypatch: pytest.MonkeyPatch,
):
    call_sequence: list[str] = []
    components = {
        "GPS": {
            "instance": _ComponentStub("GPS", "stream_serial_data", call_sequence),
            "method": "stream_serial_data",
        },
        "BILGE_DEPTH": {
            "instance": _ComponentStub(
                "BILGE_DEPTH", "record_bilge_depth", call_sequence
            ),
            "method": "record_bilge_depth",
        },
        "VELOCITY": {
            "instance": _ComponentStub(
                "VELOCITY", "calculate_gps_velocity", call_sequence
            ),
            "method": "calculate_gps_velocity",
        },
        "LOG": {"instance": _LogStub(call_sequence), "method": "increment_log"},
    }

    async def fake_sleep(delay: float) -> None:
        call_sequence.append(f"sleep:{delay}")

    monkeypatch.setattr(
        "src.kelder_api.components.background_orchestrator.stationary_strategy.asyncio.sleep",
        fake_sleep,
    )

    await StationaryStrategy.execute(
        components=components, previous_vessel_state=VesselState.UNDERWAY
    )

    assert call_sequence == [
        "GPS.stream_serial_data",
        "BILGE_DEPTH.record_bilge_depth",
        "VELOCITY.calculate_gps_velocity",
        "sleep:10",
    ]
    assert components["LOG"]["instance"].finish_calls == 1


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "speed, threshold, previous_state, expected_state",
    [
        (3.0, 5.0, VesselState.UNDERWAY, VesselState.STATIONARY),
        (5.0, 5.0, VesselState.STATIONARY, VesselState.UNDERWAY),
        (None, 5.0, VesselState.UNDERWAY, VesselState.UNDERWAY),
    ],
)
async def test_calculate_new_state_resolves_vessel_state(
    configure_orchestrator_settings,
    speed: float | None,
    threshold: float,
    previous_state: VesselState,
    expected_state: VesselState,
):
    configure_orchestrator_settings(sog_threshold=threshold)
    manager = object.__new__(BackgroundTaskManager)
    manager.components = {"VELOCITY": {"instance": _VelocityReaderStub(speed)}}
    manager.settings = SimpleNamespace(sog_threshold=threshold)

    result = await BackgroundTaskManager.calculate_new_state(manager, previous_state)
    assert result == expected_state


@pytest.mark.asyncio
async def test_calculate_new_state_propagates_velocity_errors(
    configure_orchestrator_settings,
):
    configure_orchestrator_settings(sog_threshold=4.0)
    manager = object.__new__(BackgroundTaskManager)
    manager.components = {
        "VELOCITY": {"instance": _VelocityReaderStub(speed=6.0, raise_error=True)}
    }
    manager.settings = SimpleNamespace(sog_threshold=4.0)

    with pytest.raises(RuntimeError):
        await manager.calculate_new_state(VesselState.STATIONARY)
