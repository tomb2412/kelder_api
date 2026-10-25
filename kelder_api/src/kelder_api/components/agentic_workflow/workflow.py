from pathlib import Path
from typing import Awaitable, Callable

from pydantic_ai.usage import UsageLimits

from src.kelder_api.components.agentic_workflow.agents.chatbot import chatbot_agent
from src.kelder_api.components.agentic_workflow.chat_storage import (
    clear_history,
    load_history,
    save_history,
    trim_history,
)
from src.kelder_api.components.agentic_workflow.models import ChatDeps, VesselServices
from src.kelder_api.components.agentic_workflow.utils import (
    build_marks_index,
    load_map,
)
from src.kelder_api.components.db_manager.service import DBManager
from src.kelder_api.components.neo4j_client import Neo4jClient
from src.kelder_api.components.redis_client.redis_client import RedisClient
from src.kelder_api.configuration.logging_controller import get_logger
from src.kelder_api.configuration.settings import get_settings

logger = get_logger(__name__, "agent_workflow")

MARKS_FILE = Path(__file__).resolve().parents[2] / "assets" / "marks.json"


class AgentWorkflow:
    def __init__(
        self,
        redis_client: RedisClient,
        neo4j_client: Neo4jClient | None = None,
        db_manager: DBManager | None = None,
        vessel_services: VesselServices | None = None,
    ):
        self.redis_client = redis_client
        self.neo4j_client = neo4j_client
        self.db_manager = db_manager
        self.vessel_services = vessel_services
        self.marks_data = load_map(MARKS_FILE)
        self.marks_index = build_marks_index(self.marks_data)

    async def run(
        self,
        user_id: str,
        user_message: str,
        progress_callback: Callable[[str], Awaitable[None]] | None = None,
    ) -> str:
        settings = get_settings().inference
        history = trim_history(
            await load_history(self.redis_client, user_id),
            settings.max_history_messages,
        )
        deps = ChatDeps(
            redis_client=self.redis_client,
            neo4j_client=self.neo4j_client,
            db_manager=self.db_manager,
            vessel=self.vessel_services,
            marks_data=self.marks_data,
            marks_index=self.marks_index,
            progress_callback=progress_callback,
        )

        logger.info("Running the chatbot for user %s", user_id)
        await deps.notify("Generating a chat response")
        result = await chatbot_agent.run(
            user_message,
            message_history=history,
            deps=deps,
            usage_limits=UsageLimits(request_limit=settings.max_model_requests),
        )
        logger.info("Chatbot run for user %s used %s", user_id, result.usage())

        await save_history(
            self.redis_client,
            user_id,
            trim_history(result.all_messages(), settings.max_history_messages),
        )
        return result.output

    async def clear_user_history(self, user_id: str) -> None:
        await clear_history(self.redis_client, user_id)
