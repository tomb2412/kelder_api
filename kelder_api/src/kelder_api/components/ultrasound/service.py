# hc_sr04_pi5.py
from gpiozero import DistanceSensor
import logging


# GPIO Pins
TRIG = 23
ECHO = 24

logger = logging.getLogger(__name__)


async def getBilgeDepth() -> float:
    distance = DistanceSensor(TRIG, ECHO)
    logging.debug("Succesfully read unltrasound distance: %s", distance)
    return {"bilge_depth": distance}
