import time
import logging
import math as m

import numpy as np
import board
import adafruit_lis2mdl

from src.kelder_api.components.compass.exceptions import I2CConnectionFailure

logger = logging.getLogger("Compass")


async def readCompassHeading() -> int:
    i2c = board.I2C()

    try:
        magnetometer = adafruit_lis2mdl.LIS2MDL(i2c)
    except ValueError:
        raise I2CConnectionFailure

    magnetic_field_vector = np.array(magnetometer.magnetic)
    normalised_field_vector = magnetic_field_vector / np.linalg.norm(
        magnetic_field_vector
    )

    heading = m.degrees(m.atan2(normalised_field_vector[1], normalised_field_vector[0]))
    heading = round(heading)

    if heading < 0:
        heading += 360

    return heading
