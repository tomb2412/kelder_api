from http import HTTPStatus

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel

from src.kelder_api.app.getters import (
    get_db_manager,
    get_neo4j_client,
    get_redis_client,
)
from src.kelder_api.components.agentic_workflow.agents.models import (
    PassagePlan,
    Waypoint,
    number_waypoints,
)
from src.kelder_api.components.agentic_workflow.agents.passage_planner import (
    passage_plan_agent,
)
from src.kelder_api.components.agentic_workflow.agents.tools import save_passage_plan
from src.kelder_api.components.db_manager.service import DBManager
from src.kelder_api.components.neo4j_client import Neo4jClient
from src.kelder_api.components.redis_client.redis_client import RedisClient
from src.kelder_api.components.redis_client.types import RedisSetNames
from src.kelder_api.configuration.logging_controller import get_logger

logger = get_logger(__name__, "routes.passage_plan")

router = APIRouter(tags=["Agentic"])


def get_redis_dep(request: Request) -> RedisClient:
    return get_redis_client(request.app)


def get_neo4j_dep(request: Request) -> Neo4jClient:
    return get_neo4j_client(request.app)


def get_db_dep(request: Request) -> DBManager:
    return get_db_manager(request.app)


class PassagePlanRequest(BaseModel):
    from_mark: str
    to_mark: str


class PlottedRouteRequest(BaseModel):
    course_to_steer: list[Waypoint]


def _signed_waypoint(waypoint: Waypoint, position: int) -> Waypoint:
    """Normalise a waypoint to signed decimal degrees.

    The map sends absolute values with hemisphere letters, but distance, bearing
    and progress tracking all work on signed decimal degrees.
    """
    latitude_hemisphere = waypoint.latitude_hemisphere.strip().upper()
    longitude_hemisphere = waypoint.longitude_hemisphere.strip().upper()
    if latitude_hemisphere not in ("N", "S") or longitude_hemisphere not in ("E", "W"):
        raise HTTPException(
            status_code=HTTPStatus.BAD_REQUEST,
            detail=f"Waypoint {position} has an invalid hemisphere.",
        )
    if abs(waypoint.latitude) > 90 or abs(waypoint.longitude) > 180:
        raise HTTPException(
            status_code=HTTPStatus.BAD_REQUEST,
            detail=f"Waypoint {position} is outside valid latitude/longitude range.",
        )

    latitude = abs(waypoint.latitude)
    longitude = abs(waypoint.longitude)
    return Waypoint(
        name=waypoint.name or None,
        latitude=-latitude if latitude_hemisphere == "S" else latitude,
        latitude_hemisphere=latitude_hemisphere,
        longitude=-longitude if longitude_hemisphere == "W" else longitude,
        longitude_hemisphere=longitude_hemisphere,
    )


@router.get("/passage_plan")
async def GetPassagePlan(redis_client: RedisClient = Depends(get_redis_dep)):
    logger.info("Requesting a passage plan")
    try:
        plan = (await redis_client.read_set(RedisSetNames.PASSAGE_PLAN))[0]
    except IndexError:
        plan = ""

    return {"passage_plan": plan}


@router.post("/passage_plan/waypoints")
async def PostPlottedRoute(
    body: PlottedRouteRequest,
    redis_client: RedisClient = Depends(get_redis_dep),
    db_manager: DBManager = Depends(get_db_dep),
):
    """Replace the active passage plan with a route plotted on the map."""
    if len(body.course_to_steer) < 2:
        raise HTTPException(
            status_code=HTTPStatus.BAD_REQUEST,
            detail="A route needs at least two waypoints.",
        )

    waypoints = number_waypoints(
        [
            _signed_waypoint(waypoint, position)
            for position, waypoint in enumerate(body.course_to_steer, start=1)
        ]
    )
    plan = PassagePlan(
        departure_place_name=waypoints[0].name,
        desination_place_name=waypoints[-1].name,
        course_to_steer=waypoints,
    )
    logger.info(
        "Saving plotted route %s to %s with %s waypoints",
        plan.departure_place_name,
        plan.desination_place_name,
        len(waypoints),
    )

    try:
        record = db_manager.save_passage_plan(plan)
    except Exception:
        logger.exception("Failed to store plotted route")
        raise HTTPException(
            status_code=HTTPStatus.INTERNAL_SERVER_ERROR,
            detail="Could not save the route to the database.",
        )

    try:
        activated = await save_passage_plan(plan, redis_client)
    except Exception:
        logger.exception("Failed to activate plotted route")
        activated = False
    if not activated:
        raise HTTPException(
            status_code=HTTPStatus.SERVICE_UNAVAILABLE,
            detail="Route saved, but could not be made the active plan.",
        )

    return {"passage_plan": plan, "plan_id": record.unique_key}


@router.post("/passage_plan")
async def PostPassagePlan(
    body: PassagePlanRequest,
    redis_client: RedisClient = Depends(get_redis_dep),
    neo4j_client: Neo4jClient = Depends(get_neo4j_dep),
):
    """Generate a passage plan between two named marks using graph-based A* routing."""
    logger.info(
        "Generating passage plan from '%s' to '%s'", body.from_mark, body.to_mark
    )

    prompt = (
        f"Plan a passage from '{body.from_mark}' to '{body.to_mark}'. "
        f"Use the find_route_between_marks tool with name_from='{body.from_mark}' "
        f"and name_to='{body.to_mark}' to get the waypoints."
    )

    result = await passage_plan_agent.run(
        prompt,
        deps={
            "redis_client": redis_client,
            "neo4j_client": neo4j_client,
        },
    )

    return result.output
