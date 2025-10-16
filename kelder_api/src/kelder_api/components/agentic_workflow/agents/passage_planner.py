import logging
import textwrap

from pydantic_ai import Agent, RunContext

from src.kelder_api.components.agentic_workflow.agents.models import PassagePlan
from src.kelder_api.components.passage_plan.tools import save_passage_plan
from src.kelder_api.components.redis_client.redis_client import RedisClient

logger = logging.getLogger(__name__)

async def save_passage_plan(
    passage_plan: PassagePlan, redis_client: "RedisClient"
) -> bool:
    """
    Save a full passage plan with all navigational details.
    """
    try:
        await redis_client.write_set("PASSAGE_PLAN", passage_plan)
        logger.debug("Passage plan created and saved")

        return True

    except Exception:
        return False


system_prompt = textwrap.dedent(
    """
    You are a navigation assistant trained in yacht passage planning.

    When asked to produce a passage plan:
    1. Create a full plan that meets these standards:
        - Title: departure to destination (e.g. 'Cowes to Plymouth').
        - Course to steer: list continuous waypoints for the route.
            * Identify start and end waypoints for each leg.
            * Select real waypoints; never hallucinate coordinates.
            * Ensure each leg is navigable with direct lines of sight.
            * Validate every coordinate to avoid mistakes.
        - Include departure time and ETA.

    2. Guarantee all coordinates are accurate and expressed in degrees and
        decimal minutes (longitude DDDMM.MMM, latitude DDMM.MMM).

    3. Before responding, persist the structured plan by calling the
        `save_passage_plan` tool.

    4. After saving, reply only with a confirmation and general plan overview such as
        "✅ Your passage plan from <DEPARTURE> to <DESTINATION> has been prepared and saved
        for tomorrow leaving at 9:30 am."
    """
).strip()

passage_plan_agent = Agent(
    "gpt-5-mini",
    system_prompt=system_prompt,
    output_type=PassagePlan,
)

@passage_plan_agent.tool
async def save_passage_plan_tool(
    ctx: RunContext[RedisClient], passage_plan: PassagePlan
) -> bool:
    return await save_passage_plan(passage_plan, ctx.deps)
