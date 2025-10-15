
from pydantic_graph import Graph

from src.kelder_api.components.agentic_workflow.models import State
from src.kelder_api.components.agentic_workflow.nodes import (
    ChatBotAgent,
    ResponseEvaluatorNode,
    ReasoningAgent,
    TidalSearchNode,
    BuildPassageNode,
)

class AgentWorkflow:
    def __init__(self, fake_transport: bool = False):
        self.state = State(fake_transport = fake_transport)
        self.graph = Graph(nodes = (
            ChatBotAgent, 
            ResponseEvaluatorNode,
            ReasoningAgent,
            TidalSearchNode,
            BuildPassageNode,
            )
        )

    async def run(self, user_message: str) -> str:
        self.state.user_message = user_message
        result = await self.graph.run(ReasoningAgent(), state=self.state)

        response = result.output
        return response