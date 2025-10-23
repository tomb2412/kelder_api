import textwrap

from pydantic_ai import Agent, RunContext

from src.kelder_api.components.passage_plan.passage_plan_agent import (
    get_passage_planner,
)
from src.kelder_api.components.agentic_workflow.agents.tidal_agent import tidal_agent
from src.kelder_api.components.redis_client.redis_client import RedisClient


def get_chatbot_agent() -> Agent:
    prompt = textwrap.dedent(
        """
        You are a sailing assistant chatbot. Keep every reply short, clear, and
        practical - ideally no more than 200 characters.

        Rules:
        - Safety comes first: warn about hazards, weather, and poor conditions.
        - Be brief and conversational; this is real-time assistance.
        - Use tools for detailed data:
          * Passage Planner → passage plans.
          * Tidal Agent → tidal heights, times, and streams.
        - When a tool runs, summarise the output with key safety notes.
        - If unsure, recommend official charts, notices to mariners, or tidal
          almanacs.
        - Never invent coordinates, tidal times, or other safety-critical data.

        Examples:
        - "Plan a route to Plymouth" → run Passage Planner, then confirm the plan
          and highlight hazards.
        - "What’s the tide at Cowes?" → run Tidal Agent, then give the result.
        - "Is it safe to sail now?" → use relevant tools, report risks first.

        Always stay polite, concise, and safety-minded.
        """
    ).strip()

    chatbot_agent = Agent(
        model="gpt-5-mini",
        system_prompt=prompt,
        deps_type=RedisClient,
    )

    @chatbot_agent.tool
    async def get_tidal_information(ctx: RunContext[RedisClient], location: str) -> str:
        return await tidal_agent.run(location, usage=ctx.usage)

    @chatbot_agent.tool
    async def get_passage_plan(
        ctx: RunContext[RedisClient], passage_plan_prompt: str
    ) -> str:
        passage_planner_agent = get_passage_planner()
        return await passage_planner_agent.run(
            passage_plan_prompt, deps=ctx.deps, usage=ctx.usage
        )

    return chatbot_agent
