from datetime import datetime, timedelta
import logging
from typing import List
import numpy as np

from src.kelder_api.components.redis_client.redis_client import RedisClient
from src.kelder_api.components.gps_new.interface import GPSInterface
from src.kelder_api.components.velocity.models import GPSVelocity, CalculationType
from src.kelder_api.configuration.settings import Settings
from src.kelder_api.components.gps_new.models import GPSRedisData
from src.kelder_api.components.velocity.utils import (
    haversine,
    time_difference_seconds,
    bearing_degrees,
    convert_to_decimal_degrees,
    average_bearing,
)

logger = logging.getLogger(__name__)


class VelocityCalculator:
    def __init__(self, gps_interface: GPSInterface, redis_client: RedisClient):
        self.gps_interface = gps_interface
        self.redis_client = redis_client

        self.velocity_calculation_type = Settings().velocity.velocity_calculation_type
        self.num_gps_measurements = Settings().velocity.gps_velocity_history

    async def _get_gps_data(self, now: datetime) -> List[GPSRedisData]:
        """Private method which retrieves gps data through n latest measurements or last n seconds"""
        if self.velocity_calculation_type == CalculationType.LENGTH:
            return await self.gps_interface.read_gps_history_length(
                length=self.num_gps_measurements, active=True
            )
        else:
            start_datetime = now - timedelta(seconds=self.num_gps_measurements)
            return await self.gps_interface.read_gps_history_time_series(
                start_datetime, active=True
            )

    async def calculate_gps_velocity(
        self, datetime_now: datetime = datetime.now()
    ) -> GPSVelocity:
        """Calculates a speed over ground in knots from gps history, returns an error if less than 2 measurements"""
        gps_history = await self._get_gps_data(datetime_now)
        gps_points = len(gps_history)

        if gps_points <= 1:
            message = (
                "Insufficient GPS history for a velocity measurement, length: %s"
                % gps_points
            )
            logger.warning(message)
            speed_over_ground_avg = None
            course_over_ground_avg = None
        else:
            course_over_ground_list = []
            speed_over_ground_list = []
            for i in range(0, gps_points - 1):
                latitude_start = convert_to_decimal_degrees(
                    gps_history[i].latitude_nmea, lon=False
                )
                latitude_end = convert_to_decimal_degrees(
                    gps_history[i + 1].latitude_nmea, lon=False
                )
                longitude_start = convert_to_decimal_degrees(
                    gps_history[i].longitude_nmea
                )
                longitude_end = convert_to_decimal_degrees(
                    gps_history[i + 1].longitude_nmea
                )

                distance_travelled = haversine(
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
                try:
                    instantaneous_speed_over_ground = (
                        distance_travelled / time_difference
                    )
                except ZeroDivisionError:
                    instantaneous_speed_over_ground = 0
                speed_over_ground_list.append(instantaneous_speed_over_ground)
                course_over_ground_list.append(cog_degrees)

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
