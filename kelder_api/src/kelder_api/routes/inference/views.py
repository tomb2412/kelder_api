import asyncio
import json
import logging
import os
from uuid import uuid4

from dotenv import load_dotenv
from fastapi import Request

load_dotenv(override=True)
openai_api_key = os.getenv("OPENAI_API_KEY")

from fastapi import APIRouter
from starlette.responses import StreamingResponse

from src.kelder_api.routes.inference.agents import get_chatbot_agent

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Agentic"])


@router.post("/chat_stream")
async def StreamChatResponse(request: Request):
    # read incoming request body minimally / adapt if you already get `request.message`
    body = await request.json()
    user_prompt = body.get(
        "message"
    )  # keep this minimal; adjust if your payload shape differs

    logger.info("Requesting inference")
    chatbot_agent = get_chatbot_agent()

    async def stream_chat():
        # generate unique IDs per message / text block
        message_id = str(uuid4())
        text_id = "text-" + str(uuid4())

        # Signal start of message (SSE JSON data)
        yield f"data: {json.dumps({'type': 'start', 'messageId': message_id})}\n\n"

        # Use the async context manager pattern recommended by Pydantic-AI
        async with chatbot_agent.run_stream(user_prompt) as stream_response:
            first_chunk = True

            # stream_text(delta=True) yields incremental text chunks (deltas)
            async for delta in stream_response.stream_text(delta=True):
                # send a text-start event on the first chunk
                if first_chunk:
                    yield f"data: {json.dumps({'type': 'text-start', 'id': text_id})}\n\n"
                    first_chunk = False

                # send delta parts
                yield f"data: {json.dumps({
                    'type': 'text-delta',
                    'id': text_id,
                    'delta': delta
                })}\n\n"

                # cooperative scheduling (optional but typical)
                await asyncio.sleep(0)

        # stream finished — close the text block, send finish and termination markers
        yield f"data: {json.dumps({'type': 'text-end', 'id': text_id})}\n\n"
        yield f"data: {json.dumps({'type': 'finish'})}\n\n"
        yield "data: [DONE]\n\n"

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
