import time
import redis
import logging
import asyncio
import signal
from datetime import datetime

from enum import Enum

from pydantic import ValidationError

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


class mode(Enum):
    active = 1  # Seconds between samples
    idle = 5


VELOCITY_THRESHOLD = 1.5  # speed exceeds 1.5 kts

r = redis.Redis(host="redis", port=6379, decode_responses=True)


def shutdown_handler():
    print("Shutting down...")

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

    sleep_interval = mode.active

    while not stop_event.is_set():
        try:
            timestamped_gps = await SenseGpCoords()
            logger.info("Successfully recieved new GPS data")

            if timestamped_gps.speed_over_ground > VELOCITY_THRESHOLD:
                sleep_interval = mode.active
                status = "Under Way"

            else:
                sleep_interval = mode.idle
                status = "Stationary"

            r.set("gps:Latest", timestamped_gps.redis_string)
            r.lpush("gps:History", timestamped_gps.redis_string)
            r.ltrim("gps:History", 0, 10)

            r.set("ships_status", status)

        except ValidationError as error:
            msg = "GPS fix not established"
            logger.error(msg)

        logger.info("GPS read successful. Ships status: %s", status)
        await asyncio.sleep(sleep_interval.value)

    logging.info("Clean up shutdown complete")


if __name__ == "__main__":
    asyncio.run(initiate_sensing())
