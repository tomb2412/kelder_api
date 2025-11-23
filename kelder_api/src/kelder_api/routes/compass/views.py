import logging
from typing import Tuple

from fastapi import APIRouter, Depends, Request

from src.kelder_api.app.getters import get_compass_interface, get_velocity_calculator
from src.kelder_api.components.compass_new.interface import CompassInterface
from src.kelder_api.components.velocity.service import VelocityCalculator
from src.kelder_api.routes.compass.models import CompassCard

logger = logging.getLogger("api.routes.compass")

router = APIRouter(tags=["Core Sensing"])


def get_card_dependancies(
    request: Request,
) -> Tuple[CompassInterface, VelocityCalculator]:
    compass_interface = get_compass_interface(request.app)
    velocity_calculator = get_velocity_calculator(request.app)
    return compass_interface, velocity_calculator


@router.get("/compass_heading")
async def getCompassHeading(
    components: Tuple[CompassInterface, VelocityCalculator] = Depends(
        get_card_dependancies
    ),
) -> CompassCard:
    logger.info("Request recieved for compass heading and course over ground")

    compass_interface, velocity_calculator = components

    heading_history = await compass_interface.read_heading_history_length(
        length=1, active=True
    )
    heading = heading_history[0].heading if heading_history else None

    velocity = await velocity_calculator.read_velocity_latest(active=True)
    course_over_ground = velocity.course_over_ground

    return CompassCard(heading=heading, course_over_ground=course_over_ground)
