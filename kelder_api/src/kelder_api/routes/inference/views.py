import asyncio
import json
import logging
from uuid import uuid4

from fastapi import APIRouter, Request
from starlette.responses import StreamingResponse

from src.kelder_api.configuration.settings import get_settings
from src.kelder_api.routes.inference.utils import error_stream, extract_user_prompt

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Agentic"])


@router.post("/chat_stream")
async def StreamChatResponse(request: Request):
    # read incoming request body minimally / adapt if you already get `request.message`
    body = await request.json()
    user_prompt = extract_user_prompt(body)

    if not user_prompt:
        message_id = str(uuid4())
        logger.warning("Chat stream request missing user prompt")
        return StreamingResponse(
            error_stream("No user prompt provided", message_id=message_id),
            media_type="text/event-stream",
        )

    chunk_size = get_settings().inference.stream_chunk_size
    logger.info("Requesting inference with chunk size %s", chunk_size)

    async def stream_chat():
        # generate unique IDs per message / text block
        message_id = str(uuid4())
        text_id = "text-" + str(uuid4())

        # Signal start of message (SSE JSON data)
        yield f"data: {json.dumps({'type': 'start', 'messageId': message_id})}\n\n"

        agent_workflow = request.app.state.agent_workflow

        try:
            workflow_response = await agent_workflow.run(user_prompt)
        except Exception as exc:  # pragma: no cover - defensive logging
            logger.exception("Agent workflow failed: %s", exc)
            for chunk in error_stream("Agent workflow failed", message_id=message_id):
                yield chunk
            return

        # Stream the workflow response in chunks to match existing SSE expectations
        yield f"data: {json.dumps({'type': 'text-start', 'id': text_id})}\n\n"
        for index in range(0, len(workflow_response), chunk_size):
            chunk = workflow_response[index : index + chunk_size]
            yield f"data: {
                json.dumps({'type': 'text-delta', 'id': text_id, 'delta': chunk})
            }\n\n"
            await asyncio.sleep(0)

        # stream finished — close the text block, send finish and termination markers
        yield f"data: {json.dumps({'type': 'text-end', 'id': text_id})}\n\n"
        yield f"data: {json.dumps({'type': 'finish'})}\n\n"
        yield "data: [DONE]\n\n"
        logger.info("Completed streaming response %s", message_id)

    return StreamingResponse(
        stream_chat(),
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
