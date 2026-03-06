from fastapi import FastAPI

from src.kelder_api.components.background_orchestrator.orchestrator import (
    BackgroundTaskManager,
)
from src.kelder_api.components.compass_new.interface import CompassInterface
from src.kelder_api.components.db_manager.service import DBManager
from src.kelder_api.components.drift_calculator.serivce import DriftCalculator
from src.kelder_api.components.gps_new.interface import GPSInterface
from src.kelder_api.components.log.service import LogTracker
from src.kelder_api.components.neo4j_client import Neo4jClient
from src.kelder_api.components.redis_client.redis_client import RedisClient
from src.kelder_api.components.velocity.service import VelocityCalculator


def get_redis_client(app: FastAPI) -> RedisClient:
    return app.state.redis_client


def get_gps_interface(app: FastAPI) -> GPSInterface:
    return app.state.gps_interface


def get_compass_interface(app: FastAPI) -> CompassInterface:
    return app.state.compass_interface


def get_velocity_calculator(app: FastAPI) -> VelocityCalculator:
    return app.state.velocity_calculator


def get_db_manager(app: FastAPI) -> DBManager:
    return app.state.db_manager


def get_log_tracker(app: FastAPI) -> LogTracker:
    return app.state.log_tracker


def get_drift_calculator(app: FastAPI) -> DriftCalculator:
    return app.state.drift_calculator


def get_orchestrator(app: FastAPI) -> BackgroundTaskManager:
    return app.state.background_orchestrator


def get_neo4j_client(app: FastAPI) -> Neo4jClient | None:
    return app.state.neo4j_client
