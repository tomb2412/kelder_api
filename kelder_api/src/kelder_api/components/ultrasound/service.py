# hc_sr04_pi5.py
import logging
from datetime import datetime, timezone

from gpiozero import DistanceSensor

from src.kelder_api.components.redis_client.redis_client import RedisClient
from src.kelder_api.components.ultrasound.models import BilgeDepth

# GPIO pins
TRIG = 23
ECHO = 24

logger = logging.getLogger(__name__)


class BilgeDepthSensor:
    """Manages the ultrasound which measures the depth of water below the bilge."""

    def __init__(self, redis_client: RedisClient):
        self.redis_client = redis_client
        self.TRIG = TRIG
        self.ECHO = ECHO
        
        self.sensor = DistanceSensor(self.TRIG, self.ECHO)

    async def record_bilge_depth(self) -> None:
        """Capture the current bilge depth and persist it to Redis."""
        reading = self._ultrasound_reading()
        await self.write_bilge_depth(reading)

    def _ultrasound_reading(self) -> BilgeDepth:
        """Takes the reading from the ultrasound component."""
        distance_value = None
        try:
            distance_value = self.sensor.distance
            logger.debug("Successfully read ultrasound distance: %s", distance_value)
        except Exception:
            logger.exception("Failed to take the ultrasound measurement")
        finally:
            if sensor:
                sensor.close()

        return BilgeDepth(
            timestamp=datetime.now(timezone.utc),
            bilge_depth=distance_value,
        )

    async def write_bilge_depth(self, bilge_depth: BilgeDepth) -> None:
        logger.debug("Writing bilge_depth data")
        await self.redis_client.write_set("BILGE_DEPTH", bilge_depth)

    async def read_latest_bilge_depth(self) -> BilgeDepth:
        logger.debug("Reading latest bilge depth data from Redis")
        depth = await self.redis_client.read_set("BILGE_DEPTH")
        try:
            return BilgeDepth(**depth[0])
        except IndexError:
            logger.debug("No bilge depth data available")
            return BilgeDepth(timestamp=datetime.now(timezone.utc), bilge_depth=None)
