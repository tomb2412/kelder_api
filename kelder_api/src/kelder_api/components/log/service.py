import logging
from datetime import datetime, timezone
from typing import Tuple

from src.kelder_api.components.velocity.service import VelocityCalculator
from src.kelder_api.components.velocity.models import GPSVelocity
from src.kelder_api.components.redis_client.redis_client import RedisClient
from src.kelder_api.components.gps_new.models import GPSRedisData
from src.kelder_api.components.gps_new.interface import GPSInterface
from src.kelder_api.configuration.settings import get_settings
from src.kelder_api.components.log.models import LegData, JourneyData
from src.kelder_api.components.log.exceptions import DataValidationError
from src.kelder_api.components.compass_new.models import CompassRedisData

logger = logging.getLogger(__name__)

class LogTracker:
    """
    Track the ships trip: departure and desination positions and times.
    Each leg positions and times.
    """

    def __init__(self, gps_interface: GPSInterface, redis_client: RedisClient, velocity_calculator: VelocityCalculator):
        self.gps_interface = gps_interface
        self.redis_client = redis_client
        self.velocity_calculator = velocity_calculator

        self.settings = get_settings().log_tracker

        # Variable to monitor the start of the jouney.
        self.start_journey = True
   

    async def _get_sensor_data(self) -> Tuple[GPSRedisData, GPSVelocity]:
        """Private method to retrieve the latest gps and velocity data for the trip."""
        gps_data =  await self.gps_interface.read_gps_latest(active=True)
        velocity_data = await self.velocity_calculator.read_velocity_latest(active=True)

        inter_measurement_latency = abs((gps_data.timestamp - velocity_data.timestamp.replace(tzinfo=timezone.utc)).total_seconds())
        overall_measurement_latency = abs((gps_data.timestamp - datetime.now(timezone.utc)).total_seconds())

        if inter_measurement_latency >= self.settings.time_window_length or overall_measurement_latency >= self.settings.time_window_length:
            message = (f"The time difference of the gps and velocity exceeded the allowed {self.settings.time_window_length} seconds:"
                       f"\nlatency between measurements: {inter_measurement_latency}"
                       f"\nlatency from measurements: {overall_measurement_latency}"
            )
            logger.error(message)
            raise DataValidationError(message)

        return gps_data, velocity_data
    
    async def increment_log(self):
        """
        Private method which uses class wide variables to incement:
        - the total journey time and distance
        - the start time and position the current tack began. -> for drift range
        """
        gps_data, velocity_data = await self._get_sensor_data()

        # If there is no log history at the start of the journey
        if self.start_journey:
            self.journey_data = JourneyData(
                timestamp = gps_data.timestamp,
                start_coords = [gps_data.latitude_nmea, gps_data.longitude_nmea],
                end_datetime = gps_data.timestamp,
                end_coords = [gps_data.latitude_nmea, gps_data.longitude_nmea],
            )
            self.leg_data = LegData(
                start_datetime = gps_data.timestamp,
                start_coords = [gps_data.latitude_nmea, gps_data.longitude_nmea],
                course_over_ground = velocity_data.course_over_ground
            )
            self.start_journey = False
        # If the journey has already started
        else:
            # Increment the journey data endpoints
            self.journey_data.end_datetime = gps_data.timestamp
            self.journey_data.end_coords = [gps_data.latitude_nmea, gps_data.longitude_nmea]

            # If the bearing has changes beyond the tolerance reset the leg
            if abs(self.leg_data.course_over_ground-velocity_data.course_over_ground) >= self.settings.tack_bearing_tolerance:
                self.leg_data = LegData(
                    start_datetime = gps_data.timestamp,
                    start_coords = [gps_data.latitude_nmea, gps_data.longitude_nmea],
                    course_over_ground = velocity_data.course_over_ground
                )
            # If the course has continues. Increment the latest cog
            else:
                self.leg_data.course_over_ground = velocity_data.course_over_ground
        
    async def finish_jouney(self):
        "Writes and clears the cached journey data."
        self.redis_client.write_set("LOG", self.journey_data)
        del(self.journey_data)
        del(self.leg_data)
        self.start_journey = True



