import logging
from typing import Union
from datetime import datetime

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.kelder_api.components.health.views import router as health_route
from src.kelder_api.components.gps.views import router as gps_route
from src.kelder_api.components.ultrasound.views import router as bilge_depth_route
from src.kelder_api.components.compass.views import router as compass_router

# Allow requests from frontend's origin
origins = [
    "http://localhost:5173",  # Vite dev server
]

logger = logging.getLogger(__name__)
logging.basicConfig(
    filename=f"/app/logs/{datetime.now().strftime('%Y-%m-%d')}_kelder_api.log",
    encoding="utf-8",
    format="API - {levelname} - {asctime} - {message}",
    style="{",
    datefmt="%Y-%m-%d %H:%M:%S",
    level=logging.DEBUG,
)

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health_route)
app.include_router(gps_route)
app.include_router(bilge_depth_route)
app.include_router(compass_router)
