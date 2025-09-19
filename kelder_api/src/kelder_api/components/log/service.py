import logging
from datetime import datetime, timezone
from typing import Tuple

from pydantic import ValidationError

from src.kelder_api.components.gps_new.interface import GPSInterface
from src.kelder_api.components.gps_new.models import GPSRedisData
from src.kelder_api.components.log.exceptions import DataValidationError
from src.kelder_api.components.log.models import JourneyData, LegData
from src.kelder_api.components.redis_client.redis_client import RedisClient
from src.kelder_api.components.velocity.models import GPSVelocity
from src.kelder_api.components.velocity.service import VelocityCalculator
from src.kelder_api.configuration.settings import get_settings

logger = logging.getLogger(__name__)


class LogTracker:
    """
    Track the ships trip: departure and desination positions and times.
    Each leg positions and times.
    """

    def __init__(
        self,
        gps_interface: GPSInterface,
        redis_client: RedisClient,
        velocity_calculator: VelocityCalculator,
    ):
        self.gps_interface = gps_interface
        self.redis_client = redis_client
        self.velocity_calculator = velocity_calculator

        self.settings = get_settings().log_tracker

        # Variable to monitor the start of the jouney.
        self.start_journey = True

    async def _get_sensor_data(
        self, now: datetime | None = None
    ) -> Tuple[GPSRedisData, GPSVelocity]:
        """Private method to retrieve the latest gps and velocity data for the trip."""
        if now is None:
            now = datetime.now(timezone.utc)

        try:
            gps_data = await self.gps_interface.read_gps_latest(active=True)
            velocity_data = await self.velocity_calculator.read_velocity_latest(
                active=True
            )

        except IndexError:
            message = "No data in gps and velocity dbs"
            logger.error(message)
            raise DataValidationError(message)

        inter_measurement_latency = abs(
            (
                gps_data.timestamp
                - velocity_data.timestamp.replace(tzinfo=timezone.utc)
            ).total_seconds()
        )
        overall_measurement_latency = abs((gps_data.timestamp - now).total_seconds())

        if (
            inter_measurement_latency >= self.settings.time_window_length
            or overall_measurement_latency >= self.settings.time_window_length
        ):
            message = (
                f"The time difference of the gps and velocity exceeded the allowed {self.settings.time_window_length} seconds:"
                f"\nlatency between measurements: {inter_measurement_latency}"
                f"\nlatency from measurements: {overall_measurement_latency}"
            )
            logger.error(message)
            raise DataValidationError(message)

        return gps_data, velocity_data

    async def increment_log(self, now: datetime | None = None):
        """
        Private method which uses class wide variables to incement:
        - the total journey time and distance
        - the start time and position the current tack began. -> for drift range
        """
        gps_data, velocity_data = await self._get_sensor_data(now)

        # If there is no log history at the start of the journey
        if self.start_journey:
            self.journey_data = JourneyData(
                timestamp=gps_data.timestamp,
                start_latitude=gps_data.latitude_nmea,
                start_longitude=gps_data.longitude_nmea,
                end_datetime=gps_data.timestamp,
                end_latitude=gps_data.latitude_nmea,
                end_longitude=gps_data.longitude_nmea,
            )
            self.leg_data = LegData(
                start_datetime=gps_data.timestamp,
                start_latitude=gps_data.latitude_nmea,
                start_longitude=gps_data.longitude_nmea,
                course_over_ground=velocity_data.course_over_ground,
            )
            self.start_journey = False
        # If the journey has already started
        else:
            # Increment the journey data endpoints
            self.journey_data.end_datetime = gps_data.timestamp
            self.journey_data.end_latitude = gps_data.latitude_nmea
            self.journey_data.end_longitude = gps_data.longitude_nmea

            # If the bearing has changes beyond the tolerance reset the leg
            if (
                abs(self.leg_data.course_over_ground - velocity_data.course_over_ground)
                >= self.settings.tack_bearing_tolerance
            ):
                self.leg_data = LegData(
                    start_datetime=gps_data.timestamp,
                    start_latitude=gps_data.latitude_nmea,
                    start_longitude=gps_data.longitude_nmea,
                    course_over_ground=velocity_data.course_over_ground,
                )
            # If the course has continues. Increment the latest cog
            else:
                self.leg_data.course_over_ground = velocity_data.course_over_ground

        logger.info(f"Writing log distance: {self.journey_data.disance_travelled}")
        await self.update_redis_set(self.journey_data, self.leg_data)

    async def finish_jouney(self):
        "Writes and clears the cached journey data."
        del self.journey_data
        del self.leg_data
        self.start_journey = True

    async def update_redis_set(
        self, journey_data: JourneyData, leg_data: LegData
    ) -> None:
        logger.debug("Writing the log and journey data")
        await self.redis_client.write_hashed_set("JOURNEY", journey_data)
        await self.redis_client.write_hashed_set("LEG", leg_data)

    async def get_journey_set(
        self, datetime: datetime = datetime.now(timezone.utc)
    ) -> JourneyData:
        try:
            return JourneyData(
                **(await self.redis_client.read_hashed_set("JOURNEY", datetime))
            )
        except ValidationError:
            logger.debug("No data in the leg set")
            return None

    async def get_leg_set(
        self, datetime: datetime = datetime.now(timezone.utc)
    ) -> LegData | None:
        try:
            return LegData(**(await self.redis_client.read_hashed_set("LEG", datetime)))
        except ValidationError:
            logger.debug("No data in the leg set")
            return None
