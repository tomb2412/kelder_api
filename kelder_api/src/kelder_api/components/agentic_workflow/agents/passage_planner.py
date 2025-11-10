import asyncio
import logging
import textwrap

import httpx
from pydantic import Field
from pydantic_ai import Agent, RunContext

from src.kelder_api.components.agentic_workflow.agents.models import PassagePlan
from src.kelder_api.components.redis_client.redis_client import RedisClient
from src.kelder_api.components.velocity.utils import haversine

logger = logging.getLogger(__name__)

# TODO - Move passage plan tool timeout to config


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

    When asked to produce a passage plan:
    1. Create a full plan that includes this information:
        - Title: departure to destination (e.g. 'Cowes to Plymouth').
        - Course to steer: list continuous waypoints for the route.
            * Identify start and end waypoints for each leg.
            * Select real waypoints; never hallucinate coordinates.
            * Ensure each leg is navigable with direct lines of sight.
            * Validate every coordinate to avoid mistakes.
        - Include departure time and ETA.

    2. Guarantee all coordinates are accurate and expressed in decimal degrees 
    (longitude DD.DDD latitude DDD.DDD).

    3. Before responding, persist the structured plan by calling the
        `save_passage_plan` tool.

    4. After saving, reply only with a confirmation and general plan overview such as
        "✅ Your passage plan from <DEPARTURE> to <DESTINATION> has been prepared and
          saved for tomorrow leaving at 9:30 am."
    """
).strip()

passage_plan_agent = Agent(
    "gpt-5",
    system_prompt=system_prompt,
    output_type=PassagePlan,

)

@passage_plan_agent.tool
async def save_passage_plan_tool(
    ctx: RunContext[RedisClient], passage_plan: PassagePlan
) -> bool:
    """Persist the passage plan to display to the user"""
    return await save_passage_plan(passage_plan, ctx.deps)

# @passage_plan_agent.tool
# async def check_coordinates_are_water(ctx: RunContext, latitude: str, longitude: str) -> bool | None:
#     """
#     Verify a latitude and longitude are in the water. longitude DD.DDD latitude DDD.DDD 
    
#     Returns:
#         bool - for successful response. True implies waypoint is on water, and false is on land.
#         None - tool is not active at the moment.
#     """
    
#     url = "https://isitwater-com.p.rapidapi.com/"
#     params = {
#         "latitude": latitude,
#         "longitude": longitude,
#     }
#     headers = {
#         "x-rapidapi-host": "isitwater-com.p.rapidapi.com",
#         "x-rapidapi-key": "1edb25266fmsh051f910ec50d484p1861dcjsndb0a5e076386",
#     }

#     try:
#         response = httpx.get(url, headers=headers, params=params, timeout=5)
#         response.raise_for_status()
#         data = response.json()
#     except Exception as exc:
#         logger.exception("Failed to call isitwater API")
#         return None

#     # Defensive logging
#     logger.info(f"is water response: {data}")

#     # Check key existence safely
#     if "water" not in data:
#         logger.warning(f"Unexpected API response: {data}")
#         return None

#     return data["water"]


@passage_plan_agent.tool
def calculate_distance_between_waypoints(
    ctx: RunContext,
    start_latitude: str = Field(description="The start waypoint latitude in decimal degrees"),
    start_longitude: str = Field(description="The start waypoint longitude in decimal degrees"),
    end_latitude: str = Field(description="The end waypoint latitude in decimal degrees"),
    end_longitude: str = Field(description="The end waypoint longitude in decimal degrees")
    ):
    """Calculate the distance in nautical miles between waypoints. All arguments in decimal degrees"""
    return haversine(
        latitude_start=start_latitude,
        latitude_end=end_latitude,
        longitude_start=start_longitude,
        longitude_end=end_longitude,
    )