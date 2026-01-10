from datetime import datetime, timezone
from typing import Dict, List
from unittest.mock import AsyncMock

import pytest

from src.kelder_api.components.gps_new.interface import GPSInterface
from src.kelder_api.components.gps_new.models import (
    GPGSAActiveSatellites,
    GPGSVSatellitesInView,
    GPRMCRecommendedCourse,
    GPSRedisData,
)
from src.kelder_api.components.gps_new.types import GPSStatus
from src.kelder_api.components.gps_new.utils import round_ddmm
from src.kelder_api.components.redis_client.redis_client import RedisClient


@pytest.fixture()
def mock_redis_client() -> AsyncMock:
    """Provide an async mock of the redis client for GPSInterface tests."""
    client = AsyncMock(spec=RedisClient)
    return client


@pytest.fixture()
def gps_interface(mock_redis_client: AsyncMock) -> GPSInterface:
    """Return a GPS interface that uses the mocked redis client."""
    return GPSInterface(redis_client=mock_redis_client)


@pytest.fixture()
def sample_gps_payload() -> Dict[str, str | float | List[int]]:
    """Reusable payload mirroring the structure returned from redis."""
    timestamp = datetime(2024, 1, 1, 12, 30, tzinfo=timezone.utc)
    return {
        "timestamp": timestamp,
        "status": GPSStatus.ACTIVE,
        "latitude_nmea": "5123.4567",
        "longitude_nmea": "00123.9876",
        "active_prn": [1, 2, 3],
        "hdop": 0.9,
        "satellites_in_view": {},
    }


@pytest.mark.parametrize(
    "raw_value,deg_digits,expected",
    [
        ("5123.4567", 2, "5123.46"),
        ("00123.9876", 3, "00123.99"),
        ("9020.1234", 2, "9020.12"),
    ],
)
def test_round_ddmm_truncates_to_two_decimal_minutes(
    raw_value: str, deg_digits: int, expected: str
) -> None:
    """Check utility rounding keeps degrees and rounds minutes to two decimals."""
    result = round_ddmm(raw_value, deg_digits)
    assert result == expected


@pytest.mark.parametrize(
    "latitude,longitude",
    [
        ("5123.4567", "00123.9876"),
        ("0000.0000", "00000.0000"),
    ],
)
def test_gps_redis_data_coordinate_rounding(latitude: str, longitude: str) -> None:
    """Ensure GPSRedisData normalises latitude/longitude on creation."""
    data = GPSRedisData(
        timestamp=datetime.now(timezone.utc),
        status=GPSStatus.ACTIVE,
        latitude_nmea=latitude,
        longitude_nmea=longitude,
    )
    expected_lat = round_ddmm(latitude, 2)
    expected_lon = round_ddmm(longitude, 3)
    assert data.latitude_nmea == expected_lat
    assert data.longitude_nmea == expected_lon


def test_gps_redis_data_invalid_coordinate_type_fails() -> None:
    """Non-string coordinates should raise a type error."""
    with pytest.raises(TypeError):
        GPSRedisData(
            timestamp=datetime.now(timezone.utc),
            status=GPSStatus.ACTIVE,
            latitude_nmea=1234,
            longitude_nmea="00123.9876",
        )


def test_round_ddmm_invalid_input_raises() -> None:
    """round_ddmm should surface helpful errors when input is not DDMM strings."""
    with pytest.raises(TypeError):
        round_ddmm(1234, 2)  # type: ignore[arg-type]

    with pytest.raises(ValueError):
        round_ddmm("invalid", 2)


@pytest.mark.asyncio
async def test_write_gps_builds_payload_and_writes_to_redis(
    gps_interface: GPSInterface, mock_redis_client: AsyncMock
) -> None:
    """Exercise write path to ensure Redis receives a fully populated model."""
    satellites = GPGSVSatellitesInView()
    satellites.add_satellite(prn=1, elevation=45, azimuth=180, snr=35)

    gprmc = GPRMCRecommendedCourse(
        timestamp=datetime(2024, 1, 1, 12, 0, tzinfo=timezone.utc),
        status=GPSStatus.ACTIVE,
        latitude_nmea="5123.4567",
        longitude_nmea="00123.9876",
    )
    gpgsa = GPGSAActiveSatellites(satilite_prns=[1], satilite_count=1, hdop=0.9)

    # Act: trigger the write against the mocked client.
    await gps_interface.write_gps(satellites, gprmc, gpgsa)

    mock_redis_client.write_set.assert_awaited_once()
    args, _ = mock_redis_client.write_set.await_args
    assert args[0] == "GPS"
    persisted_model = args[1]
    assert isinstance(persisted_model, GPSRedisData)
    assert persisted_model.latitude_nmea.endswith(".46")


@pytest.mark.asyncio
async def test_read_gps_latest_returns_none_when_no_data(
    gps_interface: GPSInterface, mock_redis_client: AsyncMock
) -> None:
    """Reading latest measurement handles empty redis responses gracefully."""
    mock_redis_client.read_set.return_value = []

    result = await gps_interface.read_gps_latest(active=False)

    assert result is None


@pytest.mark.asyncio
@pytest.mark.parametrize("active", [True, False])
async def test_read_gps_latest_uses_active_flag(
    gps_interface: GPSInterface,
    mock_redis_client: AsyncMock,
    sample_gps_payload: Dict[str, str | float | List[int]],
    active: bool,
) -> None:
    """Active flag should delegate to the filtered helper before returning data."""
    if active:
        gps_interface.read_active_gps_measurements = AsyncMock(
            return_value=[GPSRedisData(**sample_gps_payload)]
        )
    else:
        mock_redis_client.read_set.return_value = [sample_gps_payload]

    result = await gps_interface.read_gps_latest(active=active)

    assert isinstance(result, GPSRedisData)


@pytest.mark.asyncio
async def test_read_gps_history_length_truncates_results(
    gps_interface: GPSInterface,
    mock_redis_client: AsyncMock,
    sample_gps_payload: Dict[str, str | float | List[int]],
) -> None:
    """Ensure length parameter limits the number of returned models."""
    mock_redis_client.read_set.return_value = [sample_gps_payload for _ in range(5)]

    history = await gps_interface.read_gps_history_length(length=3, active=False)

    assert len(history) == 3


@pytest.mark.asyncio
async def test_read_gps_history_time_series_filters_active(
    gps_interface: GPSInterface,
    mock_redis_client: AsyncMock,
    sample_gps_payload: Dict[str, str | float | List[int]],
) -> None:
    """Active flag should remove void measurements from the returned series."""
    void_payload = sample_gps_payload.copy()
    void_payload["status"] = GPSStatus.VOID
    mock_redis_client.read_set.return_value = [sample_gps_payload, void_payload]

    series = await gps_interface.read_gps_history_time_series(
        start_datetime=datetime(2024, 1, 1, tzinfo=timezone.utc),
        end_datetime=datetime(2024, 1, 2, tzinfo=timezone.utc),
        active=True,
    )

    assert len(series) == 1
    assert series[0].status == GPSStatus.ACTIVE


@pytest.mark.asyncio
async def test_read_gps_all_history_active_branch(
    gps_interface: GPSInterface,
    mock_redis_client: AsyncMock,
    sample_gps_payload: Dict[str, str | float | List[int]],
) -> None:
    """Active version of all-history should delegate to the dedicated helper."""
    gps_interface.read_active_gps_measurements = AsyncMock(
        return_value=[GPSRedisData(**sample_gps_payload)]
    )

    history = await gps_interface.read_gps_all_history(active=True)

    assert len(history) == 1
    assert history[0].status == GPSStatus.ACTIVE
