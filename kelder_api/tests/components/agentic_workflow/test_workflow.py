from __future__ import annotations

from datetime import datetime, timezone
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
from src.kelder_api.components.agentic_workflow.agents.models import (
    PassagePlan,
    Waypoint,
)
from src.kelder_api.components.agentic_workflow.agents.tidal_agent import tidal_agent
from src.kelder_api.components.agentic_workflow.chat_storage import _adapter
from src.kelder_api.components.agentic_workflow.workflow import AgentWorkflow
from src.kelder_api.components.db_manager.service import DBManager
from src.kelder_api.components.passage_plan_tracker.models import PassagePlanProgress
from src.kelder_api.components.passage_plan_tracker.service import PassagePlanTracker
from src.kelder_api.components.redis_client.types import RedisSetNames


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


def _call_tools_then_echo(*calls: tuple[str, dict]):
    """Call each tool in turn, then reply with the last tool's return value."""

    def _model(messages: list[ModelMessage], info: AgentInfo) -> ModelResponse:
        tool_returns = [
            part
            for message in messages
            for part in message.parts
            if isinstance(part, ToolReturnPart)
        ]
        if len(tool_returns) < len(calls):
            name, args = calls[len(tool_returns)]
            return ModelResponse(parts=[ToolCallPart(name, args)])
        return ModelResponse(parts=[TextPart(str(tool_returns[-1].content))])

    return _model


def _saved_plan(db_manager: DBManager) -> int:
    plan = PassagePlan(
        departure_place_name="Hamble Point",
        desination_place_name="Cowes",
        course_to_steer=[
            Waypoint(name="Hamble Point", latitude=50.84, longitude=-1.31),
            Waypoint(name="Cowes", latitude=50.76, longitude=-1.30),
        ],
    )
    return db_manager.save_passage_plan(plan).unique_key


@pytest.mark.asyncio
async def test_chatbot_lists_saved_routes(mock_redis_client: AsyncMock, db_manager):
    route_id = _saved_plan(db_manager)
    workflow = AgentWorkflow(redis_client=mock_redis_client, db_manager=db_manager)

    with chatbot_agent.override(
        model=FunctionModel(_call_tools_then_echo(("list_saved_routes", {})))
    ):
        result = await workflow.run("test_user", "What routes have I saved?")

    assert f"'route_id': {route_id}" in result
    assert "'destination': 'Cowes'" in result


@pytest.mark.asyncio
async def test_chatbot_loads_saved_route_as_active_plan(
    mock_redis_client: AsyncMock, db_manager
):
    route_id = _saved_plan(db_manager)
    workflow = AgentWorkflow(redis_client=mock_redis_client, db_manager=db_manager)

    with chatbot_agent.override(
        model=FunctionModel(
            _call_tools_then_echo(("load_saved_route", {"route_id": route_id}))
        )
    ):
        await workflow.run("test_user", "Load my Cowes route")

    set_name, plan = mock_redis_client.write_set.await_args.args
    assert set_name == RedisSetNames.PASSAGE_PLAN
    assert plan.desination_place_name == "Cowes"


@pytest.mark.asyncio
async def test_loading_unknown_route_is_reported(
    mock_redis_client: AsyncMock, db_manager
):
    workflow = AgentWorkflow(redis_client=mock_redis_client, db_manager=db_manager)

    with chatbot_agent.override(
        model=FunctionModel(
            _call_tools_then_echo(("load_saved_route", {"route_id": 42}))
        )
    ):
        result = await workflow.run("test_user", "Load route 42")

    assert result == "No saved route with id 42."
    mock_redis_client.write_set.assert_not_awaited()


@pytest.mark.asyncio
async def test_chatbot_reports_dtw_and_xte(
    mock_redis_client: AsyncMock, monkeypatch: pytest.MonkeyPatch
):
    progress = PassagePlanProgress(
        timestamp=datetime(2025, 6, 1, 9, tzinfo=timezone.utc),
        distance_to_waypoint=2.4,
        next_waypoint_name="Cowes",
        next_waypoint_index=1,
        cross_track_error=0.3,
    )
    monkeypatch.setattr(
        PassagePlanTracker, "compute_progress", AsyncMock(return_value=progress)
    )
    workflow = AgentWorkflow(redis_client=mock_redis_client)

    with chatbot_agent.override(
        model=FunctionModel(_call_tools_then_echo(("get_route_progress", {})))
    ):
        result = await workflow.run("test_user", "How far to the next mark?")

    assert "'dtw_nm': 2.4" in result
    assert "'xte_nm': 0.3" in result
    assert "'steer_to_regain_track': 'port'" in result
