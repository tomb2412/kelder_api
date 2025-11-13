import logging
import subprocess
from http import HTTPStatus

from fastapi import APIRouter, HTTPException

logger = logging.getLogger("core status")

router = APIRouter(tags=["Health"])

SERVICES_TO_RESTART = ("worker", "redis", "kelder_api")


@router.get("/health_check")
def read_root():
    logger.debug("Health check success")
    return {"health": "True"}


@router.post("/restart", status_code=HTTPStatus.ACCEPTED)
def restart_container():
    """Restart the API, worker, and Redis containers."""
    logger.info("Restart endpoint requested for %s", SERVICES_TO_RESTART)

    try:
        subprocess.run(
            ["docker", "compose", "stop"],
            check=True,
        )
    except subprocess.CalledProcessError as exc:
        logger.exception("Failed to restart services: %s", SERVICES_TO_RESTART)
        raise HTTPException(
            status_code=HTTPStatus.INTERNAL_SERVER_ERROR,
            detail="Unable to restart services",
        ) from exc

    return {"status": "restarting", "services": list(SERVICES_TO_RESTART)}
