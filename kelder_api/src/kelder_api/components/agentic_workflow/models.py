from dataclasses import dataclass
from typing import Any, Awaitable, Callable

from src.kelder_api.components.compass_new.interface import CompassInterface
from src.kelder_api.components.db_manager.service import DBManager
from src.kelder_api.components.drift_calculator.serivce import DriftCalculator
from src.kelder_api.components.gps_new.interface import GPSInterface
from src.kelder_api.components.log.service import LogTracker
from src.kelder_api.components.neo4j_client import Neo4jClient
from src.kelder_api.components.redis_client.redis_client import RedisClient
from src.kelder_api.components.velocity.service import VelocityCalculator


@dataclass
class VesselServices:
    """The app's live sensor readers, shared with the chatbot's status tools."""

    gps_interface: GPSInterface
    velocity_calculator: VelocityCalculator
    compass_interface: CompassInterface
    log_tracker: LogTracker
    drift_calculator: DriftCalculator


@dataclass
class ChatDeps:
    """Dependencies shared by the chatbot and the specialist agents it calls."""

    redis_client: RedisClient
    neo4j_client: Neo4jClient | None = None
    db_manager: DBManager | None = None
    vessel: VesselServices | None = None
    marks_data: list[dict[str, Any]] | None = None
    marks_index: Any = None
    progress_callback: Callable[[str], Awaitable[None]] | None = None

    async def notify(self, message: str) -> None:
        """Report what the assistant is doing to the streaming client."""
        if self.progress_callback is not None:
            await self.progress_callback(message)

    def passage_planner_deps(self) -> dict[str, Any]:
        return {
            "redis_client": self.redis_client,
            "neo4j_client": self.neo4j_client,
            "marks_index": self.marks_index,
            "marks_data": self.marks_data,
        }
