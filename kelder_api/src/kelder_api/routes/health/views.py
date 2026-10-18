from src.kelder_api.configuration.logging_controller import get_logger
from http import HTTPStatus

import requests
from fastapi import APIRouter, HTTPException

from src.kelder_api.configuration.settings import get_settings

logger = get_logger(__name__, "outes.health")

router = APIRouter(tags=["Health"])

host_api_settings = get_settings().host_api


@router.get("/health_check")
def read_root():
    logger.debug("Health check success")
    return {"health": "True"}


@router.post("/restart", status_code=HTTPStatus.ACCEPTED)
def restart_container():
    """Restart the API, worker, and Redis containers."""
    logger.info("Restart endpoint requested")

    try:
        r = requests.post(
            f"{host_api_settings.restart_url}/restart",
            auth=(host_api_settings.username, host_api_settings.password),
            timeout=10,
        )
        r.raise_for_status()
        return {"status": "ok", "output": r.text}
    except Exception as e:
        logger.error(f"Failed to call host restart API: {e}")
        raise HTTPException(500, f"Failed to call host restart API: {e}")
