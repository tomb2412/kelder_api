import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

# Component import
from src.kelder_api.components.agentic_workflow.graph import AgentWorkflow
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
from src.kelder_api.configuration.logging_config import setup_logging
from src.kelder_api.configuration.settings import get_settings

# Routes
from src.kelder_api.routes.bilge_depth.views import router as bilge_depth_route
from src.kelder_api.routes.compass.views import router as compass_router
from src.kelder_api.routes.db_manager.views import router as db_manager_route
from src.kelder_api.routes.gps.views import router as gps_route
from src.kelder_api.routes.gps.views import router_card
from src.kelder_api.routes.health.views import router as health_route
from src.kelder_api.routes.inference.views import router as agent_routes
from src.kelder_api.routes.log.views import router as log_route
from src.kelder_api.routes.passage_plan.views import router as passage_plan_routes
from src.kelder_api.routes.routing.views import router as routing_routes
from src.kelder_api.routes.redis.views import router as redis_route
from src.kelder_api.routes.ships_status.views import router as ships_status_route
from src.kelder_api.routes.tidal_measurements.views import router as tidal_routes
from src.kelder_api.routes.velocity.views import router as velocity_route

# Explicit production origin
PRODUCTION_ORIGIN = "https://www.sailkelder.uk"

# Regex covers: localhost, any 192.168.x.x, any 172.x.x.x (Docker subnets),
# and any 10.x.x.x — with any port — over http or https.
LOCAL_ORIGIN_REGEX = (
    r"https?://(localhost|192\.168\.\d{1,3}\.\d{1,3}"
    r"|172\.\d{1,3}\.\d{1,3}\.\d{1,3}"
    r"|10\.\d{1,3}\.\d{1,3}\.\d{1,3})(:\d+)?"
)

setup_logging(component="api")

logger = logging.getLogger("api")


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Initialising API stateful dependencies")
    settings = get_settings()
    try:
        neo4j_client = Neo4jClient(
            uri=settings.neo4j.neo4j_uri,
            username=settings.neo4j.neo4j_username,
            password=settings.neo4j.neo4j_password,
            auth_disabled=settings.neo4j.neo4j_auth_disabled,
        )
        logger.info("Neo4j client initialised (%s)", settings.neo4j.neo4j_uri)
    except Exception as exc:
        neo4j_client = None
        logger.warning(
            "Neo4j unavailable on startup — routing endpoints disabled: %s", exc
        )
    redis_client = RedisClient()
    gps_interface = GPSInterface(redis_client)
    compass_interface = CompassInterface(redis_client)
    velocity_calculator = VelocityCalculator(
        gps_interface=gps_interface, redis_client=redis_client
    )
    db_manager = DBManager()
    log_tracker = LogTracker(
        gps_interface=gps_interface,
        redis_client=redis_client,
        velocity_calculator=velocity_calculator,
        db_manager=db_manager,
    )
    drift_calculator = DriftCalculator(
        redis_client=redis_client,
        velocity_calculator=velocity_calculator,
        compass_interface=compass_interface,
    )
    background_orchestrator = BackgroundTaskManager()

    app.state.neo4j_client = neo4j_client
    app.state.redis_client = redis_client
    app.state.gps_interface = gps_interface
    app.state.compass_interface = compass_interface
    app.state.velocity_calculator = velocity_calculator
    app.state.db_manager = db_manager
    app.state.log_tracker = log_tracker
    app.state.drift_calculator = drift_calculator
    app.state.agent_workflow = AgentWorkflow(redis_client, neo4j_client=neo4j_client)
    app.state.background_orchestrator = background_orchestrator
    logger.debug("API dependencies initialised and stored on app state")

    yield

    # Shutdown
    if app.state.neo4j_client is not None:
        app.state.neo4j_client.close()
    del app.state.neo4j_client
    del app.state.redis_client
    del app.state.gps_interface
    del app.state.compass_interface
    del app.state.velocity_calculator
    del app.state.log_tracker
    del app.state.db_manager
    del app.state.drift_calculator
    del app.state.agent_workflow
    del app.state.background_orchestrator
    logger.info("API stateful dependencies released during shutdown")


app = FastAPI(lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[PRODUCTION_ORIGIN],
    allow_origin_regex=LOCAL_ORIGIN_REGEX,
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
app.include_router(db_manager_route)
app.include_router(agent_routes)
app.include_router(passage_plan_routes)
app.include_router(routing_routes)
app.include_router(tidal_routes)
app.include_router(log_route)
app.include_router(ships_status_route)
