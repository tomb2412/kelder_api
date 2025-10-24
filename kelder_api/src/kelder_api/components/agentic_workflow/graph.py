from pydantic_graph import Graph

from src.kelder_api.components.agentic_workflow.models import State
from src.kelder_api.components.agentic_workflow.nodes import (
    BuildPassageNode,
    ChatBotAgent,
    ReasoningAgent,
    ResponseEvaluatorNode,
    TidalSearchNode,
)


class AgentWorkflow:
    def __init__(self):
        self.state = State()
        self.graph = Graph(
            nodes=(
                ChatBotAgent,
                ResponseEvaluatorNode,
                ReasoningAgent,
                TidalSearchNode,
                BuildPassageNode,
            )
        )

    async def run(self, user_message: str) -> str:
        self.state.user_message = user_message
        result = await self.graph.run(ChatBotAgent(), state=self.state)

        response = result.output
        return response