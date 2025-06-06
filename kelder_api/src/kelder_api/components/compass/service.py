import time
import logging
import math as m
from typing import List

import numpy as np
import board
import adafruit_lis2mdl

from src.kelder_api.components.compass.exceptions import I2CConnectionFailure
from src.kelder_api.components.compass.models import HeadingData

logger = logging.getLogger("Compass")

TACKING_THRESHOLD = 30  # Heading change to define a tack


class CompassSensor:
    """
    API for compass sensing and processing methods
    """

    @classmethod
    async def readCompassHeading(self) -> int:
        """
        Accesses I2C port and reads in a compass heading.

        Accessed by the backgroun worker
        """
        i2c = board.I2C()

        try:
            magnetometer = adafruit_lis2mdl.LIS2MDL(i2c)
        except ValueError:
            raise I2CConnectionFailure

        magnetic_field_vector = np.array(magnetometer.magnetic)
        normalised_field_vector = magnetic_field_vector / np.linalg.norm(
            magnetic_field_vector
        )

        heading = m.degrees(
            m.atan2(normalised_field_vector[1], normalised_field_vector[0])
        )
        heading = round(heading)

        if heading < 0:
            heading += 360

        return heading

    @classmethod
    def tackDetection(self, heading_history: List[str]) -> HeadingData:
        """
        Identifies changes in tack from the heading history.
        Calculates average heading from the compass redis history

        Returns:
            cleaned heading data

        Accessed by background worker
        """

        heading_data = HeadingData(heading_history=heading_history)

        # Nested list structure, first element - timestamp, second element heading
        history_length = len(heading_data.heading_measurements)
        heading_change = 0
        tack_index = 0

        # redis history added by head, so loop increases further back in time.
        while heading_change <= TACKING_THRESHOLD and (tack_index + 1) < history_length:
            heading_change = abs(
                (
                    heading_data.heading_measurements[tack_index]
                    - heading_data.heading_measurements[tack_index + 1]
                    + 180
                )
                % 360
                - 180
            )
            tack_index += 1

        if tack_index + 1 == history_length:
            logger.info(
                "No heading exceeds tacking threshold. Continuing along the current tack"
            )

        elif tack_index + 1 <= history_length:
            logging.info(
                "Tack detected at timestamp: %s",
                {heading_data.heading_timestamps[tack_index]},
            )

        # Recalculate the heading properties
        heading_data = HeadingData(heading_history=heading_history[0:tack_index])
        return heading_data, tack_index

    @classmethod
    def driftCalculation(self, heading, gps_data):
        pass
