import logging
from typing import Awaitable, Callable

from pydantic_graph import Graph

from src.kelder_api.components.agentic_workflow.chat_storage import (
    clear_history,
    load_history,
    save_history,
)
from src.kelder_api.components.agentic_workflow.models import State
from src.kelder_api.components.agentic_workflow.nodes import (
    BuildPassageNode,
    ChatBotAgent,
    ReasoningAgent,
    ResponseEvaluatorNode,
    TidalSearchNode,
)
from src.kelder_api.components.neo4j_client import Neo4jClient
from src.kelder_api.components.redis_client.redis_client import RedisClient
from src.kelder_api.configuration.logging_config import setup_logging

setup_logging(component="agent_workflow")
logger = logging.getLogger("agent_workflow")


class AgentWorkflow:
    def __init__(self, redis_client: RedisClient, neo4j_client: Neo4jClient | None = None):
        self.redis_client = redis_client
        self.neo4j_client = neo4j_client
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
        self,
        user_id: str,
        user_message: str,
        progress_callback: Callable[[str], Awaitable[None]] | None = None,
    ) -> str:
        history = await load_history(self.redis_client, user_id)
        state = State(
            redis_client=self.redis_client,
            neo4j_client=self.neo4j_client,
            message_history=history,
        )
        state.user_message = user_message
        state.progress_callback = progress_callback
        try:
            logger.info("Running the graph for user %s", user_id)
            result = await self.graph.run(ChatBotAgent(), state=state)
            await save_history(self.redis_client, user_id, state.message_history)
        finally:
            state.progress_callback = None

        response = result.output
        if hasattr(response, "message"):
            return response.message
        return str(response)

    async def clear_user_history(self, user_id: str) -> None:
        await clear_history(self.redis_client, user_id)
