from __future__ import annotations

from datetime import datetime

import pytest

from src.kelder_api.components.velocity import utils


@pytest.mark.parametrize(
    "nmea, lon, expected",
    [
        ("00123.5000", True, 1 + 23.5 / 60),
        ("5123.7500", False, 7.0625),
        ("12", True, 0.2),  # zero padded input handled by zfill
    ],
)
def test_convert_to_decimal_degrees(nmea: str, lon: bool, expected: float):
    assert utils.convert_to_decimal_degrees(nmea, lon=lon) == pytest.approx(expected)


@pytest.mark.parametrize(
    "latitude_start, longitude_start, latitude_end, longitude_end, expected",
    [
        (0.0, 0.0, 0.0, 1.0, 90.0),
        (0.0, 0.0, 1.0, 0.0, 0.0),
        (0.0, 0.0, -1.0, 0.0, 180.0),
    ],
)
def test_bearing_degrees(
    latitude_start: float,
    longitude_start: float,
    latitude_end: float,
    longitude_end: float,
    expected: float,
) -> None:
    result = utils.bearing_degrees(
        latitude_start, longitude_start, latitude_end, longitude_end
    )
    assert result == pytest.approx(expected)


@pytest.mark.parametrize(
    "bearings, expected",
    [
        ([10, 20, 30], 20.0),
        ([350, 10], 0.0),
        ([0, 180], 90.0),
    ],
)
def test_average_bearing(bearings, expected):
    assert utils.average_bearing(bearings) == pytest.approx(expected)


@pytest.mark.parametrize(
    "time_start, time_end, expected",
    [
        (datetime(2024, 1, 1, 12, 0, 0), datetime(2024, 1, 1, 12, 0, 5), 5),
        (datetime(2024, 1, 1, 12, 0, 5), datetime(2024, 1, 1, 12, 0, 5), 0),
    ],
)
def test_time_difference_seconds(time_start, time_end, expected):
    assert utils.time_difference_seconds(time_start, time_end) == expected


@pytest.mark.parametrize(
    "start, end",
    [
        ("12:00:00+00:00", datetime(1900, 1, 1, 12, 0, 0)),
        ("00:00:05+00:00", datetime(1900, 1, 1, 0, 0, 5)),
    ],
)
def test_parse_timestamp(start: str, end: datetime):
    assert utils.parse_timestamp(start) == end


def test_parse_timestamp_invalid_format_raises():
    with pytest.raises(ValueError):
        utils.parse_timestamp("not-a-time")


def test_haversine_distance_zero_when_points_match():
    assert utils.haversine(51.5, 51.5, 0.1, 0.1) == pytest.approx(0.0)


@pytest.mark.parametrize(
    "latitude_start, latitude_end, longitude_start, longitude_end",
    [
        (0.0, 1.0, 0.0, 0.0),
        (10.0, 10.0, 0.0, 1.0),
    ],
)
def test_haversine_positive_distance(
    latitude_start, latitude_end, longitude_start, longitude_end
):
    result = utils.haversine(
        latitude_start, latitude_end, longitude_start, longitude_end
    )
    assert result > 0.0
