import logging
import math
from datetime import datetime, timezone
from typing import List

import numpy as np

from src.kelder_api.components.compass_new.models import CompassRedisData
from src.kelder_api.components.redis_client.redis_client import RedisClient

logger = logging.getLogger(__name__)


class CompassInterface:
    """
    General compass interface between the board and redis server
    TODO: support calibration feature
    """

    def __init__(self, redis_client: RedisClient, fake_transport: bool = True):
        self.redis_client = redis_client
        self._lis2mdl_cls = None
        if fake_transport:
            try:
                import board  # type: ignore[import]
                from adafruit_lis2mdl import LIS2MDL  # type: ignore[import]

                self.i2c_board = board.I2C()
                self._lis2mdl_cls = LIS2MDL
            except Exception:
                logger.error("No board detected")

    async def read_heading_from_compass(
        self,
        now: datetime = datetime.now(timezone.utc),
        fake_measurements: List[float] | None = None,
    ):
        try:
            if fake_measurements:
                logger.debug("Using fake compass sensor")
                magnetic_field_vector = fake_measurements
                raise ValueError
            else:
                if self._lis2mdl_cls is None:
                    raise ValueError("Compass hardware unavailable")

                magnetic_field_vector = self._lis2mdl_cls(self.i2c_board).magnetic
            logger.debug("Successfully connected to the compass and taken reading")
        except ValueError:
            message = (
                "Connection to the I2C board has failed. Check status light and wiring."
            )
            logging.error(message)
            heading = None
        else:
            magnetic_field_vector = np.array(magnetic_field_vector)
            normalised_field_vector = magnetic_field_vector / np.linalg.norm(
                magnetic_field_vector
            )

            heading = math.degrees(
                math.atan2(normalised_field_vector[1], normalised_field_vector[0])
            )
            heading = round(heading)

            if heading < 0:
                heading += 360

        # Writes directly to redis set
        compass_redis_data = CompassRedisData(timestamp=now, heading=heading)
        await self.write_heading(compass_redis_data)

    async def write_heading(self, compass_redis_data: CompassRedisData) -> None:
        logger.debug("Writing compass data")
        await self.redis_client.write_set("COMPASS", compass_redis_data)

    async def read_heading_history_latest(
        self, active: bool = False
    ) -> CompassRedisData:
        logger.debug("Reading latest compass data")
        heading_history = await self.redis_client.read_set("COMPASS")
        if active:
            return CompassRedisData(
                **[
                    heading
                    for heading in heading_history
                    if heading["heading"] is not None
                ][0]
            )
        else:
            # TODO: Add in index error catch - return empty model?
            return CompassRedisData(**heading_history[0])

    async def read_heading_history_all(
        self, active: bool = False
    ) -> List[CompassRedisData]:
        logger.debug("Reading all compass data")
        heading_history = await self.redis_client.read_set("COMPASS")
        if active:
            return [
                CompassRedisData(**heading)
                for heading in heading_history
                if heading["heading"] is not None
            ]
        else:
            return [CompassRedisData(**heading) for heading in heading_history]

    async def read_heading_history_length(
        self, length: int, active: bool = False
    ) -> List[CompassRedisData]:
        logger.debug(f"Reading compass data of length {length}")
        heading_history = await self.redis_client.read_set("COMPASS")
        if active:
            return [
                CompassRedisData(**heading)
                for heading in heading_history
                if heading["heading"] is not None
            ][0:length]
        else:
            return [CompassRedisData(**heading) for heading in heading_history][
                0:length
            ]

    async def read_heading_history_timeseries(
        self,
        start_datetime: datetime,
        end_datetime: datetime = datetime.now(timezone.utc),
        active: bool = False,
    ) -> List[CompassRedisData]:
        logger.debug(f"Reading compass data between {start_datetime} to {end_datetime}")
        heading_history = await self.redis_client.read_set(
            "COMPASS", [start_datetime, end_datetime]
        )
        if active:
            return [
                CompassRedisData(**heading)
                for heading in heading_history
                if heading["heading"] is not None
            ]
        else:
            return [CompassRedisData(**heading) for heading in heading_history]
