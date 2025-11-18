import logging
import textwrap
from typing import Any

from pydantic import Field
from pydantic_ai import Agent, RunContext

from src.kelder_api.components.agentic_workflow.agents.models import PassagePlan
from src.kelder_api.components.agentic_workflow.agents.tools import save_passage_plan
from src.kelder_api.components.redis_client.redis_client import RedisClient
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
            * Use the tool: find_nearest_marks to find pilotage marks in the area.
            * Select appropriate marks or marinas as the start and end waypoints
             for each leg.
            * Only use marks from the dataset.
            * Ensure each leg is navigable with direct lines of sight.
            * If no marks are returned try again with a different coordinate input.
        - Include departure time and ETA.

    2. Before responding, persist the structured plan by calling the
        `save_passage_plan` tool.

    3. After saving, return the passage plan you have saved.

    *How to select a waypoint*
    - At the begining of the journey search for marks near the start position.
     Use a marina or named bouy or beacon if possible.
    - After identifying a start mark. Search again for a similar
"""
).strip()

passage_plan_agent = Agent(
    "gpt-5-nano",
    system_prompt=system_prompt,
    output_type=PassagePlan,
)


@passage_plan_agent.tool
async def save_passage_plan_tool(
    ctx: RunContext[RedisClient], passage_plan: PassagePlan
) -> bool:
    """Persist the passage plan to display to the user"""
    return await save_passage_plan(passage_plan, ctx.deps["redis_client"])


@passage_plan_agent.tool
def calculate_distance_between_waypoints(
    ctx: RunContext,
    start_latitude: int = Field(
        description="The start waypoint latitude in decimal degrees"
    ),
    start_longitude: int = Field(
        description="The start waypoint longitude in decimal degrees"
    ),
    end_latitude: int = Field(
        description="The end waypoint latitude in decimal degrees"
    ),
    end_longitude: int = Field(
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
    MARKS_DATA = ctx.deps["marks_data"]
    MARKS_INDEX = ctx.deps["marks_index"]

    # TODO: Import this as an agent setting
    neighbours = 20
    print(f"Looking for {neighbours} marks near {latitude},{longitude}")

    results = _neighbour_search(
        latitude=latitude,
        longitude=longitude,
        neighbours=neighbours,
        marks_data=MARKS_DATA,
        marks_index=MARKS_INDEX,
    )

    if len(results) == 0:
        raise RuntimeError("No marks could be found for the supplied query")

    print(f"Identified marks \n{results}")
    return results
