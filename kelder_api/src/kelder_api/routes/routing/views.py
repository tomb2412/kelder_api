import logging

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel

from src.kelder_api.app.getters import get_neo4j_client
from src.kelder_api.components.neo4j_client import Neo4jClient

logger = logging.getLogger("api.routes.routing")

router = APIRouter(prefix="/routing", tags=["Routing"])


def get_neo4j_dep(request: Request) -> Neo4jClient:
    return get_neo4j_client(request.app)


class RouteRequest(BaseModel):
    from_mark: str
    to_mark: str


@router.post("/a_star")
def get_a_star_route(
    body: RouteRequest,
    neo4j_client: Neo4jClient = Depends(get_neo4j_dep),
):
    """Run A* shortest path between two named marks and return the route."""
    logger.info("A* route requested from '%s' to '%s'", body.from_mark, body.to_mark)

    try:
        rows = neo4j_client.a_star_by_name(name_from=body.from_mark, name_to=body.to_mark)
    except Exception as e:
        logger.error("A* query failed: %s", e)
        raise HTTPException(status_code=500, detail=str(e))

    if not rows:
        raise HTTPException(
            status_code=404,
            detail=f"No route found between '{body.from_mark}' and '{body.to_mark}'.",
        )

    route_row = rows[0]
    path_nodes = route_row.get("path", [])

    waypoints = [
        {
            "name": node.get("name"),
            "latitude": node.get("latitude"),
            "longitude": node.get("longitude"),
        }
        for node in path_nodes
        if node.get("latitude") is not None and node.get("longitude") is not None
    ]

    return {
        "from_mark": route_row.get("sourceNodeName"),
        "to_mark": route_row.get("targetNodeName"),
        "total_cost_km": route_row.get("totalCost"),
        "waypoint_count": len(waypoints),
        "waypoints": waypoints,
    }
