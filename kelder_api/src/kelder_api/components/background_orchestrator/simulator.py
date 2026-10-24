import math
import random
from datetime import datetime, timezone
from pathlib import Path

import yaml

from src.kelder_api.components.compass_new.interface import CompassInterface
from src.kelder_api.components.compass_new.models import CompassRedisData
from src.kelder_api.components.gps_new.interface import GPSInterface
from src.kelder_api.components.gps_new.models import GPSRedisData
from src.kelder_api.components.gps_new.types import GPSStatus
from src.kelder_api.components.redis_client.redis_client import RedisClient
from src.kelder_api.components.redis_client.types import RedisSetNames
from src.kelder_api.components.velocity.utils import (
    convert_to_decimal_degrees,
    decimal_to_dms_format,
)
from src.kelder_api.configuration.logging_controller import get_logger

logger = get_logger(__name__, "simulator")


class Simulator(CompassInterface, GPSInterface):
    """Injects simulation data for the hardware, using yaml behaviours"""

    def __init__(
        self,
        redis_client: RedisClient,
        simulation_file_name: str,
    ):
        self.redis_client = redis_client
        self.current_time = datetime.now(tz=timezone.utc)

        self.simulation_file_name = simulation_file_name
        self._initialise_simulation_parameters()

    def _initialise_simulation_parameters(self) -> None:
        parent_path = (
            Path(__file__).resolve().parents[0]
            / "simulations"
            / f"{self.simulation_file_name}.yaml"
        )
        config = yaml.safe_load(open(parent_path))

        self.speed = config["boat"][0]["speed"]
        self.cog = config["boat"][1]["cog"]
        self.turn_rate = config["boat"][2]["turn_rate"]
        self.heading_variation = config["boat"][3]["heading_variation"]

        self.max_iterations = config["simulation"][0]["max_iterations"]
        self.interation = 0
        # Not sure how to do manage the different simulations in one file,
        #  w dicts or many files with one dict
        self.latitude = config["simulation"][1]["start_latitude"]
        self.longitude = config["simulation"][2]["start_longitude"]
        self.heading = config["simulation"][3]["heading"]

        try:
            velocity_plan = config["simulation"][4]

            self.loop_count = 0
            self.velocity_plan = []
            self.turn = 0  # Field to track what turn is active
            for turn in velocity_plan["velocity_plan"]:
                self.velocity_plan.append(
                    (
                        turn["turn"][0]["iterations"],
                        turn["turn"][1]["speed"],
                        turn["turn"][2]["cog"],
                        turn["turn"][3]["heading"],
                    )
                )
        except IndexError:
            self.velocity_plan = None

        logger.info("Initialised simulation data")

    async def repeat_handler(self) -> None:
        self.interation += 1
        logger.debug(
            "Simulation currently on iteration %s of %s",
            self.interation,
            self.max_iterations,
        )

        if self.interation == self.max_iterations:
            await self.clear_redis()
            self._initialise_simulation_parameters()

    async def clear_redis(self) -> None:
        sensor_keys = [
            f"sensor:ts:{sensor.value}"
            for sensor in [
                RedisSetNames.GPS,
                RedisSetNames.COMPASS,
                RedisSetNames.VELOCITY,
                RedisSetNames.LOG,
                RedisSetNames.DRIFT,
                RedisSetNames.BILGE_DEPTH,
            ]
        ]
        async with self.redis_client.get_connection() as redis:
            await redis.unlink(*sensor_keys)

        logger.info("Cleared the redis data streams")

    async def simulate_gps_sensor(self):
        # Advance by the real elapsed time so loop overhead doesn't drift the clock
        now = datetime.now(tz=timezone.utc)
        time_increment = (now - self.current_time).total_seconds()
        self.current_time = now

        if self.velocity_plan is not None:
            if self.loop_count == self.velocity_plan[self.turn][0]:
                self.loop_count = 0
                self.turn = (self.turn + 1) % len(self.velocity_plan)

            self.loop_count += 1
            self.speed = self.velocity_plan[self.turn][1]
            self.cog = self.velocity_plan[self.turn][2]

        self.latitude, self.longitude = self._increment_latitude_longitude(
            lat_deg=self.latitude,
            lon_deg=self.longitude,
            speed_knots=float(self.speed),
            bearing_deg=float(self.cog),
            dt_seconds=float(time_increment),
        )

        gps_redis_data = GPSRedisData(
            timestamp=self.current_time,
            status=GPSStatus.ACTIVE,
            latitude_nmea=self.latitude,
            longitude_nmea=self.longitude,
            active_prn=[10],
            hdop=0,
            satellites_in_view={},
        )

        await self.redis_client.write_set(RedisSetNames.GPS, gps_redis_data)

    async def simulate_compass_sensor(self):
        if self.velocity_plan is not None:
            self.heading = self.velocity_plan[self.turn][3]

        if self.heading_variation != 0:
            self.heading += random.randint(
                -self.heading_variation, self.heading_variation
            )

        compass_redis_data = CompassRedisData(
            timestamp=self.current_time, heading=self.heading
        )
        await self.redis_client.write_set(RedisSetNames.COMPASS, compass_redis_data)

    async def simulate_ultrasound_sensor(self):
        pass

    def _increment_latitude_longitude(
        self, lat_deg, lon_deg, speed_knots, bearing_deg, dt_seconds
    ):
        """Move a position using a simple flat-earth approximation."""
        lat_decimal = convert_to_decimal_degrees(lat_deg, lon=False)
        lon_decimal = convert_to_decimal_degrees(lon_deg, lon=True)

        bearing = math.radians(bearing_deg)

        # Distance travelled in nautical miles (1 NM ≈ 1 arc-minute latitude)
        distance_nm = speed_knots * (dt_seconds / 3600.0)
        logger.info(f"The distance covered is: {distance_nm}")

        delta_lat_minutes = distance_nm * math.cos(bearing)

        # Avoid division by zero when cos(lat) is ~0 (near poles)
        cos_lat = math.cos(math.radians(lat_decimal)) or 1e-9
        delta_lon_minutes = distance_nm * math.sin(bearing) / cos_lat

        new_lat_deg = lat_decimal + (delta_lat_minutes / 60.0)
        new_lon_deg = lon_decimal + (delta_lon_minutes / 60.0)

        new_lat_nmea = decimal_to_dms_format(new_lat_deg, is_lon=False)
        new_lon_nmea = decimal_to_dms_format(new_lon_deg, is_lon=True)

        logger.info(
            f"The latitude has changed: {lat_deg} ({lat_decimal:.6f}°) to"
            f" {new_lat_nmea} ({new_lat_deg:.6f}°)"
        )
        logger.info(
            f"The longitude has changed: {lon_deg} ({lon_decimal:.6f}°) to"
            f" {new_lon_nmea} ({new_lon_deg:.6f}°)"
        )

        return new_lat_nmea, new_lon_nmea
