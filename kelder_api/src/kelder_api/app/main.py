import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

# Component import
from src.kelder_api.components.agentic_workflow.graph import AgentWorkflow
from src.kelder_api.components.compass_new.interface import CompassInterface
from src.kelder_api.components.gps_new.interface import GPSInterface
from src.kelder_api.components.log.service import LogTracker
from src.kelder_api.components.drift_calculator.serivce import DriftCalculator
from src.kelder_api.components.redis_client.redis_client import RedisClient
from src.kelder_api.components.velocity.service import VelocityCalculator
from src.kelder_api.configuration.logging_config import setup_logging

# Routes
from src.kelder_api.routes.bilge_depth.views import router as bilge_depth_route
from src.kelder_api.routes.compass.views import router as compass_router
from src.kelder_api.routes.gps.views import router as gps_route
from src.kelder_api.routes.gps.views import router_card
from src.kelder_api.routes.health.views import router as health_route
from src.kelder_api.routes.inference.views import router as agent_routes
from src.kelder_api.routes.log.views import router as log_route
from src.kelder_api.routes.passage_plan.views import router as passage_plan_routes
from src.kelder_api.routes.redis.views import router as redis_route
from src.kelder_api.routes.tidal_measurements.views import router as tidal_routes
from src.kelder_api.routes.velocity.views import router as velocity_route

# Allow requests from frontend's origin
origins = [
    "http://localhost:5173",  # Vite dev server
    "http://192.168.1.167:5173",
    "http://192.168.1.131:5173",
]

setup_logging(component="api")

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Initialising API stateful dependencies")
    redis_client = RedisClient()
    gps_interface = GPSInterface(redis_client)
    compass_interface = CompassInterface(redis_client)
    velocity_calculator = VelocityCalculator(
        gps_interface=gps_interface, redis_client=redis_client
    )
    log_tracker = LogTracker(
        gps_interface=gps_interface,
        redis_client=redis_client,
        velocity_calculator=velocity_calculator,
    )
    drift_calculator = DriftCalculator(
        redis_client=redis_client,
        velocity_calculator=velocity_calculator,
        compass_interface=compass_interface
    )

    app.state.redis_client = redis_client
    app.state.gps_interface = gps_interface
    app.state.compass_interface = compass_interface
    app.state.velocity_calculator = velocity_calculator
    app.state.log_tracker = log_tracker
    app.state.drift_calculator = drift_calculator
    app.state.agent_workflow = AgentWorkflow()
    logger.debug("API dependencies initialised and stored on app state")

    yield

    # Shutdown
    del app.state.redis_client
    del app.state.gps_interface
    del app.state.compass_interface
    del app.state.velocity_calculator
    del app.state.log_tracker
    del app.state.drift_calculator
    del app.state.agent_workflow
    logger.info("API stateful dependencies released during shutdown")


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
app.include_router(router_card)
app.include_router(bilge_depth_route)
app.include_router(compass_router)
app.include_router(velocity_route)
app.include_router(redis_route)
app.include_router(agent_routes)
app.include_router(passage_plan_routes)
app.include_router(tidal_routes)
app.include_router(log_route)
