from dataclasses import dataclass, field
from typing import List
from enum import StrEnum

from pydantic import BaseModel, computed_field, Field
from pydantic_ai.messages import ModelMessage

from src.kelder_api.components.agentic_workflow.agents.models import PassagePlan

"""
Feautures:
- Waypoint / passage plan
- Weather and tides

"""
class NodeType(StrEnum):
    CHAT = "chat"
    PASSAGE_PLAN = "passage_plan"
    TIDAL_SEARCH = "tidal_search"


class GeneratePassagePlan(BaseModel):
    # TODO: add Field descriptions
    departure_location: str
    destination_location: str
    departure_time: str | None = None
    destination_time: str | None = None
    extra_considerations: str | None = None



class Node(BaseModel):
    # TODO: Potentially node_type and node_input may lead to conflicting results?
    node_type: NodeType = Field(
        description="The node which will be called in the output."
    )
    condifence: int = Field(
        description="Out of 10, confidence level that this node is required."
    )
    justification: str = Field(
        description="A consise, very short reason why this node is required."
    )
    node_input: str | GeneratePassagePlan = Field(
        description="The required input for the node type of what the node needs to do."
    )
    node_output: str | None = Field(
        description="Completed by the tool as a summary of their tool."
    )

#@dataclass
class State(BaseModel):
    user_message: str | None = field(default=None)
    message_history: list[ModelMessage] = field(default_factory=list)

    workflow_plan: List[Node] = field(default_factory=list)
    job_count: int = 0

    passage_plan: PassagePlan | None = field(default=None)
    fake_transport: bool = field(default=False)

    @computed_field
    @property
    def workflow_length(self) -> int:
        return len(self.workflow_plan)