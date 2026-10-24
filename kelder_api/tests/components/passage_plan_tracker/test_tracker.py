from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from src.kelder_api.components.agentic_workflow.agents.models import (
    PassagePlan,
    Waypoint,
)
from src.kelder_api.components.passage_plan_tracker.service import PassagePlanTracker
from src.kelder_api.components.velocity.utils import cross_track_distance

# A route due north along 001°W.
PLAN = PassagePlan(
    departure_place_name="South",
    desination_place_name="North",
    course_to_steer=[
        Waypoint(name="South", latitude=50.0, longitude=-1.0),
        Waypoint(name="Middle", latitude=50.5, longitude=-1.0),
        Waypoint(name="North", latitude=51.0, longitude=-1.0),
    ],
).model_dump(mode="json")


def _tracker(latitude_nmea: str | None, longitude_nmea: str | None):
    redis_client = AsyncMock()
    redis_client.read_set.return_value = [PLAN]
    gps_interface = AsyncMock()
    gps_interface.read_gps_latest.return_value = (
        SimpleNamespace(latitude_nmea=latitude_nmea, longitude_nmea=longitude_nmea)
        if latitude_nmea
        else None
    )
    return PassagePlanTracker(redis_client, gps_interface)


@pytest.mark.parametrize(
    "longitude, side",
    [(-0.95, 1), (-1.05, -1)],
)
def test_cross_track_distance_is_positive_to_starboard(longitude, side):
    xte = cross_track_distance(50.0, -1.0, 51.0, -1.0, 50.5, longitude)

    # 0.05° of longitude at 50.5°N is about 1.9 nm.
    assert xte * side == pytest.approx(1.91, abs=0.02)


@pytest.mark.asyncio
async def test_progress_reports_dtw_and_xte_for_current_leg():
    # 50°12'N 000°57'W: on the first leg, east (starboard) of the track.
    progress = await _tracker("5012.0000", "-00057.0000").compute_progress()

    assert progress.next_waypoint_name == "Middle"
    assert progress.distance_to_waypoint == pytest.approx(18.0, abs=0.2)
    assert progress.cross_track_error == pytest.approx(1.92, abs=0.02)


@pytest.mark.asyncio
async def test_no_xte_before_the_first_waypoint():
    progress = await _tracker("4950.0000", "-00100.0000").compute_progress()

    assert progress.next_waypoint_index == 0
    assert progress.cross_track_error is None


@pytest.mark.asyncio
async def test_no_gps_fix_returns_none():
    assert await _tracker(None, None).compute_progress() is None
