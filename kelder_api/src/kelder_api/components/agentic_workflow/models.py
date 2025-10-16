from dataclasses import dataclass, field
from typing import List

from pydantic import BaseModel
from pydantic_ai.messages import ModelMessage

from src.kelder_api.components.agentic_workflow.agents.reasoning import Node

"""
Feautures:
- Waypoint / passage plan
- Weather and tides

"""


@dataclass
class Waypoint:
    name: str = field()
    latitude: str = field()
    latitude_hemisphere: str = field()
    longitude: str = field()
    longitude_hemisphere: str = field()


@dataclass
class PassagePlan:
    waypoints: Waypoint | None = field(default=None)


class GeneratePassagePlan(BaseModel):
    # TODO: add Field descriptions
    departure_location: str
    destination_location: str
    departure_time: str | None = None
    destination_time: str | None = None
    extra_considerations: str | None = None


@dataclass
class State:
    user_message: str | None = field(default=None)
    message_history: list[ModelMessage] = field(default_factory=list)

    workflow_plan: List[Node] = field(default_factory=list)
    job_count: int = 0

    passage_plan: PassagePlan | None = field(default=None)
    fake_transport: bool = field(default=False)
