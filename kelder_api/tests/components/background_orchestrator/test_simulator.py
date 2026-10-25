from datetime import timedelta
from unittest.mock import AsyncMock

import pytest

from src.kelder_api.components.background_orchestrator.simulator import (
    GOOD_SIGNAL,
    Simulator,
)
from src.kelder_api.components.gps_new.models import GPSRedisData
from src.kelder_api.components.gps_new.types import GPSStatus
from src.kelder_api.components.redis_client.redis_client import RedisClient


@pytest.fixture()
def simulator() -> Simulator:
    return Simulator(AsyncMock(spec=RedisClient), "velocity_plan")


@pytest.mark.parametrize(
    "seconds,expected_status,expected_satellites",
    [
        (0, GPSStatus.VOID, 0),  # no fix
        (14, GPSStatus.VOID, 0),
        (16, GPSStatus.ACTIVE, 3),  # weak fix
        (31, GPSStatus.ACTIVE, len(GOOD_SIGNAL[1])),  # good fix from then on
        (600, GPSStatus.ACTIVE, len(GOOD_SIGNAL[1])),
    ],
)
def test_blackout_steps_through_fix_states(
    simulator: Simulator,
    seconds: int,
    expected_status: GPSStatus,
    expected_satellites: int,
) -> None:
    now = simulator.signal_started_at + timedelta(seconds=seconds)
    status, satellites, _ = simulator._signal_at(now)

    assert status == expected_status
    assert len(satellites) == expected_satellites


@pytest.mark.asyncio
async def test_lost_fix_reading_has_no_position(simulator: Simulator) -> None:
    await simulator.simulate_gps_sensor()

    written: GPSRedisData = simulator.redis_client.write_set.call_args.args[1]
    assert written.status == GPSStatus.VOID
    assert written.latitude_nmea == ""
    assert written.longitude_nmea == ""
