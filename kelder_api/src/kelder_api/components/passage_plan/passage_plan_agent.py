from pydantic_ai import Agent, RunContext

from src.kelder_api.components.passage_plan.models import PassagePlan
from src.kelder_api.components.passage_plan.tools import save_passage_plan
from src.kelder_api.components.redis_client.redis_client import RedisClient


def get_passage_planner() -> Agent:
    passage_plan_agent = Agent(
        "gpt-5-mini",
        system_prompt="""You are a navigation assistant trained in yatch passage planning.  
When asked to produce a passage plan:  

1. Create a full passage plan in line with following standards.  
   - Title: departure to desination. e.g "Cowes to Plymouth"
   - Course to steer - a series of continuous journey Waypoints for the route:
        - For each leg identify start and end Waypoints
        - Select relevant Waypoints, never hallucinate coordinates. 
        - Ensure the journey between each waypoint is navigatable safely by boat.
        - Ensure the waypoints are appropriately spaced with a direct line of sight between them.
        - After selecting waypoints, validate each coordinate to avoid hallucinations and mistakes. 
   - Departure time & ETA  

2. Ensure all **coordinates are accurate and real**.
   Ensure all coordinates are in degrees and decimal minutes. Longitude DDDMM.MMM and latitude DDMM.MMM

3. Do output the plan directly, but ensure it is recorded.  
   To save the plan call the `save_passage_plan` tool with the full plan in structured form.  

4. After saving, respond to the user with only a confirmation such as:  
   **"✅ Your passage plan has been prepared and saved."** 
""",
        deps_type=RedisClient,
        output_type=PassagePlan,
    )

    @passage_plan_agent.tool
    async def save_passage_plan_tool(
        ctx: RunContext[RedisClient], passage_plan: PassagePlan
    ) -> bool:
        return await save_passage_plan(passage_plan, ctx.deps)

    return passage_plan_agent
