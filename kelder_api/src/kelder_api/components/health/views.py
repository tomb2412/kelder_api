import logging
from fastapi import APIRouter

logger = logging.getLogger("core status")

router = APIRouter(tags = ["Health"])

@router.get("/health_check")
def read_root():
    logger.info("Health ok")
    logger.debug("Some debugging info")
    return True
