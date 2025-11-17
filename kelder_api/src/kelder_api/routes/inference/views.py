import asyncio
import json
import logging
from uuid import uuid4

from fastapi import APIRouter, Request
from starlette.responses import StreamingResponse

from src.kelder_api.components.agentic_workflow.graph import AgentWorkflow
from src.kelder_api.configuration.settings import get_settings
from src.kelder_api.routes.inference.utils import error_stream, extract_user_prompt

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Agentic"])


async def stream_chat(user_prompt: str, agent_workflow: AgentWorkflow):
    # define some stream metadata:
    chunk_size = get_settings().inference.stream_chunk_size
    logger.info("Requesting inference with chunk size %s", chunk_size)

    # generate unique IDs per message / text block
    message_id = str(uuid4())
    text_id = "text-" + str(uuid4())

    # Provide callbacks of the current state
    queue = asyncio.Queue()

    async def notify(message: str):
        await queue.put({"processing_update": message})

    run_coroutine = agent_workflow.run(user_prompt, notify)

    graph_future = asyncio.ensure_future(run_coroutine)
    queue_future = asyncio.ensure_future(queue.get())

    # Signal start of message (SSE JSON data)
    yield f"data: {json.dumps({'type': 'start', 'messageId': message_id})}\n\n"
    yield f"data: {json.dumps({'type': 'text-start', 'id': text_id})}\n\n"

    try:
        while True:
            done, pending = await asyncio.wait(
                {graph_future, queue_future},
                return_when=asyncio.FIRST_COMPLETED,
            )

            # 1. If a queue update is ready → stream it
            if queue_future in done:
                chunk = queue_future.result()
                yield "event: data\n"
                yield f"data: {
                    json.dumps(
                        {
                            'type': 'data-progress',
                            'data': {'node': chunk['processing_update']},
                            'transient': True,
                        }
                    )
                }\n\n"
                # re-arm the queue future
                queue_future = asyncio.ensure_future(queue.get())

            # 2. If the graph finished → return final result
            if graph_future in done:
                workflow_response = graph_future.result()
                break

    except Exception as exc:  # pragma: no cover - defensive logging
        logger.exception("Agent workflow failed: %s", exc)
        for chunk in error_stream("Agent workflow failed", message_id=message_id):
            yield chunk
        return

    # Stream the workflow response in chunks to match existing SSE expectations
    for index in range(0, len(workflow_response), chunk_size):
        chunk = workflow_response[index : index + chunk_size]
        yield f"data: {
            json.dumps({'type': 'text-delta', 'id': text_id, 'delta': chunk})
        }\n\n"
        await asyncio.sleep(0.025)

    # stream finished — close the text block, send finish and termination markers
    yield f"data: {json.dumps({'type': 'text-end', 'id': text_id})}\n\n"
    yield f"data: {json.dumps({'type': 'finish'})}\n\n"
    yield "data: [DONE]\n\n"
    logger.info("Completed streaming response %s", message_id)


@router.post("/chat_stream")
async def StreamChatResponse(request: Request):
    # read incoming request body minimally / adapt if you already get `request.message`
    print("Chat stream hit")
    body = await request.json()
    user_prompt = extract_user_prompt(body)
    agent_workflow = request.app.state.agent_workflow

    if not user_prompt:
        message_id = str(uuid4())
        logger.warning("Chat stream request missing user prompt")
        return StreamingResponse(
            error_stream("No user prompt provided", message_id=message_id),
            media_type="text/event-stream",
        )
    return StreamingResponse(
        stream_chat(user_prompt, agent_workflow),
        media_type="text/event-stream",  # SSE
        headers={
            # required by Vercel UI data-stream protocol
            "x-vercel-ai-ui-message-stream": "v1",
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
        },
    )


@router.post("/chat_clear")
async def ClearChatHistory(request: Request):
    agent_workflow = request.app.state.agent_workflow
    agent_workflow.state.message_history = []
    agent_workflow.state.workflow_plan = []
    agent_workflow.state.job_count = 0
    logger.info("Cleared chat history for agent workflow")
    return {"status": "ok"}
