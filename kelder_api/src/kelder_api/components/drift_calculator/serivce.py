from datetime import datetime, timezone, timedelta
import logging

from statistics import fmean
import math

from src.kelder_api.components.compass_new.interface import CompassInterface
from src.kelder_api.components.redis_client.redis_client import RedisClient
from src.kelder_api.components.velocity.service import VelocityCalculator
from src.kelder_api.configuration.logging_config import setup_logging
from src.kelder_api.configuration.settings import get_settings
from src.kelder_api.components.drift_calculator.utils import bearing_angle_difference
from src.kelder_api.components.drift_calculator.models import DriftData


"""
NOTE:

Few approaches here perhaps worth building in and configuring
- total drift on tack - Requires a tack detector
- Instantainuous velocity measurement - Requires smoothing compass data (and maybe velocity)
- Incorperate water speed - gives a true drift quantity.
"""

# Validate that all measurements are UTC and the timedeltas will always capture the correct values

setup_logging(component="drift calculator")
logger = logging.getLogger(__name__)

# TODO: make the active = True consistant across the read set methods


class DriftCalculator:
    """Calculator which processes the GPS velocity and compass heading."""

    def __init__(
        self,
        redis_client: RedisClient,
        velocity_calculator: VelocityCalculator,
        compass_interface: CompassInterface
    ):
        self.compass_interface = compass_interface
        self.redis_client = redis_client
        self.velocity_calculator = velocity_calculator

        self.settings = get_settings().drift
    
    def instantaneous_drift_calculator(self) -> DriftData:
        end_datetime = datetime.now(timezone.utc)
        start_datetime = end_datetime - timedelta(seconds=self.settings.instantaneous_history_period)

        sog_avg, cog_avg = self._calculate_avg_velocity(start_datetime=start_datetime)
        heading_avg = self._calculate_avg_heading(start_datetime=start_datetime)

        drift_angle = bearing_angle_difference(heading_avg, cog_avg)
        drift_speed = sog_avg*math.sin(drift_angle)

        return DriftData(
            timestamp = end_datetime,
            drift_speed = drift_speed
        )

    def _calculate_avg_velocity(self, start_datetime: datetime):
        velocity_history = self.velocity_calculator.read_heading_history_timeseries(
            start_datetime = start_datetime,
            active = True
        )

        sog_avg = fmean(map(lambda measurement: measurement.speed_over_ground, velocity_history))
        cog_avg = fmean(map(lambda measurement: measurement.course_over_ground, velocity_history))

        return sog_avg, cog_avg

    def _calculate_avg_heading(self, start_datetime: datetime):
        compass_history = self.compass_interface.read_heading_history_timeseries(
            start_datetime=start_datetime,
            active=True
        )

        heading_avg = fmean(map(lambda measurement: measurement.heading, compass_history))
    
        return heading_avg

    async def write_drift(self, drift_data: DriftData) -> None:
        logger.debug("Writing the drift data")
        await self.redis_client.write_set("DRIFT", drift_data)

    async def read_drift_latest(self, active: bool = False) -> DriftData:
        logger.debug("Reading the latest drift")
        drift_history = await self.redis_client.read_set("DRIFT")
        try:
            if active:
                return DriftData(
                    **[
                        measurement for measurement in drift_history if measurement["drift_speed"] is not None
                    ][0]
                )
            else:
                return DriftData(**drift_history[0])
        except IndexError:
            logger.debug("No drift history available")
            return DriftData(timestamp=datetime.now(timezone.utc), drift_speed = None)
        