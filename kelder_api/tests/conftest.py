import math
from collections import defaultdict
from dataclasses import dataclass
from typing import Any, Dict, Iterable, Tuple

import pytest

from src.kelder_api.components.redis_client import redis_client as redis_client_module


class _InMemoryRedisServer:
    def __init__(self) -> None:
        self._strings: Dict[str, str] = {}
        self._sorted_sets: Dict[str, Dict[str, float]] = defaultdict(dict)
        self._hashes: Dict[str, Dict[str, Any]] = defaultdict(dict)

    def reset(self) -> None:
        self._strings.clear()
        self._sorted_sets.clear()
        self._hashes.clear()


@dataclass
class _FakeConnectionPool:
    server: _InMemoryRedisServer
    disconnected: bool = False

    async def disconnect(self) -> None:
        self.disconnected = True


class _FakeRedis:
    def __init__(
        self, connection_pool: _FakeConnectionPool | None = None, **_: Any
    ) -> None:
        if connection_pool is None:
            raise ValueError("connection_pool must be provided for FakeRedis")
        self._server = connection_pool.server

    async def close(self) -> None:
        return None

    async def ping(self) -> bool:
        return True

    async def set(self, key: str, value: str) -> None:
        self._server._strings[key] = value

    async def get(self, key: str) -> str | None:
        return self._server._strings.get(key)

    async def zadd(self, key: str, mapping: Dict[str, float]) -> None:
        sorted_set = self._server._sorted_sets[key]
        sorted_set.update(mapping)

    async def zrevrangebyscore(
        self,
        key: str,
        max: float | str = "+inf",
        min: float | str = "-inf",
        withscores: bool = False,
    ) -> Iterable[Tuple[str, float]]:
        sorted_set = self._server._sorted_sets.get(key, {})
        max_score = _normalise_score(max, default=math.inf)
        min_score = _normalise_score(min, default=-math.inf)

        items = [
            (member, score)
            for member, score in sorted_set.items()
            if min_score <= score <= max_score
        ]
        items.sort(key=lambda item: item[1], reverse=True)
        if withscores:
            return items
        return [member for member, _ in items]

    async def hset(self, key: str, mapping: Dict[str, Any]) -> None:
        self._server._hashes[key].update(mapping)

    async def hgetall(self, key: str) -> Dict[str, Any]:
        return dict(self._server._hashes.get(key, {}))


def _normalise_score(value: float | str, default: float) -> float:
    if isinstance(value, (int, float)):
        return float(value)
    if value in {"+inf", "+infinity", "inf", "infinity"}:
        return math.inf
    if value in {"-inf", "-infinity"}:
        return -math.inf
    return float(value)


@pytest.fixture()
def redis_server(monkeypatch: pytest.MonkeyPatch) -> _InMemoryRedisServer:
    server = _InMemoryRedisServer()

    def _connection_pool_factory(*args: Any, **kwargs: Any) -> _FakeConnectionPool:
        return _FakeConnectionPool(server=server)

    def _redis_factory(*args: Any, **kwargs: Any) -> _FakeRedis:
        connection_pool = kwargs.get("connection_pool")
        if connection_pool is None and args:
            connection_pool = args[0]
        return _FakeRedis(connection_pool=connection_pool)

    monkeypatch.setattr(redis_client_module, "ConnectionPool", _connection_pool_factory)
    monkeypatch.setattr(redis_client_module, "Redis", _redis_factory)

    return server
