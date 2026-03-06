import logging

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel

from src.kelder_api.app.getters import get_neo4j_client, get_redis_client
from src.kelder_api.components.agentic_workflow.agents.passage_planner import (
    passage_plan_agent,
)
from src.kelder_api.components.neo4j_client import Neo4jClient
from src.kelder_api.components.redis_client.redis_client import RedisClient
from src.kelder_api.components.redis_client.types import RedisSetNames

logger = logging.getLogger("api.routes.passage_plan")

router = APIRouter(tags=["Agentic"])


def get_redis_dep(request: Request) -> RedisClient:
    return get_redis_client(request.app)


def get_neo4j_dep(request: Request) -> Neo4jClient:
    return get_neo4j_client(request.app)


class PassagePlanRequest(BaseModel):
    from_mark: str
    to_mark: str


@router.get("/passage_plan")
async def GetPassagePlan(redis_client: RedisClient = Depends(get_redis_dep)):
    logger.info("Requesting a passage plan")
    try:
        plan = (await redis_client.read_set(RedisSetNames.PASSAGE_PLAN))[0]
    except IndexError:
        plan = ""

    return {"passage_plan": plan}


@router.post("/passage_plan")
async def PostPassagePlan(
    body: PassagePlanRequest,
    redis_client: RedisClient = Depends(get_redis_dep),
    neo4j_client: Neo4jClient = Depends(get_neo4j_dep),
):
    """Generate a passage plan between two named marks using graph-based A* routing."""
    logger.info("Generating passage plan from '%s' to '%s'", body.from_mark, body.to_mark)

    prompt = (
        f"Plan a passage from '{body.from_mark}' to '{body.to_mark}'. "
        f"Use the find_route_between_marks tool with name_from='{body.from_mark}' "
        f"and name_to='{body.to_mark}' to get the waypoints."
    )

    result = await passage_plan_agent.run(
        prompt,
        deps={
            "redis_client": redis_client,
            "neo4j_client": neo4j_client,
        },
    )

    return result.output
