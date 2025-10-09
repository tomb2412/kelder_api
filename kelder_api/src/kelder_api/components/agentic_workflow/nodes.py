from __future__ import annotations as _annotations
from dataclasses import dataclass

from pydantic_graph import BaseNode, End, GraphRunContext


from src.kelder_api.components.agentic_workflow.models import (
    State
)
from src.kelder_api.components.agentic_workflow.agents.chatbot import(
    chatbot_agent,
    ChatResponse,
    TidalSearch,
    BuildPassageRoute
)

@dataclass
class FakeResult:
    output: ChatResponse

@dataclass
class ChatBotAgent(BaseNode[State]):
    async def run(self, ctx: GraphRunContext[State]) -> ResponseEvaluatorNode:
        # Conditional return logic        

        if ctx.state.fake_transport:
            result = FakeResult(output=ChatResponse("Mock response"))
        else:
            # defaults in graph initialisation
            result = chatbot_agent.run(
                ctx.state.user_message,
                message_history = ctx.state.message_history
            )
            ctx.state.message_history += result.new_messages()

        return chatbot_end_nodes[type(result.output)](result.output)


@dataclass
class BuildPassageNode(BaseNode[State]):
    async def run(self, ctx: GraphRunContext[State]):
        pass


@dataclass
class ResponseEvaluatorNode(BaseNode[State]):
    input: str
    async def run(self, ctx: GraphRunContext[State]) -> End[str]:
        return End(self.input)


@dataclass
class TidalSearchNode(BaseNode[State]):
    async def run(self, ctx: GraphRunContext[State]):
        pass

chatbot_end_nodes = {
    ChatResponse: ResponseEvaluatorNode,
    # BuildPassageRoute: BuildPassageNode,
    # TidalSearch: TidalSearchNode,
}