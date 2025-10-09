from dataclasses import dataclass, field

from pydantic_ai.messages import ModelMessage
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

@dataclass
class State:
    user_message: str | None = field(default=None)
    message_history: list[ModelMessage] = field(default_factory=list)
    passage_plan: PassagePlan | None = field(default = None)
    fake_transport: bool = field(default = False)