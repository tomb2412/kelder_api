import logging
import subprocess
from http import HTTPStatus

from fastapi import APIRouter

logger = logging.getLogger("core status")

router = APIRouter(tags=["Health"])


@router.get("/health_check")
def read_root():
    logger.debug("Health check success")
    return {"health": "True"}


@router.post("/restart", status_code=HTTPStatus.ACCEPTED)
def restart_container():
    """Restart a single Docker container using the engine's Python SDK."""
    logger.info("Restart endpoint requested")
    subprocess.run(["docker", "compose", "restart"])
