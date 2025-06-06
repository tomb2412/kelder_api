import asyncio
import logging
import signal
from datetime import datetime

import redis
from pydantic import ValidationError

from src.kelder_api.components.compass.exceptions import I2CConnectionFailure
from src.kelder_api.components.compass.service import CompassSensor
from src.kelder_api.components.gps.models import status
from src.kelder_api.components.gps.service import (
    SenseGpCoords,
    parse_gps_data,
)
from src.kelder_api.configuration.settings import Settings

logger = logging.getLogger(__name__)
logging.basicConfig(
    filename=f"/app/logs/{datetime.now().strftime('%Y-%m-%d')}_kelder_api.log",
    encoding="utf-8",
    format="WORKER - {levelname} - {asctime} - {message}",
    style="{",
    datefmt="%Y-%m-%d %H:%M:%S",
    level=logging.DEBUG,
)

r = redis.Redis(
    host=Settings().redis.redis_host,
    port=Settings().redis.redis_port,
    decode_responses=True,
)
stop_event = asyncio.Event()


def shutdown_handler(r):
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

        except ValidationError:
            msg = "GPS fix not established"
            logger.error(msg)
        else:
            r.lpush("gps:History", timestamped_gps.redis_string)
            r.ltrim("gps:History", 0, 10)

            print(timestamped_gps)

            gps_history = r.lrange("gps:History", 0, Settings().gps.gps_velocity_history)
            ships_status = parse_gps_data(gps_history).ships_status
            r.set("ships_status", ships_status.value)

            if ships_status == status.UNDER_WAY:
                try:
                    compass_heading = await CompassSensor.readCompassHeading()
                except I2CConnectionFailure:
                    compass_heading = 0
                    logging.error("Cannot read from compass")
                else:
                    r.lpush(
                        "compass:History",
                        f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}|{compass_heading}",
                    )

                    # Read and parse heading information
                    compass_heading_history = r.lrange(
                        "compass:History", 0, -1
                    )  # UPDATE TO ACTAUL LENGTH

                    # Store until tack changes, or exceeds memory threshold, or status = STATIONARY
                    average_tack_heading, tack_index = CompassSensor.tackDetection(
                        compass_heading_history
                    )
                    r.ltrim("compass:History", 0, tack_index)

                    print(average_tack_heading)

        logger.info("Ships status: %s", ships_status.value)
        await asyncio.sleep(
            Settings().sleep_times.UNDER_WAY_SLEEP
            if ships_status == status.UNDER_WAY
            else Settings().sleep_times.STATIONARY_SLEEP
        )

    logging.info("Clean up shutdown complete")


if __name__ == "__main__":
    asyncio.run(initiate_sensing())
