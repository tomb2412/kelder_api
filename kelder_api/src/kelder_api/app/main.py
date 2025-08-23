import logging
from typing import Union
from datetime import datetime

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.kelder_api.routes.health.views import router as health_route
from src.kelder_api.routes.gps.views import router as gps_route
from src.kelder_api.routes.bilge_depth.views import router as bilge_depth_route
from src.kelder_api.routes.compass.views import router as compass_router

# Allow requests from frontend's origin
origins = [
    "http://localhost:5173",  # Vite dev server
    "http://192.168.1.167:5173",
    "http://192.168.1.131:5173",
]

logging.basicConfig(
    filename=f"/app/logs/{datetime.now().strftime('%Y-%m-%d')}_kelder_api.log",
    encoding="utf-8",
    format="API - {levelname} - {asctime} - {message}",
    style="{",
    datefmt="%Y-%m-%d %H:%M:%S",
    level=logging.DEBUG,
)

logger = logging.getLogger(__name__)

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


@app.on_event("shutdown")
async def shutdown_event():
    """Clean up Redis connections on shutdown."""
    logger.info("Shutting down Redis client...")
    await redis_client.close()
