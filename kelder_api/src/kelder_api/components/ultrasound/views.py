import logging
from src.kelder_api.components.ultrasound.service import getBilgeDepth as getBilgeDepthService
from random import randint 

from fastapi import APIRouter

router = APIRouter(tags=["Core Sensing"])

logger = logging.getLogger(__name__)

@router.get("/bilge_depth")
async def getBilgeDepth():
    logger.info("Requesting Bilge Depth")
    return await getBilgeDepthService()