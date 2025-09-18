from fastapi import FastAPI

from src.kelder_api.components.redis_client.redis_client import RedisClient
from src.kelder_api.components.gps_new.interface import GPSInterface
from src.kelder_api.components.compass_new.interface import CompassInterface
from src.kelder_api.components.velocity.service import VelocityCalculator
from src.kelder_api.components.log.service import LogTracker


def get_redis_client(app: FastAPI) -> RedisClient:
    return app.state.redis_client


def get_gps_interface(app: FastAPI) -> GPSInterface:
    return app.state.gps_interface


def get_compass_interface(app: FastAPI) -> CompassInterface:
    return app.state.compass_interface


def get_velocity_calculator(app: FastAPI) -> VelocityCalculator:
    return app.state.velocity_calculator


def get_log_tracker(app: FastAPI) -> LogTracker:
    return app.state.log_tracker
