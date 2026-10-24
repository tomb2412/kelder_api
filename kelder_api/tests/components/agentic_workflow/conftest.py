from __future__ import annotations

from unittest.mock import AsyncMock

import pytest
from pydantic_ai import models

from src.kelder_api.components.redis_client.redis_client import RedisClient

# Fail loudly if a test would reach a real model provider.
models.ALLOW_MODEL_REQUESTS = False


@pytest.fixture()
def mock_redis_client() -> AsyncMock:
    client = AsyncMock(spec=RedisClient)
    client.read_value.return_value = None
    return client
