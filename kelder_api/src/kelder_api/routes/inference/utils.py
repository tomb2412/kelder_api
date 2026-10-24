import json
from typing import Any, Dict, Iterable, Optional

from pydantic_ai.exceptions import ModelHTTPError


def extract_user_prompt(payload: Dict[str, Any]) -> Optional[str]:
    message = payload.get("message")
    if isinstance(message, str) and message.strip():
        return message.strip()

    messages = payload.get("messages")
    if isinstance(messages, list):
        for entry in reversed(messages):
            if not isinstance(entry, dict):
                continue
            parts = entry.get("parts")
            if not isinstance(parts, list):
                continue
            for part in parts:
                if not isinstance(part, dict):
                    continue
                if part.get("type") != "text":
                    continue
                text = part.get("text")
                if isinstance(text, str) and text.strip():
                    return text.strip()
    return None


def error_stream(error: str, message_id: Optional[str] = None) -> Iterable[str]:
    payload = {"type": "error", "error": error}
    if message_id is not None:
        payload["messageId"] = message_id

    yield f"data: {json.dumps(payload)}\n\n"
    yield f"data: {json.dumps({'type': 'finish'})}\n\n"
    yield "data: [DONE]\n\n"


def describe_workflow_error(exc: BaseException) -> str:
    """Turn a workflow failure into a message that is safe to show the user."""
    if isinstance(exc, ModelHTTPError):
        body = exc.body if isinstance(exc.body, dict) else {}
        if body.get("code") == "insufficient_quota":
            return "The assistant is unavailable: the AI provider quota is used up."
        if exc.status_code == 429:
            return "The assistant is busy right now, please try again in a minute."
        if exc.status_code >= 500:
            return "The AI provider is having problems, please try again shortly."
    return "Agent workflow failed"
