from dataclasses import replace

from pydantic import TypeAdapter
from pydantic_ai.messages import (
    ModelMessage,
    ModelRequest,
    SystemPromptPart,
    UserPromptPart,
)

from src.kelder_api.components.redis_client.redis_client import RedisClient

_adapter = TypeAdapter(list[ModelMessage])


def _history_key(user_id: str) -> str:
    return f"chat:{user_id}:history"


def _strip_system_prompts(history: list[ModelMessage]) -> list[ModelMessage]:
    """Drop system prompt parts persisted by older versions of the agents.

    Agents now use instructions, which are sent fresh on every request. Stale
    system prompts left in stored history would otherwise override them.
    """
    cleaned: list[ModelMessage] = []
    for message in history:
        if isinstance(message, ModelRequest):
            parts = [p for p in message.parts if not isinstance(p, SystemPromptPart)]
            if not parts:
                continue
            message = replace(message, parts=parts)
        cleaned.append(message)
    return cleaned


def trim_history(history: list[ModelMessage], max_messages: int) -> list[ModelMessage]:
    """Keep the most recent messages, starting on a user prompt.

    Cutting mid-exchange could leave a tool return without its tool call, which
    the model API rejects, so the window is advanced to the next user prompt.
    """
    if len(history) <= max_messages:
        return history
    window = history[-max_messages:]
    for index, message in enumerate(window):
        if isinstance(message, ModelRequest) and any(
            isinstance(part, UserPromptPart) for part in message.parts
        ):
            return window[index:]
    return []


async def load_history(redis: RedisClient, user_id: str) -> list[ModelMessage]:
    raw = await redis.read_value(_history_key(user_id))
    if not raw:
        return []
    try:
        return _strip_system_prompts(_adapter.validate_json(raw))
    except Exception:
        return []


async def save_history(
    redis: RedisClient, user_id: str, history: list[ModelMessage]
) -> None:
    serialized = _adapter.dump_json(history).decode()
    await redis.write_value(_history_key(user_id), serialized)


async def clear_history(redis: RedisClient, user_id: str) -> None:
    await redis.write_value(_history_key(user_id), "[]")
