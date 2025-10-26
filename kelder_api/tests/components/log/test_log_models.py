from __future__ import annotations

from datetime import datetime

import pytest

from src.kelder_api.components.log.models import JourneyData
from src.kelder_api.components.velocity import utils as velocity_utils


@pytest.mark.parametrize(
    "start_latitude, start_longitude, end_latitude, end_longitude",
    [
        ("00123.0000", "00123.0000", "00123.0000", "00123.0000"),
        ("00123.0000", "00123.0000", "00124.0000", "00123.5000"),
    ],
)
def test_journey_distance_matches_haversine(
    start_latitude: str,
    start_longitude: str,
    end_latitude: str,
    end_longitude: str,
) -> None:
    journey = JourneyData(
        timestamp=datetime(2024, 1, 1, 12, 0, 0),
        end_datetime=datetime(2024, 1, 1, 12, 0, 0),
        start_latitude=start_latitude,
        start_longitude=start_longitude,
        end_latitude=end_latitude,
        end_longitude=end_longitude,
    )

    expected = round(
        velocity_utils.haversine(
            velocity_utils.convert_to_decimal_degrees(start_latitude),
            velocity_utils.convert_to_decimal_degrees(end_latitude),
            velocity_utils.convert_to_decimal_degrees(start_longitude),
            velocity_utils.convert_to_decimal_degrees(end_longitude),
        ),
        1,
    )

    assert journey.distance_travelled == expected
