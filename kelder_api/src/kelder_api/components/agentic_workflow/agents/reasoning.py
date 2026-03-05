import textwrap
from typing import List

from pydantic import BaseModel, Field
from pydantic_ai import Agent

from src.kelder_api.components.agentic_workflow.models import Node

# TODO: how will the model manage dates?
# TODO: conflicting prompt with same node more than once
# TODO: add jobs to the list
# TODO: Reasoning agent and the chat node seem not in sync


class OchestrationPlan(BaseModel):
    plan: List[Node] = Field(
        description="Please provide a list of Nodes to call, within the workflow."
    )
    description: str = Field(
        description="Very short and consise description of the workflow"
    )


prompt = textwrap.dedent(
    """
    You are an orchestration agent within a graph-based workflow, for a chatbot.

    Your task is to analyse the user's request, determine which available nodes (tools)
    are required, and in what order they should be called to meet the user's goal.

    If the user requires no nodes, simply reply with nothing

    Available nodes:
    - passage_plan: plans or adjusts a sea passage, manages routes, waypoints, and saves
     results. This always requires - departure and destination locations, but you can
       assume tomorrow if no date is given.
    - tidal_search: retrieves tidal predictions such as high/low water times, heights,
     and current water levels.

    Behaviours:
    - Break down the user request into clear workflow steps.
    - Justify briefly why each node is required.
    - Assign a confidence score out of 10 for each node.
    - Never include multiple nodes or repeat nodes.
    - Reuse existing data where possible; avoid redundant calls.
    - If the request cannot be completed using available nodes, reply with an empty
      plan to communicate this.


    Example:
    User input: "Please plan a passage between Cowes and Southampton, for tomorrow."
    Output:
    {
    "plan": [
        {
        "node_type": "passage_plan",
        "condifence": 10,
        "justification": "Required to generate the passage using tidal information."
        "node_input": "Generate a passage plan to sail from Cowes to Southampton
         tomorrow."
        "node_output": "null",
        }
    ],
    "description": "Identify optimal tide times, plan the passage, then summarise the
     result."
    }

    Be concise, structured, and logical. Focus on which nodes are needed, why, and how
     confident you are in each choice.

    ** NEVER PRODUCE A PLAN WITHOUT A CHAT NODE AT THE END **
"""
).strip()

reasoning_agent = Agent(
    model="openai:gpt-4o-mini",
    output_type=OchestrationPlan,
    system_prompt=prompt,
)
