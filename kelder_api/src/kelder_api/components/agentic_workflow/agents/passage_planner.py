import asyncio
import json
import logging
import textwrap
from pathlib import Path
from typing import Any

from pydantic import Field
from pydantic_ai import Agent, RunContext
from rtree import index

from src.kelder_api.components.agentic_workflow.agents.models import PassagePlan
from src.kelder_api.components.redis_client.redis_client import RedisClient
from src.kelder_api.components.velocity.utils import haversine

logger = logging.getLogger(__name__)

# TODO - Move passage plan tool timeout to config

MARKS_FILE = Path(__file__).resolve().parents[3] / "assets" / "marks.json"


def _load_marks() -> list[dict[str, Any]]:
    """Load seamark metadata from disk."""
    try:
        with MARKS_FILE.open() as marks_file:
            data = json.load(marks_file)
            if isinstance(data, list):
                return data
            logger.warning("Marks data at %s is not a list", MARKS_FILE)
    except FileNotFoundError:
        logger.warning("Marks file %s was not found", MARKS_FILE)
    except json.JSONDecodeError:
        logger.exception("Marks file %s contains invalid JSON", MARKS_FILE)
    return []


def _build_marks_index(marks: list[dict[str, Any]]):
    """Create an R-tree index for quick nearest lookups."""
    if not marks:
        return None

    idx = index.Index()
    inserted = 0

    for idx_counter, mark in enumerate(marks):
        coordinates = mark.get("coordinates")
        if not isinstance(coordinates, (list, tuple)) or len(coordinates) != 2:
            continue

        try:
            longitude = float(coordinates[0])
            latitude = float(coordinates[1])
        except (TypeError, ValueError):
            continue

        bounds = (longitude, latitude, longitude, latitude)
        idx.insert(idx_counter, bounds, obj=mark)
        inserted += 1

    if inserted == 0:
        return None
    return idx


MARKS_DATA = _load_marks()
MARKS_INDEX = _build_marks_index(MARKS_DATA)


async def save_passage_plan(
    passage_plan: PassagePlan, redis_client: "RedisClient"
) -> bool:
    """
    Save a full passage plan with all navigational details.
    """

    try:
        async with asyncio.timeout(2):
            await redis_client.write_set("PASSAGE_PLAN", passage_plan)
            logger.debug("Passage plan created and saved")
        return True

    except TimeoutError:
        logger.error("The passage plan failed to save within the timeperiod")
    except Exception:
        logger.error("Passage plan failed to save")
        raise


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
    return await save_passage_plan(passage_plan, ctx.deps)


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


def _neighbour_search(latitude: float, longitude: float, neighbours: int):
    """Return the requested number of closest marks to a coordinate pair."""
    if neighbours < 1 or not MARKS_DATA:
        return []

    limit = min(neighbours, len(MARKS_DATA))

    if MARKS_INDEX is not None:
        bbox = (longitude, latitude, longitude, latitude)
        return [
            result.object for result in MARKS_INDEX.nearest(bbox, limit, objects=True)
        ]

    def _distance(mark: dict[str, Any]) -> float:
        coordinates = mark.get("coordinates", [None, None])
        try:
            lon, lat = coordinates
        except (TypeError, ValueError):
            return float("inf")
        try:
            lon = float(lon)
            lat = float(lat)
        except (TypeError, ValueError):
            return float("inf")
        return haversine(
            latitude_start=latitude,
            latitude_end=lat,
            longitude_start=longitude,
            longitude_end=lon,
        )

    sorted_marks = sorted(MARKS_DATA, key=_distance)
    return sorted_marks[:limit]


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
    neighbours = 10
    print(f"Looking for {neighbours} marks near {latitude},{longitude}")
    if not MARKS_DATA:
        raise RuntimeError(
            f"No marks data available;"
            f"ensure {MARKS_FILE} exists and contains valid seamarks."
        )

    results = _neighbour_search(
        latitude=latitude, longitude=longitude, neighbours=neighbours
    )

    if not results:
        raise RuntimeError("No marks could be found for the supplied query")

    print(f"Identified marks \n{results}")
    return results
