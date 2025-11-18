from __future__ import annotations as _annotations

import logging
from dataclasses import dataclass
from pathlib import Path

from pydantic_graph import BaseNode, End, GraphRunContext

from src.kelder_api.components.agentic_workflow.agents.chatbot import (
    ChatResponse,
    ReasoningInput,
    chatbot_agent,
)
from src.kelder_api.components.agentic_workflow.agents.passage_planner import (
    passage_plan_agent,
)
from src.kelder_api.components.agentic_workflow.agents.reasoning import (
    reasoning_agent,
)
from src.kelder_api.components.agentic_workflow.agents.tidal_agent import tidal_agent
from src.kelder_api.components.agentic_workflow.models import (
    GeneratePassagePlan,
    ReasoningEndNodes,
    State,
)
from src.kelder_api.components.agentic_workflow.utils import (
    build_marks_index,
    clean_user_message,
    find_models,
    load_map,
    notify_progress,
)

# TODO: they need the date!
# TODO: Do we need getter agents and deletion agents.
# TODO: task pass or fail communication? - flag in Node model.
# TODO: do we need to allow nodes to directly communicate with the chatbot?
logger = logging.getLogger(__name__)

MARKS_FILE = Path(__file__).resolve().parents[3] / "assets" / "marks.json"
SOLENT_COASTLINE_FILE = Path(__file__).resolve().parents[3] / "assets" / "seas.json"


@dataclass
class ChatBotAgent(BaseNode[State]):
    async def run(self, ctx: GraphRunContext[State]) -> ResponseEvaluatorNode:
        logger.debug("Chatbot agent called")
        await notify_progress(ctx.state, "Generating a chat response")
        prompt = f"The users message: {ctx.state.user_message}"
        if ctx.state.workflow_length > 0:
            prompt += "\nIn response we have the following processes:"
            for node in ctx.state.workflow_plan:
                prompt += f"-Ran: {node.node_type}. Result: {node.node_output}"

        # defaults in graph initialisation
        result = await chatbot_agent.run(
            prompt, message_history=ctx.state.message_history
        )

        ctx.state.message_history += clean_user_message(
            result.new_messages(), ctx.state.user_message
        )

        return chatbot_end_nodes[type(result.output)](input=result.output.message)


@dataclass
class ReasoningAgent(BaseNode[State]):
    """TODO: add in the description of the workflow plan"""

    input: str | None = None

    async def run(
        self, ctx: GraphRunContext[State]
    ) -> ChatBotAgent | BuildPassageNode | TidalSearchNode:
        logger.debug("Reasoning agent called")
        await notify_progress(ctx.state, "Reasoning actions")

        if ctx.state.workflow_length == 0:
            result = await reasoning_agent.run(
                ctx.state.user_message, message_history=ctx.state.message_history
            )
            ctx.state.workflow_plan = result.output.plan
            ctx.state.job_count = 0

        if ctx.state.job_count < ctx.state.workflow_length:
            return reasoning_end_nodes[
                ctx.state.workflow_plan[ctx.state.job_count].node_type
            ](ctx.state.workflow_plan[ctx.state.job_count].node_input)
        else:
            return ChatBotAgent()


@dataclass
class BuildPassageNode(BaseNode[State]):
    """TODO: add in the passage plan description"""

    passage_plan_description: GeneratePassagePlan

    async def run(self, ctx: GraphRunContext[State]) -> ReasoningAgent:
        logger.debug("Passage planing agent called")
        await notify_progress(ctx.state, "Generating a passage plan")

        MARKS_DATA = load_map(MARKS_FILE)
        SEA_DATA = load_map(SOLENT_COASTLINE_FILE)
        MARKS_INDEX = build_marks_index(MARKS_DATA)

        prompt = (
            f"Users message: {ctx.state.user_message}\n"
            f"Task description: {self.passage_plan_description}"
        )

        if ctx.state.passage_plan:
            prompt += f"Previous plan: {ctx.state.passage_plan}"
        if ctx.state.workflow_length > 0:
            prompt += "\nIn response we have the following processes:"
            for node in ctx.state.workflow_plan:
                prompt += f"-Ran: {node.node_type}. Result: {node.node_output}"

        tidal_nodes = find_models(
            ctx.state.workflow_plan, ReasoningEndNodes.TIDAL_SEARCH
        )
        if len(tidal_nodes) > 0:
            prompt += f"Latest tidal analysis: {tidal_nodes[-1].node_output}"

        result = await passage_plan_agent.run(
            prompt,
            deps={
                "redis_client": ctx.state.redis_client,
                "marks_index": MARKS_INDEX,
                "marks_data": MARKS_DATA,
                "sea_boundries": SEA_DATA,
            },
        )
        ctx.state.workflow_plan[ctx.state.job_count].node_output = result.output
        ctx.state.passage_plan = result.output
        ctx.state.job_count += 1

        return ReasoningAgent()


# TODO: Evaluator
@dataclass
class ResponseEvaluatorNode(BaseNode[State]):
    input: str

    async def run(self, ctx: GraphRunContext[State]) -> End[str]:
        await notify_progress(ctx.state, "Evaluating the final response")
        ctx.state.workflow_plan = []
        ctx.state.job_count = 0
        return End(self.input)


@dataclass
class TidalSearchNode(BaseNode[State]):
    input_prompt: str

    async def run(self, ctx: GraphRunContext[State]) -> ReasoningAgent:
        logger.debug("Tidal query agent called for %s" % self.input_prompt)
        await notify_progress(ctx.state, "Searching tidal information")
        prompt = (
            f"Users message: {ctx.state.user_message}"
            f"Task description: {self.input_prompt}"
        )

        result = await tidal_agent.run(prompt)

        ctx.state.workflow_plan[ctx.state.job_count].node_output = result.output
        ctx.state.job_count += 1

        return ReasoningAgent()


chatbot_end_nodes = {
    ReasoningInput: ReasoningAgent,
    ChatResponse: ResponseEvaluatorNode,
}

reasoning_end_nodes = {
    ReasoningEndNodes.PASSAGE_PLAN: BuildPassageNode,
    ReasoningEndNodes.TIDAL_SEARCH: TidalSearchNode,
}
