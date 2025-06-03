import asyncio
import logging
import signal
from datetime import datetime
from enum import Enum

import redis
from pydantic import ValidationError

from src.kelder_api.components.compass.service import readCompassHeading
from src.kelder_api.components.gps.service import SenseGpCoords
from src.kelder_api.components.gps.models import status, sleep_interval

logger = logging.getLogger(__name__)
logging.basicConfig(
    filename=f"/app/logs/{datetime.now().strftime('%Y-%m-%d')}_kelder_api.log",
    encoding="utf-8",
    format="WORKER - {levelname} - {asctime} - {message}",
    style="{",
    datefmt="%Y-%m-%d %H:%M:%S",
    level=logging.DEBUG,
)

stop_event = asyncio.Event()
r = redis.Redis(host="redis", port=6379, decode_responses=True)

VELOCITY_THRESHOLD = 1.5  # speed exceeds 1.5 kts

def shutdown_handler():
    # close redis connections, and clear keys
    r.flushdb()
    r.close()
    # close connection
    stop_event.set()


def set_up_signal_handlers():
    loop = asyncio.get_running_loop()
    loop.add_signal_handler(signal.SIGTERM, shutdown_handler)
    loop.add_signal_handler(signal.SIGINT, shutdown_handler)


async def initiate_sensing():
    set_up_signal_handlers()

    ships_status = status.STATIONARY

    while not stop_event.is_set():
        try:
            timestamped_gps = await SenseGpCoords()
            logger.info("Successfully recieved new GPS data")
            print(timestamped_gps)
            if timestamped_gps.speed_over_ground > VELOCITY_THRESHOLD:
                ships_status = status.UNDER_WAY
                compass_heading = await readCompassHeading()
            else:
                ships_status = status.STATIONARY

            r.set("gps:Latest", timestamped_gps.redis_string)
            r.lpush("gps:History", timestamped_gps.redis_string)
            r.ltrim("gps:History", 0, 10)

            r.set("ships_status", status)


        except ValidationError:
            msg = "GPS fix not established"
            logger.error(msg)

        logger.info("Ships status: %s", ships_status)
        await asyncio.sleep(
            sleep_interval.UNDER_WAY.value if ships_status == status.UNDER_WAY else sleep_interval.STATIONARY.value
            )

    logging.info("Clean up shutdown complete")


if __name__ == "__main__":
    asyncio.run(initiate_sensing())
