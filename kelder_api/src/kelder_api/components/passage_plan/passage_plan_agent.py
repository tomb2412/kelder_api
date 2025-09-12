from pydantic_ai import Agent, RunContext

from src.kelder_api.components.redis_client.redis_client import RedisClient
from src.kelder_api.components.passage_plan.tools import save_passage_plan
from src.kelder_api.components.passage_plan.models import PassagePlan

def get_passage_planner() -> Agent:
    passage_plan_agent = Agent(
        "gpt-5-mini",
        system_prompt="""You are a navigation assistant trained in yatch passage planning.  
When asked to produce a passage plan:  

1. Create a full passage plan in line with following standards.  
   - Title: departure to desination. e.g "Cowes to Plymouth"
   - Tides: Use the tidal tool to identify daytime high and low water, local time.
   - Weather: Use the tool to fetch weather data.
   - Course to steer: select relevant waypoints, never hallucinate coordinates. 
   - Pilotage (departure & arrival)  
   - Ports of refuge 
   - Navigational hazards (shoals, overfalls, traffic, restricted zones)  
   - Departure time & ETA  

2. Ensure all **coordinates are accurate and real**.  

3. Do output the plan directly, but ensure it is also recorded.  
   Instead, call the `save_passage_plan` tool with the full plan in structured form.  

4. After saving, respond to the user with only a confirmation such as:  
   **"✅ Your passage plan has been prepared and saved."** 
""",
   deps_type=RedisClient,
   output_type=PassagePlan
   )
    
    @passage_plan_agent.tool
    async def save_passage_plan_tool(ctx: RunContext[RedisClient], passage_plan: PassagePlan) -> bool:
        return await save_passage_plan(passage_plan, ctx.deps)

    return passage_plan_agent