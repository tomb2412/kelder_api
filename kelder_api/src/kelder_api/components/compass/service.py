import logging
import math as m
import time
from typing import List, Tuple

import adafruit_lis2mdl
import board
import numpy as np

from src.kelder_api.components.compass.exceptions import I2CConnectionFailure
from src.kelder_api.components.compass.models import HeadingData
from src.kelder_api.components.gps.utils import (
    convert_to_decimal_degrees,
    haversine,
    time_difference_seconds,
)

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
    def tackDetection(self, heading_history: HeadingData) -> Tuple[HeadingData, int]:
        """
        Identifies changes in tack from the heading history.
        Calculates average heading from the compass redis history

        Returns:
            cleaned heading data

        Accessed by background worker
        """

        # Nested list structure, first element - timestamp, second element heading
        history_length = len(heading_data.heading_measurements)
        heading_change = 0
        tack_index = 0

        # redis history added by head, so loop iterates further back in time.
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
    def driftCalculation(self, heading: HeadingData):
        """
        Public method to calculate the magnitude of speed perpendicular to the direction of the boat.

        is speed through water, the dot product? - Not with flow

        Arbitrary coordinate system. Intuatively follows current and boat speed.
        Here current data not available so defined as perpendicular to boat speed

        # Calculate the opposite vector
        #  - Calculate SOG heading.
        #  - Calculate theta - subtract angle between HDG and SOG.
        #  - Magnitude is SOG*sin(theta)
        #  - Direction is perpendicular to HDG
        #  - Capture theata sign for direction
        """

        # First calculate the speed over groud direction
        delta_latitude = convert_to_decimal_degrees(
            heading.end_of_tack_latitude
        ) - convert_to_decimal_degrees(heading.start_of_tack_latitude)
        delta_longitude = convert_to_decimal_degrees(
            heading.end_of_tack_longitude
        ) - convert_to_decimal_degrees(heading.start_of_tack_longitude)

        # lat long mag is in DD.DDDD
        lat_long_magnitude = m.sqrt(delta_latitude**2 + delta_longitude**2)
        # sog mag is nautical miles
        distance_over_ground = haversine(
            heading.start_of_tack_latitude,
            heading.end_of_tack_latitude,
            heading.start_of_tack_longitude,
            heading.end_of_tack_longitude,
        )
        time_difference = time_difference_seconds(
            heading.heading_timestamps[0], heading.heading_timestamps[-1]
        )
        sog_magnitude = distance_over_ground / time_difference

        # dot with (0,1) and divide by magnitude
        speed_over_ground_heading = m.acos(delta_longitude / lat_long_magnitude)

        theata_radians = speed_over_ground_heading - m.radians(heading.average_heading)
        drift_magnitude = sog_magnitude * m.sin(theata_radians)

        drift_bearing = (
            heading.average_heading - 90
            if m.copysign(1, theata_radians)
            else heading.average_heading + 90
        )

        logger.info("Calculated drift and bearing successfully")
        logger.debug(f"""
Drift parameters:
    - heading.end_of_tack_latitude: {heading.end_of_tack_latitude}
    - heading.start_of_tack_latitude: {heading.start_of_tack_latitude}
    - heading.end_of_tack_longitude: {heading.end_of_tack_longitude}
    - heading.start_of_tack_longitude: {heading.start_of_tack_longitude}
    - lat_long_magnitude: {lat_long_magnitude}
    - time_difference: {time_difference}
    - sog_magnitude: {sog_magnitude}
    - speed_over_ground_heading: {speed_over_ground_heading}
    - theata_radians: {theata_radians}
    - drift_magnitude: {drift_magnitude}
    - drift_bearing: {drift_bearing}
        """)

        return drift_magnitude, drift_bearing
