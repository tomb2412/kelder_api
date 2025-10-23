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
from src.kelder_api.components.agentic_workflow.agents.tidal_agent import tidal_agent
from src.kelder_api.components.agentic_workflow.models import (
    GeneratePassagePlan,
    State,
    NodeType,
)
from src.kelder_api.components.agentic_workflow.utils import (
    clean_user_message,
    find_models
)



# TODO: they need the date!
# TODO: Do we need getter agents and deletion agents.
# TODO: task pass or fail communication? - flag in Node model.
# TODO: do we need to allow nodes to directly communicate with the chatbot?
logger = logging.getLogger(__name__)


@dataclass
class ChatBotAgent(BaseNode[State]):
    description: str

    async def run(self, ctx: GraphRunContext[State]) -> ResponseEvaluatorNode:
        logger.debug("Chatbot agent called")
        prompt = f"The users message: {ctx.state.user_message}"
        if ctx.state.workflow_length > 0:
            prompt += "\nIn response we have the following processes:"
            for node in ctx.state.workflow_plan:
                prompt += (f"-Ran: {node.node_type}." \
                           f" Result: {node.node_output}")
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
    """TODO: add in the description of the workflow plan"""
    async def run(
        self, ctx: GraphRunContext[State]
    ) -> ChatBotAgent | BuildPassageNode | TidalSearchNode:
        logger.debug("Reasoning agent called")
        print("Return to the reasoning agent")

        if ctx.state.workflow_length == 0: 
            result = await reasoning_agent.run(
                ctx.state.user_message, message_history=ctx.state.message_history
            )
            print(f"The reasoning agent output: {result.output}")
            ctx.state.workflow_plan = result.output.plan
            ctx.state.job_count = 0
        
        if ctx.state.job_count < ctx.state.workflow_length:
            print(f"Current node: {ctx.state.workflow_plan[ctx.state.job_count].node_type}")
            return chatbot_end_nodes[
                ctx.state.workflow_plan[ctx.state.job_count].node_type
            ](ctx.state.workflow_plan[ctx.state.job_count].node_input)
        else:
            return ChatBotAgent(description="")



@dataclass
class BuildPassageNode(BaseNode[State]):
    """TODO: add in the passage plan description"""
    passage_plan_description: GeneratePassagePlan

    async def run(self, ctx: GraphRunContext[State]) -> ReasoningAgent:
        logger.debug("Passage planing agent called")

        prompt = f"Users message: {ctx.state.user_message}\n" \
            f"Task description: {self.passage_plan_description}"

        if ctx.state.passage_plan:
            prompt += f"Previous plan: {ctx.state.passage_plan}"
        if ctx.state.workflow_length > 0:
            prompt += "\nIn response we have the following processes:"
            for node in ctx.state.workflow_plan:
                prompt += (f"-Ran: {node.node_type}." \
                           f" Result: {node.node_output}")

        tidal_nodes = find_models(ctx.state.workflow_plan, NodeType.TIDAL_SEARCH)
        if len(tidal_nodes) > 0:
            prompt += f"Latest tidal analysis: {tidal_nodes[-1].node_output}"
        
        print("Generating the plan")
        result = await passage_plan_agent.run(prompt)
        print(f"The passage plan has been produced")
        ctx.state.workflow_plan[ctx.state.job_count].node_output = result.output
        ctx.state.passage_plan = result.output
        ctx.state.job_count += 1

        print("returning to the reasoning agent")
        return ReasoningAgent()


# TODO: Evaluator
@dataclass
class ResponseEvaluatorNode(BaseNode[State]):
    input: str

    async def run(self, ctx: GraphRunContext[State]) -> End[str]:
        ctx.state.workflow_plan = []
        ctx.state.job_count = 0
        return End(self.input)

@dataclass
class TidalSearchNode(BaseNode[State]):
    input_prompt: str
    
    async def run(self, ctx: GraphRunContext[State]) -> ReasoningAgent:
        logger.debug("Tidal query agent called for %s" %self.input_prompt)
        prompt = f"Users message: {ctx.state.user_message}" \
            f"Task description: {self.input_prompt}"

        result = await tidal_agent.run(prompt)

        ctx.state.workflow_plan[ctx.state.job_count].node_output = result.output
        ctx.state.job_count += 1

        return ReasoningAgent()

chatbot_end_nodes = {
    NodeType.CHAT: ChatBotAgent,
    NodeType.PASSAGE_PLAN: BuildPassageNode,
    NodeType.TIDAL_SEARCH: TidalSearchNode,
}
