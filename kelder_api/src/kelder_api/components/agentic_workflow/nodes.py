from __future__ import annotations as _annotations

from dataclasses import dataclass

from pydantic_graph import BaseNode, End, GraphRunContext

from src.kelder_api.components.agentic_workflow.agents.chatbot import (
    ChatResponse,
    chatbot_agent,
)
from src.kelder_api.components.agentic_workflow.agents.reasoning import (
    NodeType,
    reasoning_agent,
)
from src.kelder_api.components.agentic_workflow.models import (
    GeneratePassagePlan,
    State,
)
from src.kelder_api.components.agentic_workflow.utils import clean_user_message


@dataclass
class FakeResult:
    output: ChatResponse


@dataclass
class ChatBotAgent(BaseNode[State]):
    description: str

    async def run(self, ctx: GraphRunContext[State]) -> ResponseEvaluatorNode:
        prompt = f"The users message: {ctx.state.user_message}"
        if ctx.state.workflow_plan != []:
            prompt += "\nIn response we have the following processes:"
            for node in ctx.state.workflow_plan:
                prompt += f"-Ran: {node.node_type}."

        # Conditional return logic
        if ctx.state.fake_transport:
            result = FakeResult(output=ChatResponse("Mock response"))
        else:
            # defaults in graph initialisation
            result = await chatbot_agent.run(
                prompt, message_history=ctx.state.message_history
            )
            print(f"The chatbot response is {result.output}")

            ctx.state.message_history += clean_user_message(
                result.new_messages(), ctx.state.user_message
            )

        return ResponseEvaluatorNode(result.output)


@dataclass
class ReasoningAgent(BaseNode[State]):
    async def run(
        self, ctx: GraphRunContext[State]
    ) -> ChatBotAgent | BuildPassageNode | TidalSearchNode:
        if ctx.state.workflow_plan == []:
            if ctx.state.fake_transport:
                result = FakeResult(output=ChatResponse("Mock response"))
            else:
                result = await reasoning_agent.run(
                    ctx.state.user_message, message_history=ctx.state.message_history
                )
                print(f"The reasoning agent output: {result.output}")
            ctx.state.workflow_plan = result.output.plan
            ctx.state.job_count = 0

        ctx.state.job_count += 1
        return chatbot_end_nodes[
            ctx.state.workflow_plan[ctx.state.job_count - 1].node_type
        ](ctx.state.workflow_plan[ctx.state.job_count - 1].node_input)


@dataclass
class BuildPassageNode(BaseNode[State]):
    passage_plan_description: GeneratePassagePlan

    async def run(self, ctx: GraphRunContext[State]) -> ReasoningAgent:
        pass


@dataclass
class ResponseEvaluatorNode(BaseNode[State]):
    input: str

    async def run(self, ctx: GraphRunContext[State]) -> End[str]:
        ctx.state.workflow_plan = []
        ctx.state.job_count = 0
        return End(self.input)


@dataclass
class TidalSearchNode(BaseNode[State]):
    async def run(self, ctx: GraphRunContext[State]) -> ReasoningAgent:
        pass


chatbot_end_nodes = {
    NodeType.CHAT: ChatBotAgent,
    NodeType.PASSAGE_PLAN: BuildPassageNode,
    NodeType.TIDAL_SEARCH: TidalSearchNode,
}
