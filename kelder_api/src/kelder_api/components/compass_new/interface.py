import board
import adafruit_lis2mdl
import logging
import numpy as np
import math
from datetime import datetime

from src.kelder_api.components.redis_client.redis_client import RedisClient
from src.kelder_api.components.compass_new.models import CompassRedisData

logger = logging.getLogger(__name__)

class CompassInterface:
    """
    General compass interface between the board and redis server
    TODO: support calibration feature
    """

    def __init__(self, redis_client: RedisClient):
        self.redis_client = redis_client
        self.i2c_board = board.I2C()

    def read_heading_from_compass(self, now: datetime = datetime.now()):
        try:
            magnetometer = adafruit_lis2mdl.LIS2MDL(self.i2c_board)
            logger.debug("successfully connected to the compass and taken reading")
        except ValueError:
            message = "Connection to the I2C board has failed. Check board status light and wiring."
            logging.error(message)
            heading = None
        else:
            magnetic_field_vector = np.array(magnetometer.magnetic)
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
        compass_redis_data =  CompassRedisData(
            timestamp = now,
            heading = heading
        )
        self.write_heading(compass_redis_data)
    
    async def write_heading(self, compass_redis_data: CompassRedisData) -> None:
        logger.dubug("Writing compass data")
        await self.redis_client.write_set("COMPASS", compass_redis_data)
        
    async def read_heading_history_latest(self, active: bool = False) -> CompassRedisData:
        logger.debug("Reading latest compass data")
        heading_history = await self.redis_client.read_set("COMPASS")
        if active:
            return CompassRedisData(**[heading for heading in heading_history if heading["heading"]][0])
        else:
            return CompassRedisData(**heading_history[0])

    async def read_heading_history_all(self, active: bool = False) -> List[CompassRedisData]:
        logger.debug("Reading all compass data")
        heading_history = await self.redis_client.read_set("COMPASS")
        if active:
            return [CompassRedisData(**heading) for heading in heading_history if heading["heading"]]
        else:
            return [CompassRedisData(**heading) for heading in heading_history]
        
    async def read_heading_history_length(self, length: int, active: bool = False) -> List[CompassRedisData]:
        logger.debug(f"Reading compass data of length {length}")
        heading_history = await self.redis_client.read_set("COMPASS")
        if active:
            return [CompassRedisData(**heading) for heading in heading_history if heading["heading"]][0:length]
        else:
            return [CompassRedisData(**heading) for heading in heading_history][0:length]

    async def read_heading_history_timeseries(self, start_datetime: datetime, end_datetime: datetime = datetime.now(), active: bool = False) -> List[CompassRedisData]:
        logger.debug(f"Reading compass data between {start_datetime} to {end_datetime}")
        heading_history = await self.redis_client.read_set("COMPASS", [start_datetime, end_datetime])
        if active:
            return [CompassRedisData(**heading) for heading in heading_history if heading["heading"]]
        else:
            return [CompassRedisData(**heading) for heading in heading_history]