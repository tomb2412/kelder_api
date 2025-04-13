import logging
from typing import Union
from datetime import datetime

from fastapi import FastAPI

from src.kelder_api.components.health.views import router as health_route
from src.kelder_api.components.gps.views import router as gps_route

logger = logging.getLogger(__name__)
logging.basicConfig(
    filename=f"src/kelder_api/logs/{datetime.now().strftime("%Y-%m-%d")}_kelder_api.log",
    encoding = "utf-8",
    format="{levelname} - {asctime} - {message}",
    style = "{",
    datefmt = "%Y-%m-%d %H:%M:%S",
    level=logging.DEBUG
)

app = FastAPI()

app.include_router(health_route)
app.include_router(gps_route)