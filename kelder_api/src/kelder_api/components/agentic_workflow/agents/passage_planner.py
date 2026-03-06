import logging
import textwrap
from datetime import datetime, timezone
from typing import Any

from pydantic import Field
from pydantic_ai import Agent, RunContext

from src.kelder_api.components.agentic_workflow.agents.models import PassagePlan
from src.kelder_api.components.agentic_workflow.agents.tools import save_passage_plan
from src.kelder_api.components.velocity.utils import (
    haversine,
)

logger = logging.getLogger(__name__)

# TODO - Move passage plan tool timeout to config


system_prompt = textwrap.dedent(
    """
    You are a navigation assistant trained in yacht passage planning.

    When asked to produce a passage plan, your role will be to identify waypoints
     and generate a route.

    1. Create a plan that includes this information:
        - Title: departure to destination (e.g. 'Cowes to Plymouth').
        - Course to steer: list continuous waypoints for the route.
            * If exact mark names are provided, use find_route_between_marks to get
             the optimised safe route from the graph database — prefer this tool.
            * Otherwise use find_nearest_marks to find pilotage marks in the area.
            * Only use marks from the dataset.
            * Ensure each leg is navigable with direct lines of sight.
        - Include departure time and ETA.

    2. Before responding, persist the structured plan by calling the
        `save_passage_plan` tool.

    3. After saving, return the passage plan you have saved.

    *How to select a waypoint*
    - At the begining of the journey search for marks near the start position.
     Use a marina or named bouy or beacon if possible.
    - After identifying a start mark, search again for a similar mark near the
     destination, then build intermediate waypoints linking them via safe pilotage
     marks along the route.
"""
).strip()

passage_plan_agent = Agent(
    "openai:gpt-4o-mini",
    system_prompt=system_prompt,
    output_type=PassagePlan,
)


@passage_plan_agent.system_prompt
def passage_planner_datetime_prompt() -> str:
    return f"Current UTC datetime: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M')} UTC."


@passage_plan_agent.tool
async def save_passage_plan_tool(
    ctx: RunContext[dict[str, Any]], passage_plan: PassagePlan
) -> bool:
    """Persist the passage plan to display to the user"""
    return await save_passage_plan(passage_plan, ctx.deps["redis_client"])


@passage_plan_agent.tool
def calculate_distance_between_waypoints(
    ctx: RunContext,
    start_latitude: float = Field(
        description="The start waypoint latitude in decimal degrees"
    ),
    start_longitude: float = Field(
        description="The start waypoint longitude in decimal degrees"
    ),
    end_latitude: float = Field(
        description="The end waypoint latitude in decimal degrees"
    ),
    end_longitude: float = Field(
        description="The end waypoint longitude in decimal degrees"
    ),
):
    """
    Calculate the distance in nautical miles between waypoints.
    All arguments in decimal degrees.
    """
    return haversine(
        latitude_start=start_latitude,
        latitude_end=end_latitude,
        longitude_start=start_longitude,
        longitude_end=end_longitude,
    )


def _neighbour_search(
    latitude: float,
    longitude: float,
    neighbours: int,
    marks_data: list[dict[str, Any]],
    marks_index: list[dict[str, Any]],
):
    """Return the requested number of closest marks to a coordinate pair."""
    limit = min(neighbours, len(marks_data))

    bbox = (longitude, latitude, longitude, latitude)

    return [result.object for result in marks_index.nearest(bbox, limit, objects=True)]


@passage_plan_agent.tool
def find_nearest_marks(
    ctx: RunContext,
    latitude: float = Field(
        description="Latitude of the current position in decimal degrees"
    ),
    longitude: float = Field(
        description="Longitude of the current position in decimal degrees"
    ),
):
    """Lookup nearby marks such as harbours, buoys, and cardinal markers."""
    MARKS_DATA = ctx.deps.get("marks_data")
    MARKS_INDEX = ctx.deps.get("marks_index")

    if not MARKS_DATA or not MARKS_INDEX:
        return "Spatial mark index unavailable — use find_route_between_marks instead."

    # TODO: Import this as an agent setting
    neighbours = 20
    logger.debug("Looking for %s marks near %s, %s", neighbours, latitude, longitude)

    results = _neighbour_search(
        latitude=latitude,
        longitude=longitude,
        neighbours=neighbours,
        marks_data=MARKS_DATA,
        marks_index=MARKS_INDEX,
    )

    if len(results) == 0:
        logger.warning("No marks found near %s, %s", latitude, longitude)
        return "No marks found near this position — try a nearby coordinate."

    logger.debug("Identified marks near %s, %s: %s", latitude, longitude, results)
    return results


@passage_plan_agent.tool
def find_route_between_marks(
    ctx: RunContext,
    name_from: str = Field(description="Exact name of the departure mark"),
    name_to: str = Field(description="Exact name of the destination mark"),
):
    """Find the optimal safe route between two named marks using A* graph pathfinding.

    Returns an ordered list of waypoints (name, latitude, longitude) from departure
    to destination. Use these as the course_to_steer in the passage plan.
    """
    neo4j_client = ctx.deps.get("neo4j_client")
    if neo4j_client is None:
        logger.warning("neo4j_client not available in deps")
        return "Graph routing unavailable — neo4j client not configured."

    logger.debug("Finding route from %s to %s", name_from, name_to)
    rows = neo4j_client.a_star_by_name(name_from=name_from, name_to=name_to)

    if not rows:
        return f"No route found between '{name_from}' and '{name_to}'."

    route_row = rows[0]
    path_nodes = route_row.get("path", [])

    waypoints = [
        {
            "name": node["name"],
            "latitude": node["latitude"],
            "longitude": node["longitude"],
        }
        for node in path_nodes
        if "latitude" in node and "longitude" in node
    ]

    logger.debug(
        "Route found: %s waypoints, total cost %.3f km",
        len(waypoints),
        route_row.get("totalCost", 0),
    )
    return waypoints
