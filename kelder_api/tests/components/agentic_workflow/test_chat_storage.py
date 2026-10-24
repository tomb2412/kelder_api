from __future__ import annotations

from unittest.mock import AsyncMock

import pytest
from pydantic_ai import capture_run_messages
from pydantic_ai.messages import (
    ModelRequest,
    ModelResponse,
    SystemPromptPart,
    TextPart,
    ToolCallPart,
    ToolReturnPart,
    UserPromptPart,
)
from pydantic_ai.models.test import TestModel

from src.kelder_api.components.agentic_workflow.agents.chatbot import chatbot_agent
from src.kelder_api.components.agentic_workflow.chat_storage import (
    _adapter,
    load_history,
    trim_history,
)


def _exchange(text: str) -> list:
    return [
        ModelRequest(parts=[UserPromptPart(content=text)]),
        ModelResponse(parts=[ToolCallPart(tool_name="final_result", args={})]),
        ModelRequest(parts=[ToolReturnPart(tool_name="final_result", content="ok")]),
        ModelResponse(parts=[TextPart(content=f"reply to {text}")]),
    ]


def test_trim_history_keeps_short_history_untouched():
    history = _exchange("one")

    assert trim_history(history, max_messages=10) == history


def test_trim_history_starts_window_on_a_user_prompt():
    latest = _exchange("two")
    history = _exchange("one") + latest

    # A window of 6 would start on the orphaned tool return from "one".
    trimmed = trim_history(history, max_messages=6)

    assert trimmed == latest


@pytest.mark.asyncio
async def test_load_history_strips_persisted_system_prompts():
    legacy = [
        ModelRequest(
            parts=[
                SystemPromptPart(content="old chatbot prompt"),
                UserPromptPart(content="hi"),
            ]
        ),
        ModelResponse(parts=[TextPart(content="hello")]),
    ]
    redis = AsyncMock()
    redis.read_value.return_value = _adapter.dump_json(legacy).decode()

    history = await load_history(redis, "test_user")

    assert len(history) == 2
    assert [type(part) for part in history[0].parts] == [UserPromptPart]


@pytest.mark.asyncio
async def test_chatbot_instructions_are_sent_with_chat_history():
    chat_history = [
        ModelRequest(parts=[UserPromptPart(content="Plan a passage")]),
        ModelResponse(parts=[TextPart(content="Handing over")]),
    ]

    with capture_run_messages() as messages:
        with chatbot_agent.override(model=TestModel(call_tools=[])):
            await chatbot_agent.run(
                "Plan a passage", message_history=chat_history, deps=None
            )

    request = next(
        m for m in messages[len(chat_history) :] if isinstance(m, ModelRequest)
    )
    assert "sailing assistant" in request.instructions
