from __future__ import annotations

from dataclasses import dataclass
from types import SimpleNamespace
from typing import Any, Iterable, List
from unittest.mock import AsyncMock

import pytest

from src.kelder_api.components.agentic_workflow import nodes as nodes_module
from src.kelder_api.components.agentic_workflow.agents import chatbot as chatbot_module
from src.kelder_api.components.agentic_workflow.agents import (
    passage_planner as passage_module,
)
from src.kelder_api.components.agentic_workflow.agents import (
    reasoning as reasoning_module,
)
from src.kelder_api.components.agentic_workflow.agents import (
    tidal_agent as tidal_module,
)
from src.kelder_api.components.agentic_workflow.agents.chatbot import (
    ChatResponse,
    ReasoningInput,
)
from src.kelder_api.components.redis_client.redis_client import RedisClient


class _FakeAgentResult:
    def __init__(self, output: Any):
        self.output = output

    def new_messages(self) -> List[Any]:
        return []


class _ChatbotStub:
    def __init__(self) -> None:
        self._responses: list[Any] = []
        self.prompts: list[str] = []

    def set_responses(self, responses: Iterable[Any]) -> None:
        self._responses = list(responses)

    async def run(self, prompt: str, message_history: list[Any] | None = None):
        self.prompts.append(prompt)
        if not self._responses:
            raise AssertionError("No chatbot responses configured")
        response = self._responses.pop(0)
        return _FakeAgentResult(response)


class _ReasoningStub:
    def __init__(self) -> None:
        self._plan: list[Any] = []
        self.calls: list[str] = []

    def set_plan(self, nodes: list[Any]) -> None:
        self._plan = nodes

    async def run(self, user_message: str, message_history: list[Any] | None = None):
        self.calls.append(user_message)
        plan = SimpleNamespace(plan=self._plan)
        return SimpleNamespace(output=plan)


@dataclass
class _SimpleAgentStub:
    outputs: list[Any]

    def __init__(self) -> None:
        self.outputs = []
        self.prompts: list[str] = []

    def set_outputs(self, outputs: Iterable[Any]) -> None:
        self.outputs = list(outputs)

    async def run(self, prompt: str, deps: Any = None):
        self.prompts.append(prompt)
        if not self.outputs:
            raise AssertionError("No outputs configured for agent stub")
        return SimpleNamespace(output=self.outputs.pop(0))


@pytest.fixture()
def fake_chatbot(monkeypatch: pytest.MonkeyPatch) -> _ChatbotStub:
    stub = _ChatbotStub()
    monkeypatch.setattr(chatbot_module, "chatbot_agent", stub)
    monkeypatch.setattr(nodes_module, "chatbot_agent", stub)
    return stub


@pytest.fixture()
def fake_reasoning(monkeypatch: pytest.MonkeyPatch) -> _ReasoningStub:
    stub = _ReasoningStub()
    monkeypatch.setattr(reasoning_module, "reasoning_agent", stub)
    monkeypatch.setattr(nodes_module, "reasoning_agent", stub)
    return stub


@pytest.fixture()
def fake_passage_agent(monkeypatch: pytest.MonkeyPatch) -> _SimpleAgentStub:
    stub = _SimpleAgentStub()
    monkeypatch.setattr(passage_module, "passage_plan_agent", stub)
    monkeypatch.setattr(nodes_module, "passage_plan_agent", stub)
    return stub


@pytest.fixture()
def fake_tidal_agent(monkeypatch: pytest.MonkeyPatch) -> _SimpleAgentStub:
    stub = _SimpleAgentStub()
    monkeypatch.setattr(tidal_module, "tidal_agent", stub)
    monkeypatch.setattr(nodes_module, "tidal_agent", stub)
    return stub


@pytest.fixture()
def chatbot_responses(fake_chatbot: _ChatbotStub):
    def _configure(*messages: str | ReasoningInput | ChatResponse):
        fake_chatbot.set_responses(messages)

    return _configure


@pytest.fixture()
def reasoning_plan(fake_reasoning: _ReasoningStub):
    def _configure(nodes: list[Any]):
        fake_reasoning.set_plan(nodes)

    return _configure


@pytest.fixture()
def passage_outputs(fake_passage_agent: _SimpleAgentStub):
    def _configure(*outputs: Any):
        fake_passage_agent.set_outputs(outputs)

    return _configure


@pytest.fixture()
def tidal_outputs(fake_tidal_agent: _SimpleAgentStub):
    def _configure(*outputs: Any):
        fake_tidal_agent.set_outputs(outputs)

    return _configure


@pytest.fixture()
def mock_redis_client() -> AsyncMock:
    """Provide an async mock of the redis client for GPSInterface tests."""
    client = AsyncMock(spec=RedisClient)
    client.read_value.return_value = None
    return client
