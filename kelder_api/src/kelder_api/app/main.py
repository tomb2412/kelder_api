import logging
from datetime import datetime

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.kelder_api.components.redis_client.redis_client import RedisClient
from src.kelder_api.components.gps_new.interface import GPSInterface
from src.kelder_api.components.compass_new.interface import CompassInterface
from src.kelder_api.components.velocity.service import VelocityCalculator
from src.kelder_api.routes.health.views import router as health_route
from src.kelder_api.routes.velocity.views import router as velocity_route
from src.kelder_api.routes.gps.views import router as gps_route
from src.kelder_api.routes.redis.views import router as redis_route
# from src.kelder_api.routes.bilge_depth.views import router as bilge_depth_route
from src.kelder_api.routes.compass.views import router as compass_router
from src.kelder_api.routes.inference.views import router as agent_routes
from src.kelder_api.routes.passage_plan.views import router as passage_plan_routes

# Allow requests from frontend's origin
origins = [
    "http://localhost:5173",  # Vite dev server
    "http://192.168.1.167:5173",
    "http://192.168.1.131:5173",
]

logging.basicConfig(
    # filename=f"/app/logs/{datetime.now().strftime('%Y-%m-%d')}_kelder_api.log",
    encoding="utf-8",
    format="API - {levelname} - {asctime} - {message}",
    style="{",
    datefmt="%Y-%m-%d %H:%M:%S",
    level=logging.DEBUG,
)

logger = logging.getLogger(__name__)

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    redis_client = RedisClient()
    gps_interface = GPSInterface(redis_client)
    compass_interface = CompassInterface(redis_client)

    app.state.redis_client = redis_client
    app.state.gps_interface = gps_interface
    app.state.compass_interface = compass_interface
    app.state.velocity_calculator = VelocityCalculator(
        gps_interface=gps_interface, redis_client=redis_client
    )

    yield  

    # Shutdown
    del app.state.redis_client
    del app.state.gps_interface
    del app.state.velocity_calculator

app = FastAPI(lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health_route)
app.include_router(gps_route)
# app.include_router(bilge_depth_route)
app.include_router(compass_router)
app.include_router(velocity_route)
app.include_router(redis_route)
app.include_router(agent_routes)
app.include_router(passage_plan_routes)
