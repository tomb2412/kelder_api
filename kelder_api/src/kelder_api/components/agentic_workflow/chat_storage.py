from pydantic import TypeAdapter
from pydantic_ai.messages import ModelMessage

from src.kelder_api.components.redis_client.redis_client import RedisClient

_adapter = TypeAdapter(list[ModelMessage])


def _history_key(user_id: str) -> str:
    return f"chat:{user_id}:history"


async def load_history(redis: RedisClient, user_id: str) -> list[ModelMessage]:
    raw = await redis.read_value(_history_key(user_id))
    if not raw:
        return []
    try:
        return _adapter.validate_json(raw)
    except Exception:
        return []


async def save_history(
    redis: RedisClient, user_id: str, history: list[ModelMessage]
) -> None:
    serialized = _adapter.dump_json(history).decode()
    await redis.write_value(_history_key(user_id), serialized)


async def clear_history(redis: RedisClient, user_id: str) -> None:
    await redis.write_value(_history_key(user_id), "[]")
