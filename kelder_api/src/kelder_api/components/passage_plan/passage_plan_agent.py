from agents import Agent, FunctionTool

from functools import partial

from src.kelder_api.components.redis_client.redis_client import RedisClient
from src.kelder_api.components.passage_plan.tools import save_passage_plan
from src.kelder_api.components.passage_plan.models import PassagePlan

def get_passage_planner(redis_client: RedisClient) -> Agent:
    save_passage_plan_tool = FunctionTool(
         name="Save_the_passage_plan",
         description="Use this tool when the passage plan is complete and ready to display to the user",
         params_pydantic_model=PassagePlan,
         on_invoke_tool=partial(save_passage_plan, redis_client=redis_client),
      )

    passage_plan_agent = Agent(
        name = "Passage Planner",
        instructions="""You are a navigation assistant trained in RYA Day Skipper passage planning.  
When asked to produce a passage plan:  

1. Create a full passage plan in line with RYA Day Skipper standards.  
   - Tides & currents  
   - Weather forecast  
   - Course to steer (waypoints, bearings, distances, ETA)  
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
    model="gpt-5-mini",
    tools = [save_passage_plan_tool]
    )

    return passage_plan_agent