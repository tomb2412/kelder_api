import logging
import math
from datetime import datetime, timedelta, timezone
from statistics import StatisticsError, fmean
from typing import Tuple

from src.kelder_api.components.compass_new.interface import CompassInterface
from src.kelder_api.components.drift_calculator.models import DriftData
from src.kelder_api.components.drift_calculator.utils import bearing_angle_difference
from src.kelder_api.components.redis_client.redis_client import RedisClient
from src.kelder_api.components.velocity.service import VelocityCalculator
from src.kelder_api.configuration.logging_config import setup_logging
from src.kelder_api.configuration.settings import get_settings

"""
NOTE:

Few approaches here perhaps worth building in and configuring
- total drift on tack - Requires a tack detector
- Instantainuous velocity measurement - Requires smoothing compass data
  (and maybe velocity)
- Incorperate water speed - gives a true drift quantity.
"""

# Ensure all measurements are UTC so timedeltas capture the correct values

setup_logging(component="drift calculator")
logger = logging.getLogger(__name__)

# TODO: make the active = True consistant across the read set methods


class DriftCalculator:
    """Calculator which processes the GPS velocity and compass heading."""

    def __init__(
        self,
        redis_client: RedisClient,
        velocity_calculator: VelocityCalculator,
        compass_interface: CompassInterface,
    ):
        self.compass_interface = compass_interface
        self.redis_client = redis_client
        self.velocity_calculator = velocity_calculator

        self.settings = get_settings().drift

    async def instantaneous_drift_calculator(
        self, datetime_now: datetime | None = None
    ) -> None:
        sog_avg, cog_avg = await self._calculate_avg_velocity(
            end_datetime=datetime_now
        )
        heading_avg, end_datetime  = await self._calculate_avg_heading(end_datetime=datetime_now)

        if sog_avg is not None and cog_avg is not None and heading_avg is not None:
            drift_angle = bearing_angle_difference(heading_avg, cog_avg)
            drift_speed = round(sog_avg * abs(math.sin(math.radians(drift_angle))),1)
        else:
            drift_speed = None
        logger.debug(f"The final drift is: {DriftData(timestamp=end_datetime, drift_speed=drift_speed, drift_angle = drift_angle)}")
        await self.write_drift(DriftData(timestamp=end_datetime, drift_speed=drift_speed, drift_angle = drift_angle))

    async def _calculate_avg_velocity(
        self, end_datetime: datetime | None = None
    ) -> Tuple[float | None]:
        if end_datetime is None:
            end_datetime = datetime.now(timezone.utc).replace(microsecond=0)
        start_datetime = end_datetime - timedelta(
            seconds=self.settings.instantaneous_history_period
        )
        velocity_history = await self.velocity_calculator.read_velocity_timeseries(
            end_datetime=end_datetime,
            start_datetime=start_datetime,
            active=True
        )
        logger.debug(f"Requesting the velocity timeseries. From: {start_datetime}-{end_datetime}. Got length: {len(velocity_history)}")
        # TODO: catch no data
        try:
            sog_avg = fmean(
                map(lambda measurement: measurement.speed_over_ground, velocity_history)
            )
            cog_avg = fmean(
                map(
                    lambda measurement: measurement.course_over_ground, velocity_history
                )
            )
        except StatisticsError:
            sog_avg = None
            cog_avg = None
            logger.error(
                "No velocity data available in the last"
                f"{self.settings.instantaneous_history_period}"
            )
        logger.debug(f"The vecocity average: {sog_avg}, {cog_avg}")
        return sog_avg, cog_avg

    async def _calculate_avg_heading(self, end_datetime: datetime | None = None) -> float | None:
        if end_datetime is None:
            end_datetime = datetime.now(timezone.utc).replace(microsecond=0)
        start_datetime = end_datetime - timedelta(
            seconds=self.settings.instantaneous_history_period
        )
        compass_history = await self.compass_interface.read_heading_history_timeseries(
            end_datetime=end_datetime,
            start_datetime=start_datetime,
            active=True
        )
        logger.debug(f"Requesting the compass timeseries. From: {start_datetime}-{end_datetime}. Got length: {len(compass_history)}")

        try:
            heading_avg = fmean(
                map(lambda measurement: measurement.heading, compass_history)
            )
        except StatisticsError:
            heading_avg = None
            logger.error(
                f"No compass data available in the last {
                    self.settings.instantaneous_history_period
                }"
            )
        logger.debug(f"The heading average: {heading_avg}")
        return heading_avg, end_datetime

    async def write_drift(self, drift_data: DriftData) -> None:
        logger.info("Writing the drift data")
        await self.redis_client.write_set("DRIFT", drift_data)

    async def read_drift_latest(self, active: bool = False) -> DriftData:
        logger.debug("Reading the latest drift")
        drift_history = await self.redis_client.read_set("DRIFT")
        try:
            if active:
                return DriftData(
                    **[
                        measurement
                        for measurement in drift_history
                        if measurement["drift_speed"] is not None
                    ][0]
                )
            else:
                return DriftData(**drift_history[0])
        except IndexError:
            logger.debug("No drift history available")
            return DriftData(timestamp=datetime.now(timezone.utc), drift_speed=None)
