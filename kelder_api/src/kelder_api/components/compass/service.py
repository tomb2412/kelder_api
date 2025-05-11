import time 
import math as m

import numpy as np
import board
import adafruit_lis2mdl.LIS2MDL

from src.kelder_api.components.compass.exceptions import I2CConnectionFailure


async def readCompassHeading():
    i2c = board.I2C()

    try:
        magnetometer = adafruit_lis2mdl.LIS2MDL(i2c)
    except ValueError:
        raise I2CConnectionFailure()

    magnetic_field_vector = np.array(magnetometer.magnetic)
    normalised_field_vector = magnetic_field_vector/np.linalg.norm(magnetic_field_vector)

    heading = m.degrees(m.atac2(normalised_field_vector[1],normalised_field_vector[0]))
    heading = round(heading)

    return(heading)