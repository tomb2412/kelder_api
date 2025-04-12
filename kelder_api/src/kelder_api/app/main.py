import logging
from typing import Union

from fastapi import FastAPI

from src.kelder_api.components.health.views import router as health_route
from src.kelder_api.components.gps.views import router as gps_route

logger = logging.getLogger(__name__)
logging.basicConfig(filename="logs/kelder_api.log")

app = FastAPI()

app.include_router(health_route)
app.include_router(gps_route)