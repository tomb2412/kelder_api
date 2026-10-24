import textwrap
from datetime import datetime, timezone
from typing import Annotated

from pydantic import Field
from pydantic_ai import Agent, RunContext
from pydantic_ai.exceptions import ModelHTTPError, UsageLimitExceeded

from src.kelder_api.components.agentic_workflow.agents.models import PassagePlan
from src.kelder_api.components.agentic_workflow.agents.passage_planner import (
    passage_plan_agent,
)
from src.kelder_api.components.agentic_workflow.agents.tidal_agent import tidal_agent
from src.kelder_api.components.agentic_workflow.models import ChatDeps
from src.kelder_api.configuration.logging_controller import get_logger
from src.kelder_api.configuration.settings import get_settings

logger = get_logger(__name__, "agent_workflow.chatbot")

prompt = textwrap.dedent(
    """
    You are a sailing assistant chatbot. Keep every reply short, clear, and
    practical - ideally no more than 200 characters.

    Rules:
    - Be brief and conversational; this is real-time assistance.
    - Never invent coordinates, tidal times, or other safety-critical data. Use
      your tools to get them, and say so if a tool could not provide them.
    - Use get_tidal_information for tide heights, high/low water times and streams.
    - Use create_passage_plan to plan or change a route. When tides matter for
      the passage, get the tidal information first and pass it on as
      considerations.
    - If you need a departure or destination to plan a passage, ask for it.
      Assume tomorrow if no date is given.

    Examples:
    - "Plan a route to Plymouth" → create a passage plan, then confirm the plan
        and highlight hazards.
    - "What's the tide at Cowes?" → get tidal information, then give the result.
    - "Is it safe to sail now?" → use relevant tools, report risks first.

    Boat data:
    - Draft: 1.2m

    Include metadata about location, or time (including UT or DST) if you quote
     information in the response.
    """
).strip()

chatbot_agent = Agent(
    model=get_settings().inference.chat_model,
    deps_type=ChatDeps,
    output_type=str,
    instructions=prompt,
    defer_model_check=True,
)


@chatbot_agent.instructions
def chatbot_datetime_prompt() -> str:
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M")
    return f"Current UTC datetime: {now} UTC."


@chatbot_agent.tool
async def get_tidal_information(
    ctx: RunContext[ChatDeps],
    request: Annotated[
        str,
        Field(
            description=(
                "What to find out, including the location and the date or time of "
                "interest, e.g. 'High water times at Cowes tomorrow'"
            )
        ),
    ],
) -> str:
    """Ask the tidal specialist about tide heights, high/low water and streams."""
    await ctx.deps.notify("Searching tidal information")
    try:
        result = await tidal_agent.run(request, usage=ctx.usage)
    except (ModelHTTPError, UsageLimitExceeded):
        raise
    except Exception:
        logger.exception("Tidal agent failed")
        return "Tidal data unavailable — could not retrieve tidal information."
    return result.output


@chatbot_agent.tool
async def create_passage_plan(
    ctx: RunContext[ChatDeps],
    departure: Annotated[
        str, Field(description="Where the passage starts, e.g. 'Cowes'")
    ],
    destination: Annotated[
        str, Field(description="Where the passage ends, e.g. 'Hamble'")
    ],
    departure_time: Annotated[
        str | None, Field(description="When to leave, in UTC, if known")
    ] = None,
    considerations: Annotated[
        str | None,
        Field(
            description=(
                "Anything the planner must account for, such as tidal information "
                "already retrieved or marks to avoid"
            ),
        ),
    ] = None,
) -> PassagePlan | str:
    """Build a passage plan between two places and save it for the user to view."""
    await ctx.deps.notify("Generating a passage plan")
    task = f"Plan a passage from {departure} to {destination}."
    if departure_time:
        task += f"\nDeparture time: {departure_time}"
    if considerations:
        task += f"\nConsiderations: {considerations}"

    try:
        result = await passage_plan_agent.run(
            task, deps=ctx.deps.passage_planner_deps(), usage=ctx.usage
        )
    except (ModelHTTPError, UsageLimitExceeded):
        raise
    except Exception:
        logger.exception("Passage plan agent failed")
        return "Passage planning failed — could not generate a route."
    return result.output
