from __future__ import annotations

from unittest.mock import AsyncMock

import pytest
from pydantic_ai.messages import (
    ModelMessage,
    ModelResponse,
    TextPart,
    ToolCallPart,
    ToolReturnPart,
)
from pydantic_ai.models.function import AgentInfo, FunctionModel
from pydantic_ai.models.test import TestModel

from src.kelder_api.components.agentic_workflow.agents.chatbot import chatbot_agent
from src.kelder_api.components.agentic_workflow.agents.tidal_agent import tidal_agent
from src.kelder_api.components.agentic_workflow.chat_storage import _adapter
from src.kelder_api.components.agentic_workflow.workflow import AgentWorkflow


def _ask_for_tides(messages: list[ModelMessage], info: AgentInfo) -> ModelResponse:
    """Call the tidal tool once, then reply with whatever it returned."""
    tool_returns = [
        part
        for message in messages
        for part in message.parts
        if isinstance(part, ToolReturnPart)
    ]
    if not tool_returns:
        return ModelResponse(
            parts=[
                ToolCallPart(
                    "get_tidal_information", {"request": "High water at Cowes"}
                )
            ]
        )
    return ModelResponse(parts=[TextPart(f"Tides: {tool_returns[-1].content}")])


def _failing_model(messages: list[ModelMessage], info: AgentInfo) -> ModelResponse:
    raise RuntimeError("tidal API down")


@pytest.mark.asyncio
async def test_direct_reply_is_returned_and_saved(mock_redis_client: AsyncMock):
    workflow = AgentWorkflow(redis_client=mock_redis_client)

    with chatbot_agent.override(
        model=TestModel(call_tools=[], custom_output_text="Hello skipper")
    ):
        result = await workflow.run("test_user", "Hi")

    assert result == "Hello skipper"
    key, saved = mock_redis_client.write_value.await_args.args
    assert key == "chat:test_user:history"
    assert len(_adapter.validate_json(saved)) == 2


@pytest.mark.asyncio
async def test_chatbot_delegates_to_tidal_agent_and_reports_progress(
    mock_redis_client: AsyncMock,
):
    progress_calls: list[str] = []

    async def progress_callback(message: str) -> None:
        progress_calls.append(message)

    workflow = AgentWorkflow(redis_client=mock_redis_client)

    with (
        chatbot_agent.override(model=FunctionModel(_ask_for_tides)),
        tidal_agent.override(
            model=TestModel(call_tools=[], custom_output_text="HW 14:02 UTC")
        ),
    ):
        result = await workflow.run(
            "test_user", "When is high water?", progress_callback=progress_callback
        )

    assert result == "Tides: HW 14:02 UTC"
    assert progress_calls == [
        "Generating a chat response",
        "Searching tidal information",
    ]


@pytest.mark.asyncio
async def test_tidal_agent_failure_is_reported_to_the_chatbot(
    mock_redis_client: AsyncMock,
):
    workflow = AgentWorkflow(redis_client=mock_redis_client)

    with (
        chatbot_agent.override(model=FunctionModel(_ask_for_tides)),
        tidal_agent.override(model=FunctionModel(_failing_model)),
    ):
        result = await workflow.run("test_user", "When is high water?")

    assert result.startswith("Tides: Tidal data unavailable")


def test_marks_index_loads_from_assets(mock_redis_client: AsyncMock):
    workflow = AgentWorkflow(redis_client=mock_redis_client)

    assert workflow.marks_data
    assert workflow.marks_index is not None
