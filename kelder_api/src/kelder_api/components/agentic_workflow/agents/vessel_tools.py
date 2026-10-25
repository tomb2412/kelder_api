import json
from datetime import date, datetime, timedelta, timezone
from typing import Annotated, Any, Awaitable, TypeVar

from pydantic import Field
from pydantic_ai import RunContext
from pydantic_ai.toolsets import FunctionToolset

from src.kelder_api.components.agentic_workflow.models import ChatDeps
from src.kelder_api.components.background_orchestrator.enums import VesselStateModel
from src.kelder_api.components.passage_plan_tracker.models import PassagePlanProgress
from src.kelder_api.components.passage_plan_tracker.service import (
    PassagePlanTracker,
    distance_remaining,
    read_active_plan,
    read_stored_progress,
)
from src.kelder_api.components.redis_client.redis_client import RedisClient
from src.kelder_api.components.redis_client.types import RedisSetNames
from src.kelder_api.components.ultrasound.models import BilgeDepth
from src.kelder_api.components.velocity.utils import convert_to_decimal_degrees
from src.kelder_api.configuration.logging_controller import get_logger
from src.kelder_api.configuration.settings import get_settings

logger = get_logger(__name__, "agent_workflow.vessel_tools")

T = TypeVar("T")

vessel_toolset: FunctionToolset[ChatDeps] = FunctionToolset()


def _position(latitude_nmea: str, longitude_nmea: str) -> dict[str, float] | None:
    """Convert stored NMEA strings to decimal degrees for the model."""
    try:
        return {
            "latitude": round(convert_to_decimal_degrees(latitude_nmea), 5),
            "longitude": round(convert_to_decimal_degrees(longitude_nmea), 5),
        }
    except ValueError:
        return None


def _minutes_since(timestamp: datetime) -> float:
    if timestamp.tzinfo is None:
        timestamp = timestamp.replace(tzinfo=timezone.utc)
    return round((datetime.now(timezone.utc) - timestamp).total_seconds() / 60, 1)


async def _read(reading: Awaitable[T], label: str) -> T | None:
    """One failed sensor read should not hide the rest of the status."""
    try:
        return await reading
    except Exception:
        logger.exception("Could not read %s for the chatbot", label)
        return None


async def _read_vessel_state(redis_client: RedisClient) -> str | None:
    states = await redis_client.read_set(RedisSetNames.VESSEL_STATE)
    return VesselStateModel(**states[0]).vessel_state.value if states else None


async def _read_bilge(redis_client: RedisClient) -> dict[str, Any] | None:
    readings = await redis_client.read_set(RedisSetNames.BILGE_DEPTH)
    if not readings:
        return None
    reading = BilgeDepth(**readings[0])
    age = _minutes_since(reading.timestamp)
    return {
        "sensor_distance_m": reading.bilge_depth,
        "age_minutes": age,
        "stale": age > get_settings().bilge_depth.max_data_age_minutes,
    }


def _route_progress(progress: PassagePlanProgress | None) -> dict[str, Any] | None:
    """DTW and XTE along the active plan, as stored by the worker for the GPS card."""
    if progress is None or progress.next_waypoint_index is None:
        return None

    route: dict[str, Any] = {
        "next_waypoint": progress.next_waypoint_name,
        "next_waypoint_number": progress.next_waypoint_index + 1,
        "dtw_nm": progress.distance_to_waypoint,
        "xte_nm": None,
    }
    if progress.cross_track_error is None:
        route["xte_note"] = "Not yet on a leg — heading to the first waypoint."
    elif progress.cross_track_error == 0:
        route["xte_nm"] = 0.0
        route["xte_note"] = "On track."
    else:
        xte = progress.cross_track_error
        route["xte_nm"] = abs(xte)
        route["off_track_to"] = "starboard" if xte > 0 else "port"
        route["steer_to_regain_track"] = "port" if xte > 0 else "starboard"
    return route


@vessel_toolset.tool
async def get_vessel_status(ctx: RunContext[ChatDeps]) -> dict[str, Any] | str:
    """Live boat data, as shown on the GPS card. Call it again for every question.

    Returns position, speed and course over ground, compass heading, drift,
    today's log, progress along the active route (next waypoint, distance to
    waypoint (DTW) and cross track error (XTE)), whether the boat is underway,
    and the bilge sensor reading. A null value means there is no recent
    reading for it; route is null when no passage plan is active or route
    progress has not been updated recently.
    """
    vessel = ctx.deps.vessel
    if vessel is None:
        return "Live vessel data unavailable — sensors not configured."

    await ctx.deps.notify("Reading the boat's instruments")
    gps = await _read(vessel.gps_interface.read_gps_latest(active=True), "GPS")
    velocity = await _read(
        vessel.velocity_calculator.read_velocity_latest(active=True), "velocity"
    )
    headings = await _read(
        vessel.compass_interface.read_heading_history_length(length=1, active=True),
        "compass",
    )
    drift = await _read(vessel.drift_calculator.read_drift_latest(active=True), "drift")
    journey = await _read(vessel.log_tracker.get_journey_set(), "journey")
    vessel_state = await _read(
        _read_vessel_state(ctx.deps.redis_client), "vessel state"
    )
    bilge = await _read(_read_bilge(ctx.deps.redis_client), "bilge depth")
    progress = await _read(
        PassagePlanTracker(
            ctx.deps.redis_client, vessel.gps_interface
        ).read_progress_latest(),
        "route progress",
    )

    position = None
    if gps is not None:
        position = _position(gps.latitude_nmea, gps.longitude_nmea)
        if position is not None:
            position["fix_time"] = gps.timestamp.isoformat()
            position["fix_age_minutes"] = _minutes_since(gps.timestamp)

    return {
        "measured_at": datetime.now(timezone.utc).isoformat(),
        "position": position,
        "speed_over_ground_kn": velocity.speed_over_ground if velocity else None,
        "course_over_ground_deg": velocity.course_over_ground if velocity else None,
        "heading_deg": headings[0].heading if headings else None,
        "drift_kn": drift.drift_speed if drift else None,
        "drift_angle_deg": drift.drift_angle if drift else None,
        "log_today_nm": journey.distance_travelled if journey else None,
        "log_note": "Straight-line distance from today's start, not along the track.",
        "route": _route_progress(progress),
        "vessel_state": vessel_state,
        "bilge": bilge,
    }


def _eta(distance_nm: float | None, speed_kn: float | None) -> dict[str, Any] | None:
    """Arrival time at the current speed; None when stopped or unknown."""
    if distance_nm is None or not speed_kn or speed_kn < 0.1:
        return None
    hours = distance_nm / speed_kn
    arrival = datetime.now(timezone.utc) + timedelta(hours=hours)
    return {"arrival_utc": arrival.isoformat(), "minutes": round(hours * 60)}


@vessel_toolset.tool
async def get_active_passage_plan(ctx: RunContext[ChatDeps]) -> dict[str, Any] | str:
    """The passage plan currently active and shown on the map.

    Use it for the destination, the route's waypoints and legs, the distance
    left, and the ETA to the next waypoint or the destination. ETAs assume the
    current speed over ground and are null when stopped; remaining is null
    when there is no recent route progress.
    """
    await ctx.deps.notify("Reading the active passage plan")
    plan = await read_active_plan(ctx.deps.redis_client)
    if plan is None:
        return "No active passage plan."

    waypoints = []
    for index, waypoint in enumerate(plan.course_to_steer):
        leg = {}
        if index > 0:
            leg = {
                "leg_distance_nm": round(plan.distance_between_waypoints[index - 1], 2),
                "leg_bearing_deg": round(plan.bearing_between_waypoints[index - 1]),
            }
        waypoints.append(
            {
                "number": index + 1,
                "name": waypoint.name,
                "latitude": round(waypoint.latitude, 5),
                "longitude": round(waypoint.longitude, 5),
                **leg,
            }
        )

    remaining = None
    progress = await _read(
        read_stored_progress(ctx.deps.redis_client),
        "route progress",
    )
    if progress is not None and progress.next_waypoint_index is not None:
        speed = None
        if ctx.deps.vessel is not None:
            velocity = await _read(
                ctx.deps.vessel.velocity_calculator.read_velocity_latest(active=True),
                "velocity",
            )
            speed = velocity.speed_over_ground if velocity else None
        to_destination = distance_remaining(plan, progress)
        remaining = {
            "next_waypoint": progress.next_waypoint_name,
            "next_waypoint_number": progress.next_waypoint_index + 1,
            "dtw_nm": progress.distance_to_waypoint,
            "distance_to_destination_nm": to_destination,
            "speed_over_ground_kn": speed,
            "eta_next_waypoint": _eta(progress.distance_to_waypoint, speed),
            "eta_destination": _eta(to_destination, speed),
        }

    return {
        "departure": plan.departure_place_name,
        "destination": plan.desination_place_name,
        "planned_at": plan.timestamp.isoformat(),
        "total_distance_nm": round(sum(plan.distance_between_waypoints), 2),
        "waypoints": waypoints,
        "remaining": remaining,
    }


@vessel_toolset.tool
async def get_todays_journey(ctx: RunContext[ChatDeps]) -> dict[str, Any] | str:
    """Today's journey so far: when and where it started, and how far it has gone.

    distance_nm is the straight-line distance from the start to the latest
    position, not the distance sailed along the track.
    """
    vessel = ctx.deps.vessel
    if vessel is None:
        return "Journey data unavailable — sensors not configured."

    await ctx.deps.notify("Checking today's journey")
    journey = await vessel.log_tracker.get_journey_set()
    if journey is None:
        return "No journey recorded today."

    try:
        track_points = len(json.loads(journey.gps_data))
    except json.JSONDecodeError:
        track_points = None

    return {
        "started_at": journey.timestamp.isoformat(),
        "last_update": journey.end_datetime.isoformat(),
        "duration_minutes": round(
            (journey.end_datetime - journey.timestamp).total_seconds() / 60
        ),
        "distance_nm": journey.distance_travelled,
        "start_position": _position(journey.start_latitude, journey.start_longitude),
        "latest_position": _position(journey.end_latitude, journey.end_longitude),
        "track_points": track_points,
    }


@vessel_toolset.tool
async def list_previous_journeys(
    ctx: RunContext[ChatDeps],
    limit: Annotated[
        int,
        Field(description="How many journeys to return, newest first", ge=1, le=50),
    ] = 10,
    from_date: Annotated[
        date | None,
        Field(description="Only journeys that departed on or after this UTC date"),
    ] = None,
    to_date: Annotated[
        date | None,
        Field(description="Only journeys that departed on or before this UTC date"),
    ] = None,
) -> list[dict[str, Any]] | str:
    """Completed journeys from the logbook, newest first.

    distance_nm is the straight-line distance between departure and arrival,
    not the distance sailed along the track.
    """
    if ctx.deps.db_manager is None:
        return "Journey history unavailable — no database configured."

    await ctx.deps.notify("Looking up previous journeys")
    if from_date is None and to_date is None:
        records = ctx.deps.db_manager.list_trips(limit)
    else:
        records = [
            record
            for record in ctx.deps.db_manager.list_trips()
            if (from_date is None or record.departure_time.date() >= from_date)
            and (to_date is None or record.departure_time.date() <= to_date)
        ][:limit]
    if not records:
        return "No journeys found for that period."

    return [
        {
            "journey_id": record.unique_key,
            "departed_at": record.departure_time.isoformat(),
            "arrived_at": record.arrival_time.isoformat(),
            "duration_minutes": round(record.duration_seconds / 60),
            "distance_nm": round(record.distance_travelled, 2),
            "start_position": _position(
                record.departure_location.latitude,
                record.departure_location.longitude,
            ),
            "end_position": _position(
                record.arrival_location.latitude, record.arrival_location.longitude
            ),
        }
        for record in records
    ]
