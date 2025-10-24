import json
from typing import Any, Dict, Iterable, Optional


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
