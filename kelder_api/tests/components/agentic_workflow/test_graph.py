from __future__ import annotations

import pytest

from unittest.mock import AsyncMock
from src.kelder_api.components.agentic_workflow.agents.chatbot import (
    ChatResponse,
    ReasoningInput,
)
from src.kelder_api.components.agentic_workflow.graph import AgentWorkflow
from src.kelder_api.components.agentic_workflow.models import (
    GeneratePassagePlan,
    Node,
    ReasoningEndNodes,
)


@pytest.mark.asyncio
async def test_agent_workflow_returns_direct_chat_response(
    fake_reasoning,
    chatbot_responses,
    mock_redis_client: AsyncMock,
):
    chatbot_responses(ChatResponse(message="Hello skipper"))
    workflow = AgentWorkflow(redis_client=mock_redis_client)

    result = await workflow.run("Hi")

    assert result == "Hello skipper"
    assert fake_reasoning.calls == []


@pytest.mark.asyncio
async def test_agent_workflow_executes_reasoning_plan_and_reports_progress(
    fake_reasoning,
    chatbot_responses,
    reasoning_plan,
    passage_outputs,
    mock_redis_client
):
    plan = [
        Node(
            node_type=ReasoningEndNodes.PASSAGE_PLAN,
            condifence=9,
            justification="Plan the requested route",
            node_input=GeneratePassagePlan(
                departure_location="Cowes",
                destination_location="Southampton",
            ),
            node_output=None,
        )
    ]
    reasoning_plan(plan)
    passage_outputs("Route prepared")
    chatbot_responses(
        ReasoningInput(message="Hand over to orchestrator"),
        ChatResponse(message="Passage plan ready"),
    )

    progress_calls: list[str] = []

    async def progress_callback(node: str) -> None:
        progress_calls.append(node)

    workflow = AgentWorkflow(redis_client=mock_redis_client)
    result = await workflow.run(
        "Plan a short hop from Cowes to Southampton",
        progress_callback=progress_callback,
    )

    assert result == "Passage plan ready"
    assert fake_reasoning.calls == ["Plan a short hop from Cowes to Southampton"]
    assert progress_calls == [
        "Generating a chat response",
        "Reasoning actions",
        "Generating a passage plan",
        "Reasoning actions",
        "Generating a chat response",
        "Evaluating the final response",
    ]
