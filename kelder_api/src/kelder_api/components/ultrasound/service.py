# hc_sr04_pi5.py
import logging

from gpiozero import DistanceSensor

# GPIO Pins
TRIG = 23
ECHO = 24

logger = logging.getLogger(__name__)


async def getBilgeDepth() -> float:
    distance = DistanceSensor(TRIG, ECHO)
    logging.debug("Succesfully read ultrasound distance: %s", distance)
    return {"bilge_depth": distance}
