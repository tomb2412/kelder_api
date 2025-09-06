import asyncio
import logging
import signal
from datetime import datetime
from typing import List

import redis

#import redis.asyncio as redis
from pydantic import ValidationError

import digitalio
from digitalio import DigitalInOut

from src.kelder_api.components.compass.exceptions import I2CConnectionFailure
from src.kelder_api.components.compass.service import CompassSensor
from src.kelder_api.components.gps.models import GpsMeasurementData, status
from src.kelder_api.components.gps.service import (
    SenseGpCoords,
    extract_gps_data,
)
from src.kelder_api.components.gps.utils import haversine
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

    # Initialising status for the loop's logging feature
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

            gps_history = r.lrange(
                "gps:History", 0, Settings().gps.gps_velocity_history
            )
            gps_extracted = extract_gps_data(gps_history)
            print(gps_extracted)
            previous_ships_status = ships_status
            ships_status = gps_extracted.ships_status

            r.set("ships_status", ships_status.value)

            if ships_status == status.UNDER_WAY:
                await record_compass_measurement(gps_extracted)
                await update_log_values(gps_extracted,gps_history,ships_status,previous_ships_status)

        logger.info("Ships status: %s", ships_status.value)
        await asyncio.sleep(
            Settings().sleep_times.UNDER_WAY_SLEEP
            if ships_status == status.UNDER_WAY
            else Settings().sleep_times.STATIONARY_SLEEP
        )

    logging.info("Clean up shutdown complete")

async def update_log_values(
        gps_extracted: GpsMeasurementData,
        gps_history: List[str],
        ships_status: status,
        previous_ships_status: status
    ) -> None:
    """
    Handles distance and time logging for each trip. Trip defined as being underway
    """
    # If the previous status was stationary, start the log
    if previous_ships_status == status.STATIONARY:
        r.hset("log", mapping={"time_start": datetime.now().strftime("%Y-%m-%d %H:%M:%S"), "log": 0})
        previous_log = 0
    # If the boat was already underway
    else:
        previous_log = r.hget("logs", "log")
        print(previous_log)

    # Try and find the previous gps measurement
    try:
        previous_gps_measurement = gps_history[1].split("|")
    # Occurs if the gps history is empty.
    except IndexError:
        logger.warning("Ships log could not be calculated due to no GPS history")
        previous_latitude_nmea = gps_extracted.latitude_nmea
        previous_longitude_nmea = gps_extracted.longitude_nmea
    else:
        previous_latitude_nmea = previous_gps_measurement[1]
        previous_longitude_nmea = previous_gps_measurement[2]

    # Calculate the new log distance
    log_distance_under_way = float(previous_log) + float(haversine(
                    previous_latitude_nmea,
                    previous_longitude_nmea,
                    gps_extracted.latitude_nmea,
                    gps_extracted.longitude_nmea
                )
    )

    r.hset("logs", "log", log_distance_under_way)
    logger.info("Trip log recalculated: %s", log_distance_under_way)


async def record_compass_measurement(gps_extracted: GpsMeasurementData) -> None:
    """
    Make a compass reading and call tack detection and drift processes
    """
    try:
        compass_heading = await CompassSensor.readCompassHeading()
        logging.info(
            "Successfully retrieved compass heading: %s", compass_heading
        )
    except I2CConnectionFailure:
        compass_heading = 0
        logging.error("Cannot read from compass")
    else:
        r.lpush(
            "compass:History",
            f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}|{compass_heading}|{gps_extracted.latitude_nmea}|{gps_extracted.longitude_nmea}",
        )

        # Read and parse heading information
        compass_heading_history = r.lrange(
            "compass:History", 0, 10
        )  # TODO: UPDATE TO ACTAUL LENGTH
        print(compass_heading_history)

        # Store until tack changes, or exceeds memory threshold, or status = STATIONARY
        heading_data, tack_index = CompassSensor.tackDetection(
            compass_heading_history
        )
        r.ltrim("compass:History", 0, tack_index)
        print(heading_data)
        drift_speed, drift_bearing = CompassSensor.driftCalculation(
            heading_data
        )

if __name__ == "__main__":
    asyncio.run(initiate_sensing())
