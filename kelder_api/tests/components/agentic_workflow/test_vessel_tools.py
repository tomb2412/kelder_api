from __future__ import annotations

from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock

import pytest
from pydantic_ai.messages import (
    ModelMessage,
    ModelResponse,
    TextPart,
    ToolCallPart,
    ToolReturnPart,
)
from pydantic_ai.models.function import AgentInfo, FunctionModel

from src.kelder_api.components.agentic_workflow.agents.chatbot import chatbot_agent
from src.kelder_api.components.agentic_workflow.agents.models import (
    PassagePlan,
    Waypoint,
)
from src.kelder_api.components.agentic_workflow.models import VesselServices
from src.kelder_api.components.agentic_workflow.workflow import AgentWorkflow
from src.kelder_api.components.db_manager.models import (
    JourneyHistoryRecord,
    JourneyLocation,
)
from src.kelder_api.components.passage_plan_tracker.models import PassagePlanProgress
from src.kelder_api.components.passage_plan_tracker.service import REDIS_KEY
from src.kelder_api.components.redis_client.types import RedisSetNames


def _now() -> datetime:
    """Taken when each test builds its data, so slow runs don't skew reading ages."""
    return datetime.now(timezone.utc)


async def _call_tool(workflow: AgentWorkflow, name: str, **args: Any) -> Any:
    """Have the chatbot call one tool and return that tool's raw result."""
    returned: list[Any] = []

    def _model(messages: list[ModelMessage], info: AgentInfo) -> ModelResponse:
        for message in messages:
            for part in message.parts:
                if isinstance(part, ToolReturnPart):
                    returned.append(part.content)
                    return ModelResponse(parts=[TextPart("done")])
        return ModelResponse(parts=[ToolCallPart(name, args)])

    with chatbot_agent.override(model=FunctionModel(_model)):
        await workflow.run("test_user", f"call {name}")
    return returned[0]


def _vessel_services(**overrides: Any) -> VesselServices:
    gps = SimpleNamespace(
        timestamp=_now() - timedelta(minutes=2),
        latitude_nmea="5044.20",
        longitude_nmea="-00118.90",
    )
    journey = SimpleNamespace(
        timestamp=_now() - timedelta(hours=2),
        end_datetime=_now(),
        start_latitude="5050.40",
        start_longitude="-00118.60",
        end_latitude="5044.20",
        end_longitude="-00118.90",
        distance_travelled=6.2,
        gps_data="[[50.84, -1.31], [50.74, -1.32]]",
    )
    readers = {
        "gps_interface": SimpleNamespace(read_gps_latest=AsyncMock(return_value=gps)),
        "velocity_calculator": SimpleNamespace(
            read_velocity_latest=AsyncMock(
                return_value=SimpleNamespace(
                    speed_over_ground=5.2, course_over_ground=271.0
                )
            )
        ),
        "compass_interface": SimpleNamespace(
            read_heading_history_length=AsyncMock(
                return_value=[SimpleNamespace(heading=265.0)]
            )
        ),
        "drift_calculator": SimpleNamespace(
            read_drift_latest=AsyncMock(
                return_value=SimpleNamespace(drift_speed=0.4, drift_angle=6.0)
            )
        ),
        "log_tracker": SimpleNamespace(get_journey_set=AsyncMock(return_value=journey)),
    }
    readers.update(overrides)
    return VesselServices(**readers)


def _redis_sets(
    mock_redis_client: AsyncMock,
    bilge_age_minutes: float = 1,
    plan: PassagePlan | None = None,
) -> None:
    sets = {
        RedisSetNames.VESSEL_STATE: [
            {"timestamp": _now().isoformat(), "vessel_state": "underway"}
        ],
        RedisSetNames.BILGE_DEPTH: [
            {
                "timestamp": (
                    _now() - timedelta(minutes=bilge_age_minutes)
                ).isoformat(),
                "bilge_depth": 0.31,
            }
        ],
    }
    if plan is not None:
        sets[RedisSetNames.PASSAGE_PLAN] = [plan.model_dump(mode="json")]
    mock_redis_client.read_set.side_effect = lambda name, *_, **__: sets.get(name, [])


@pytest.mark.asyncio
async def test_vessel_status_matches_the_gps_card(mock_redis_client: AsyncMock):
    _redis_sets(mock_redis_client)
    workflow = AgentWorkflow(mock_redis_client, vessel_services=_vessel_services())

    status = await _call_tool(workflow, "get_vessel_status")

    assert status["position"]["latitude"] == pytest.approx(50.73667, abs=1e-5)
    assert status["position"]["longitude"] == pytest.approx(-1.315, abs=1e-5)
    assert status["position"]["fix_age_minutes"] == pytest.approx(2, abs=0.1)
    assert status["speed_over_ground_kn"] == 5.2
    assert status["course_over_ground_deg"] == 271.0
    assert status["heading_deg"] == 265.0
    assert status["drift_kn"] == 0.4
    assert status["log_today_nm"] == 6.2
    assert status["vessel_state"] == "underway"
    assert status["bilge"]["sensor_distance_m"] == 0.31
    assert status["bilge"]["stale"] is False
    assert status["route"] is None  # no passage plan in redis


def _store_progress(
    mock_redis_client: AsyncMock,
    cross_track_error: float | None,
    age: timedelta = timedelta(seconds=2),
) -> None:
    """Store route progress the way the worker does each tick."""
    progress = PassagePlanProgress(
        timestamp=_now() - age,
        distance_to_waypoint=2.4,
        next_waypoint_name="Cowes",
        next_waypoint_index=1,
        cross_track_error=cross_track_error,
    )
    values = {REDIS_KEY: progress.model_dump_json()}
    mock_redis_client.read_value.side_effect = lambda key: values.get(key)


@pytest.mark.asyncio
async def test_vessel_status_reports_the_workers_dtw_and_xte(
    mock_redis_client: AsyncMock,
):
    _redis_sets(mock_redis_client)
    _store_progress(mock_redis_client, cross_track_error=0.3)
    workflow = AgentWorkflow(mock_redis_client, vessel_services=_vessel_services())

    status = await _call_tool(workflow, "get_vessel_status")

    assert status["route"] == {
        "next_waypoint": "Cowes",
        "next_waypoint_number": 2,
        "dtw_nm": 2.4,
        "xte_nm": 0.3,
        "off_track_to": "starboard",
        "steer_to_regain_track": "port",
    }


@pytest.mark.asyncio
async def test_vessel_status_ignores_stale_route_progress(
    mock_redis_client: AsyncMock,
):
    _redis_sets(mock_redis_client)
    _store_progress(mock_redis_client, cross_track_error=None, age=timedelta(hours=1))
    workflow = AgentWorkflow(mock_redis_client, vessel_services=_vessel_services())

    status = await _call_tool(workflow, "get_vessel_status")

    assert status["route"] is None


@pytest.mark.asyncio
async def test_vessel_status_survives_a_failed_sensor(mock_redis_client: AsyncMock):
    _redis_sets(mock_redis_client, bilge_age_minutes=30)
    broken_gps = SimpleNamespace(
        read_gps_latest=AsyncMock(side_effect=RuntimeError("serial unplugged"))
    )
    workflow = AgentWorkflow(
        mock_redis_client,
        vessel_services=_vessel_services(gps_interface=broken_gps),
    )

    status = await _call_tool(workflow, "get_vessel_status")

    assert status["position"] is None
    assert status["speed_over_ground_kn"] == 5.2
    assert status["bilge"]["stale"] is True


@pytest.mark.asyncio
async def test_vessel_status_without_sensors_is_reported(
    mock_redis_client: AsyncMock,
):
    workflow = AgentWorkflow(mock_redis_client)

    status = await _call_tool(workflow, "get_vessel_status")

    assert status == "Live vessel data unavailable — sensors not configured."


def _ryde_to_camber() -> PassagePlan:
    return PassagePlan(
        departure_place_name="Ryde Harbour",
        desination_place_name="Camber Docks",
        course_to_steer=[
            Waypoint(name="Ryde Harbour", latitude=50.7326, longitude=-1.1544),
            Waypoint(name="Cowes", latitude=50.7556, longitude=-1.1415),
            Waypoint(name="Camber Docks", latitude=50.7912, longitude=-1.1065),
        ],
    )


@pytest.mark.asyncio
async def test_active_plan_gives_destination_and_eta(mock_redis_client: AsyncMock):
    plan = _ryde_to_camber()
    _redis_sets(mock_redis_client, plan=plan)
    _store_progress(mock_redis_client, cross_track_error=0.1)  # 2.4 nm to "Cowes"
    workflow = AgentWorkflow(mock_redis_client, vessel_services=_vessel_services())

    result = await _call_tool(workflow, "get_active_passage_plan")

    last_leg = plan.distance_between_waypoints[1]
    remaining = result["remaining"]
    assert result["destination"] == "Camber Docks"
    assert [wp["name"] for wp in result["waypoints"]] == [
        "Ryde Harbour",
        "Cowes",
        "Camber Docks",
    ]
    assert result["waypoints"][2]["leg_distance_nm"] == round(last_leg, 2)
    assert remaining["next_waypoint"] == "Cowes"
    assert remaining["distance_to_destination_nm"] == round(2.4 + last_leg, 2)
    assert remaining["eta_next_waypoint"]["minutes"] == round(2.4 / 5.2 * 60)
    assert remaining["eta_destination"]["minutes"] == round((2.4 + last_leg) / 5.2 * 60)


@pytest.mark.asyncio
async def test_active_plan_without_recent_progress(mock_redis_client: AsyncMock):
    _redis_sets(mock_redis_client, plan=_ryde_to_camber())
    _store_progress(mock_redis_client, cross_track_error=None, age=timedelta(hours=1))
    workflow = AgentWorkflow(mock_redis_client, vessel_services=_vessel_services())

    result = await _call_tool(workflow, "get_active_passage_plan")

    assert result["destination"] == "Camber Docks"
    assert result["remaining"] is None


@pytest.mark.asyncio
async def test_active_plan_has_no_eta_when_stopped(mock_redis_client: AsyncMock):
    _redis_sets(mock_redis_client, plan=_ryde_to_camber())
    _store_progress(mock_redis_client, cross_track_error=None)
    stopped = SimpleNamespace(
        read_velocity_latest=AsyncMock(
            return_value=SimpleNamespace(speed_over_ground=0.0, course_over_ground=None)
        )
    )
    workflow = AgentWorkflow(
        mock_redis_client,
        vessel_services=_vessel_services(velocity_calculator=stopped),
    )

    remaining = (await _call_tool(workflow, "get_active_passage_plan"))["remaining"]

    assert remaining["distance_to_destination_nm"] is not None
    assert remaining["eta_destination"] is None


@pytest.mark.asyncio
async def test_no_active_plan(mock_redis_client: AsyncMock):
    _redis_sets(mock_redis_client)
    workflow = AgentWorkflow(mock_redis_client, vessel_services=_vessel_services())

    result = await _call_tool(workflow, "get_active_passage_plan")

    assert result == "No active passage plan."


@pytest.mark.asyncio
async def test_todays_journey(mock_redis_client: AsyncMock):
    workflow = AgentWorkflow(mock_redis_client, vessel_services=_vessel_services())

    journey = await _call_tool(workflow, "get_todays_journey")

    assert journey["duration_minutes"] == 120
    assert journey["distance_nm"] == 6.2
    assert journey["track_points"] == 2
    assert journey["start_position"]["latitude"] == pytest.approx(50.84, abs=1e-5)


def _save_trip(db_manager, departed: datetime, distance: float) -> int:
    record = JourneyHistoryRecord(
        departure_time=departed,
        arrival_time=departed + timedelta(minutes=90),
        departure_location=JourneyLocation(latitude="5050.40", longitude="-00118.60"),
        arrival_location=JourneyLocation(latitude="5044.20", longitude="-00118.90"),
        distance_travelled=distance,
        gps_data="[]",
    )
    return db_manager.save_trip(record).unique_key


@pytest.mark.asyncio
async def test_previous_journeys_newest_first(mock_redis_client, db_manager):
    _save_trip(db_manager, datetime(2026, 10, 10, 9, tzinfo=timezone.utc), 4.0)
    newest = _save_trip(db_manager, datetime(2026, 10, 18, 9, tzinfo=timezone.utc), 7.5)
    workflow = AgentWorkflow(mock_redis_client, db_manager=db_manager)

    journeys = await _call_tool(workflow, "list_previous_journeys")

    assert [j["distance_nm"] for j in journeys] == [7.5, 4.0]
    assert journeys[0]["journey_id"] == newest
    assert journeys[0]["duration_minutes"] == 90
    assert journeys[0]["end_position"]["latitude"] == pytest.approx(50.73667, abs=1e-5)


@pytest.mark.asyncio
async def test_previous_journeys_filtered_by_date(mock_redis_client, db_manager):
    _save_trip(db_manager, datetime(2026, 10, 10, 9, tzinfo=timezone.utc), 4.0)
    _save_trip(db_manager, datetime(2026, 10, 18, 9, tzinfo=timezone.utc), 7.5)
    workflow = AgentWorkflow(mock_redis_client, db_manager=db_manager)

    journeys = await _call_tool(
        workflow,
        "list_previous_journeys",
        from_date="2026-10-17",
        to_date="2026-10-19",
    )
    nothing = await _call_tool(
        workflow, "list_previous_journeys", from_date="2026-10-20"
    )

    assert [j["distance_nm"] for j in journeys] == [7.5]
    assert nothing == "No journeys found for that period."
