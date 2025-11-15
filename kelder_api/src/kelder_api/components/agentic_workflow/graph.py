from typing import Awaitable, Callable

from pydantic_graph import Graph

from src.kelder_api.components.agentic_workflow.models import State
from src.kelder_api.components.agentic_workflow.nodes import (
    BuildPassageNode,
    ChatBotAgent,
    ReasoningAgent,
    ResponseEvaluatorNode,
    TidalSearchNode,
)
from src.kelder_api.components.redis_client.redis_client import RedisClient

ProgressCallback = Callable[[str], Awaitable[None]]


class AgentWorkflow:
    def __init__(self, redis_client: RedisClient):
        self.state = State(redis_client=redis_client)
        self.graph = Graph(
            nodes=(
                ChatBotAgent,
                ResponseEvaluatorNode,
                ReasoningAgent,
                TidalSearchNode,
                BuildPassageNode,
            )
        )

    async def run(
        self, user_message: str, progress_callback: ProgressCallback | None = None
    ) -> str:
        self.state.user_message = user_message
        self.state.progress_callback = progress_callback
        try:
            result = await self.graph.run(ChatBotAgent(), state=self.state)
        finally:
            self.state.progress_callback = None

        response = result.output
        if hasattr(response, "message"):
            return response.message
        return str(response)
