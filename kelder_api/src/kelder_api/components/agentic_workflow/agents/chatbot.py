import textwrap
from dataclasses import dataclass

from pydantic_ai import Agent


# TODO: class to initialise all the agents and then expopse runtime inference methods
# TODO: I need to remove orchestration properties from this prompt -
# ONLY return the ResponseEvaluatorNode
@dataclass
class ChatResponse:
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

    Examples:
    - "Plan a route to Plymouth" → run Passage Planner, then confirm the plan
        and highlight hazards.
    - "What’s the tide at Cowes?" → run Tidal Agent, then give the result.
    - "Is it safe to sail now?" → use relevant tools, report risks first.

    Always stay concise, and respond as susinctly as possible.
    Always include any assumptions made about location, or time (including UT or DST). 

    """
).strip()

chatbot_agent = Agent(
    model="gpt-5-mini",
    output_type=ChatResponse,  # | TidalSearch | BuildPassageRoute,
    system_prompt=prompt,
)
