import textwrap
from dataclasses import dataclass
from datetime import datetime, timezone

from pydantic_ai import Agent


# TODO: class to initialise all the agents and then expopse runtime inference methods
# TODO: I need to remove orchestration properties from this prompt -
# ONLY return the ResponseEvaluatorNode
@dataclass
class ChatResponse:
    message: str


@dataclass
class ReasoningInput:
    message: str


@dataclass
class TidalSearch:
    location: str
    justification: str


prompt = textwrap.dedent(
    """
    You are a sailing assistant chatbot. Keep every reply short, clear, and
    practical - ideally no more than 200 characters.

    Rules:
    - Be brief and conversational; this is real-time assistance.
    - Never invent coordinates, tidal times, or other safety-critical data.
    - If you need any external data - return the reasoning agent which will manage all
     tool calling.

    Examples:
    - "Plan a route to Plymouth" → run Passage Planner, then confirm the plan
        and highlight hazards.
    - "What’s the tide at Cowes?" → run Tidal Agent, then give the result.
    - "Is it safe to sail now?" → use relevant tools, report risks first.

    Boat data:
    - Draft: 1.2m

    Always stay concise, and respond as susinctly as possible, but keep a conversational
     friendilness.
    Include metadata made about location, or time (including UT or DST) if you quote
     information in the response.
    """
).strip()

chatbot_agent = Agent(
    model="openai:gpt-4o-mini",
    output_type=ChatResponse | ReasoningInput,  # | TidalSearch | BuildPassageRoute,
    system_prompt=prompt,
)


@chatbot_agent.system_prompt
def chatbot_datetime_prompt() -> str:
    return f"Current UTC datetime: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M')} UTC."
