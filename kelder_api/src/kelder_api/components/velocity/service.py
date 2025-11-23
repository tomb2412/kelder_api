import logging
from datetime import datetime, timedelta, timezone
from typing import List, Tuple

from src.kelder_api.components.gps_new.interface import GPSInterface
from src.kelder_api.components.gps_new.models import GPSRedisData
from src.kelder_api.components.redis_client.redis_client import RedisClient
from src.kelder_api.components.velocity.models import CalculationType, GPSVelocity
from src.kelder_api.components.velocity.utils import (
    average_bearing,
    bearing_degrees,
    convert_to_decimal_degrees,
    haversine,
    time_difference_seconds,
)
from src.kelder_api.configuration.logging_config import setup_logging
from src.kelder_api.configuration.settings import get_settings

setup_logging(component="velocity")
logger = logging.getLogger("velocity")


class VelocityCalculator:
    def __init__(self, gps_interface: GPSInterface, redis_client: RedisClient):
        self.gps_interface = gps_interface
        self.redis_client = redis_client

        velocity_settings = get_settings().velocity
        self.velocity_calculation_type = velocity_settings.velocity_calculation_type
        self.num_gps_measurements = velocity_settings.gps_velocity_history

    async def _get_gps_data(
        self, end_datetime: datetime | None = None
    ) -> Tuple[List[GPSRedisData], datetime]:
        """Fetch GPS history using either fixed length or recent time window."""

        if self.velocity_calculation_type == CalculationType.LENGTH:
            return await self.gps_interface.read_gps_history_length(
                length=self.num_gps_measurements, active=True
            ), end_datetime
        else:
            if end_datetime is None:
                end_datetime = datetime.now(timezone.utc).replace(microsecond=0)
            start_datetime = end_datetime - timedelta(seconds=self.num_gps_measurements)

            return await self.gps_interface.read_gps_history_time_series(
                start_datetime, end_datetime=end_datetime, active=True
            ), end_datetime

    async def calculate_gps_velocity(
        self, datetime_now: datetime | None = None
    ) -> GPSVelocity:
        """Calculate speed over ground in knots from recent GPS history."""
        gps_history, datetime_now = await self._get_gps_data(datetime_now)
        gps_points = len(gps_history)

        logger.info(
            "Identified %s GPS points in the last %s units",
            gps_points,
            self.num_gps_measurements,
        )

        if gps_points <= 1:
            logger.warning(
                "Insufficient GPS history for a velocity measurement; length: %s",
                gps_points,
            )
            speed_over_ground_avg = None
            course_over_ground_avg = None
        else:
            course_over_ground_list = []
            speed_over_ground_list = []
            for i in range(0, gps_points - 1):
                latitude_end = convert_to_decimal_degrees(
                    gps_history[i].latitude_nmea, lon=False
                )
                latitude_start = convert_to_decimal_degrees(
                    gps_history[i + 1].latitude_nmea, lon=False
                )
                longitude_end = convert_to_decimal_degrees(
                    gps_history[i].longitude_nmea
                )
                longitude_start = convert_to_decimal_degrees(
                    gps_history[i + 1].longitude_nmea
                )
                distance_travelled_nm = haversine(
                    latitude_start=latitude_start,
                    latitude_end=latitude_end,
                    longitude_start=longitude_start,
                    longitude_end=longitude_end,
                )
                time_difference = time_difference_seconds(
                    time_end=gps_history[i].timestamp,
                    time_start=gps_history[i + 1].timestamp,
                )
                cog_degrees = bearing_degrees(
                    latitude_start=latitude_start,
                    latitude_end=latitude_end,
                    longitude_start=longitude_start,
                    longitude_end=longitude_end,
                )

                if time_difference <= 0:
                    instantaneous_speed_over_ground = 0
                else:
                    instantaneous_speed_over_ground = (
                        distance_travelled_nm / time_difference
                    ) * 3600  # convert to knots
                speed_over_ground_list.append(instantaneous_speed_over_ground)
                course_over_ground_list.append(cog_degrees)

            logger.debug(
                f"Calculated a speed over ground list to be: {speed_over_ground_list}"
            )
            logger.debug(
                f"Calculated a course over ground list to be: {course_over_ground_list}"
            )
            speed_over_ground_avg = sum(speed_over_ground_list) / (gps_points - 1)
            course_over_ground_avg = average_bearing(course_over_ground_list)

        await self.write_velocity(
            GPSVelocity(
                timestamp=datetime_now,
                speed_over_ground=speed_over_ground_avg,
                course_over_ground=course_over_ground_avg,
                number_of_measurements=gps_points,
            )
        )

    async def write_velocity(self, gps_velocity: GPSVelocity) -> None:
        logger.debug("Writing gps reading")
        await self.redis_client.write_set("VELOCITY", gps_velocity)

    async def read_velocity_latest(self, active: bool = False) -> GPSVelocity:
        """
        Reads the latest velocity in the redis velocity set

        Args:
            active  filter invalid velocity measurments (None)
        """
        logger.debug("Reading latest velocity measurement")
        try:
            if active:
                velocities = await self.redis_client.read_set("VELOCITY")
                latest_active_velocity = [
                    active_sog
                    for active_sog in velocities
                    if active_sog["speed_over_ground"] is not None
                ][0]
                return GPSVelocity(**latest_active_velocity)
            else:
                return GPSVelocity(**(await self.redis_client.read_set("VELOCITY"))[0])
        except IndexError:
            logger.info("No velocity data found in redis")
            return GPSVelocity(
                timestamp=datetime.now(timezone.utc),
                speed_over_ground=None,
                course_over_ground=None,
                number_of_measurements=0,
            )

    async def read_velocity_all(self, active: bool = False) -> List[GPSVelocity]:
        logger.debug("Reading all velocity measurement")
        if active:
            velocities = await self.redis_client.read_set("VELOCITY")
            return [
                GPSVelocity(**active_sog)
                for active_sog in velocities
                if active_sog["speed_over_ground"] is not None
            ]
        else:
            return [
                GPSVelocity(**velocity)
                for velocity in await self.redis_client.read_set("VELOCITY")
            ]

    async def read_velocity_timeseries(
        self,
        start_datetime: datetime,
        end_datetime: datetime = datetime.now(tz=timezone.utc),
        active: bool = True,
    ) -> List[GPSVelocity]:
        logger.info(f"Reading velocity data between {start_datetime} to {end_datetime}")
        velocity_set = await self.redis_client.read_set(
            "VELOCITY", [start_datetime, end_datetime]
        )
        if active:
            return [
                GPSVelocity(**active_sog)
                for active_sog in velocity_set
                if active_sog["speed_over_ground"] is not None
            ]
        else:
            return [GPSVelocity(**velocity) for velocity in velocity_set]
