import asyncio
import logging
import signal
from datetime import datetime

import redis
from pydantic import ValidationError

from src.kelder_api.components.compass.service import readCompassHeading
from src.kelder_api.components.gps.models import sleep_interval, status
from src.kelder_api.components.gps.service import SenseGpCoords

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

    while not stop_event.is_set():
        try:
            timestamped_gps = await SenseGpCoords()
            logger.info("Successfully recieved new GPS data")

            if timestamped_gps.ships_status == status.UNDER_WAY:
                pass
                #compass_heading = await readCompassHeading() #MAKE own redis key

            r.set("gps:Latest", timestamped_gps.redis_string)
            r.lpush("gps:History", timestamped_gps.redis_string)
            r.ltrim("gps:History", 0, 10)

            r.set("ships_status", timestamped_gps.ships_status.value)


        except ValidationError:
            msg = "GPS fix not established"
            logger.error(msg)

        logger.info("Ships status: %s", timestamped_gps.ships_status)
        await asyncio.sleep(
            sleep_interval.UNDER_WAY.value if timestamped_gps.ships_status == status.UNDER_WAY else sleep_interval.STATIONARY.value
            )

    logging.info("Clean up shutdown complete")


if __name__ == "__main__":
    asyncio.run(initiate_sensing())
