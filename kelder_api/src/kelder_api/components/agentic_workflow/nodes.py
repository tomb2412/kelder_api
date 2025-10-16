from __future__ import annotations as _annotations

import logging
from dataclasses import dataclass

from pydantic_graph import BaseNode, End, GraphRunContext

from src.kelder_api.components.agentic_workflow.agents.chatbot import (
    ChatResponse,
    chatbot_agent,
)
from src.kelder_api.components.agentic_workflow.agents.passage_planner import (
    passage_plan_agent,
)
from src.kelder_api.components.agentic_workflow.agents.reasoning import (
    reasoning_agent,
)
from src.kelder_api.components.agentic_workflow.models import (
    GeneratePassagePlan,
    State,
    NodeType,
)
from src.kelder_api.components.agentic_workflow.utils import clean_user_message


# TODO: they need the date!
logger = logging.getLogger(__name__)

@dataclass
class FakeResult:
    output: ChatResponse


@dataclass
class ChatBotAgent(BaseNode[State]):
    description: str

    async def run(self, ctx: GraphRunContext[State]) -> ResponseEvaluatorNode:
        logger.debug("Chatbot agent called")
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
        logger.debug("Reasoning agent called")
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
        
        return chatbot_end_nodes[
            ctx.state.workflow_plan[ctx.state.job_count].node_type
        ](ctx.state.workflow_plan[ctx.state.job_count].node_input)


@dataclass
class BuildPassageNode(BaseNode[State]):
    passage_plan_description: GeneratePassagePlan

    async def run(self, ctx: GraphRunContext[State]) -> ReasoningAgent:
        logger.debug("Passage planing agent called")

        prompt = f"Users message: {ctx.state.user_message}" \
            f"Task description: {self.passage_plan_description}"
        if ctx.state.passage_plan:
            prompt += f"Previous plan: {ctx.state.passage_plan}"
        
        result = await passage_plan_agent.run(
            prompt, message_history=ctx.state.message_history
        )
        
        ctx.state.workflow_plan[ctx.state.job_count].node_output = result.output
        ctx.state.job_count += 1

        return ReasoningAgent()

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
