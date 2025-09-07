import logging
import asyncio
import json
from uuid import uuid4

from dotenv import load_dotenv
import os
load_dotenv(override=True)
openai_api_key = os.getenv('OPENAI_API_KEY')

from fastapi import APIRouter
from agents import Runner
from starlette.responses import StreamingResponse
from openai.types.responses import ResponseTextDeltaEvent

from src.kelder_api.routes.inference.models import InferenceRequest, Message
from src.kelder_api.routes.inference.agents import get_agent

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Agentic"])

@router.post("/chat_stream")
async def StreamChatResponse(request: InferenceRequest):
    logger.info("Requesting inference")
    
    conversation_history = []
    for msg in request.messages:
        for part in msg.parts:
            if part.type == 'text':
                conversation_history.append({
                    'role': msg.role,
                    'content': part.text
                })
    
    agent = get_agent()
    result = Runner.run_streamed(
        agent,
        input=conversation_history
        )

    async def async_generator():     
        first_chunk = True
        message_id = str(uuid4())
        text_id = "text-" + str(uuid4())  # Generate unique ID

        yield f"data: {json.dumps({'type': 'start', 'messageId': message_id})}\n\n"

        async for event in result.stream_events():        
            if event.type == "raw_response_event" and isinstance(event.data, ResponseTextDeltaEvent):
                # Start text stream on first chunk
                if first_chunk:
                    yield f"data: {json.dumps({'type': 'text-start', 'id': text_id})}\n\n"
                    first_chunk = False
                
                # Stream text delta
                yield f"data: {json.dumps({'type': 'text-delta', 'id': text_id, 'delta': event.data.delta})}\n\n"

            elif event.type == "response.completed":
                # End text stream
                yield f"data: {json.dumps({'type': 'text-end', 'id': text_id})}\n\n"
                # small pause to allow cooperative multitasking
            await asyncio.sleep(0)
                # Finish the message
        yield f"data: {json.dumps({'type': 'finish'})}\n\n"
        
        # Terminate the stream
        yield f"data: [DONE]\n\n"
            
    return StreamingResponse(
        async_generator(),
        media_type="text/event-stream",
        headers={
            "x-vercel-ai-ui-message-stream": "v1",  # Required header
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
        })


