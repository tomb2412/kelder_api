import logging
from http import HTTPStatus

import requests
from fastapi import APIRouter, HTTPException

from src.kelder_api.configuration.settings import get_settings

logger = logging.getLogger("api.routes.health")

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
        raise HTTPException(500, f"Failed to call host restart API: {e}")
