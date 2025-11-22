import logging

from fastapi import APIRouter, Depends, HTTPException, Request

from src.kelder_api.app.getters import get_orchestrator
from src.kelder_api.components.background_orchestrator.orchestrator import (
    BackgroundTaskManager,
)

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Ships status"])


def get_dependancy(request: Request) -> BackgroundTaskManager:
    return get_orchestrator(request.app)


@router.get("/vessel_state")
async def get_vessel_state(
    orchestrator: BackgroundTaskManager = Depends(get_dependancy),
) -> dict[str, str]:
    vessel_state = await orchestrator.read_vessel_state()
    if vessel_state is None:
        raise HTTPException(status_code=404, detail="No vessel state data available")
    return {"vessel_state": vessel_state.vessel_state.value}
