import asyncio
import logging
import signal
from datetime import datetime

import redis
from pydantic import ValidationError

from src.kelder_api.components.compass.service import CompassSensor
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
    r = redis.Redis(host="redis", port=6379, decode_responses=True)
    set_up_signal_handlers()

    while not stop_event.is_set():
        try:
            timestamped_gps = await SenseGpCoords()
            logger.info("Successfully recieved new GPS data")
            
            r.lpush("gps:History", timestamped_gps.redis_string)
            r.ltrim("gps:History", 0, 10)

            gps_history = r.lrange("gps:History", 0, GPS_VELOCITY_HISTORY)
            
            r.set("ships_status", timestamped_gps.ships_status.value)

            if timestamped_gps.ships_status == status.UNDER_WAY:
                try:
                    compass_heading = await CompassSensor.readCompassHeading()
                except I2CConnectionFailure:
                    compass_heading = 0
                    logging.error("Cannot read from compass")
                else:
                    r.lpush("compass:History", f"{datetime.now().strftime("%Y-%m-%d %H:%M:%S")}|{compass_heading}")
                    
                    # Read and parse heading information
                    compass_heading_history = r.lrange("compass:History", 0, -1) # UPDATE TO ACTAUL LENGTH

                    # Store until tack changes, or exceeds memory threshold, or status = STATIONARY
                    average_tack_heading, tack_index = CompassSensor.tackDetection(compass_heading_history)
                    r.ltrim("compass:History", 0, tack_index)

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

def identify_ships_status(gps_history: list[str]) -> status:
    """
    Can implement more support for adaption to changing range when underway or stationary
    """
    gps_coords = parse_gps_data(gps_history)

    if gps_coords.average_speed_over_ground > VELOCITY_THRESHOLD:
        return status.UNDER_WAY
    elif gps_coords.average_speed_over_ground <= VELOCITY_THRESHOLD:
        return status.STATIONARY



