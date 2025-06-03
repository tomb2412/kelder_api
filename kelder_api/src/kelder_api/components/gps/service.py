import asyncio
import logging
import os
from datetime import datetime
from typing import Any, List, Tuple, Union

import pynmea2
import redis
import serial
import serial_asyncio
from pydantic import ValidationError
from redis.exceptions import ConnectionError, TimeoutError

from src.kelder_api.components.gps.models import (
    GpsException,
    GpsMeasurementData,
    GpsRedisData,
)
from src.kelder_api.components.gps.utils import (
    gps_velocity,
    parse_timestamp,
    time_difference_seconds,
    time_elapsed_seconds,
)

logger = logging.getLogger(__name__)


GPS_SERIAL_CONF = {"url": "/dev/ttyAMA0", "baudrate": 9600, "timeout": 0.5}
MAX_DELAY_SECONDS = 30
MAX_VELOCITY_TEMPORAL_CHANGE = 10 # Maximum time between GPS measurements to give for a velocity measurement
GPS_VELOCITY_HISTORY = 10


async def SenseGpCoords() -> GpsMeasurementData:
    """
    Access latest GPS data via the serial port

    To Do:
        - Time period between gps read outs
        - constants: PORT
        - Initialise the serial class every time?

    Returns:
        gps_coors   custom data model with the latest latitude and long
    """

    gps_data_found = True

    try:
        reader, _ = await serial_asyncio.open_serial_connection(**GPS_SERIAL_CONF)

    except serial.SerialException:
        logger.error(
            "Serial connection to the GPS or port cannot be established. Sometimes due to containers with incorrect access"
        )

    try:
        while gps_data_found:
            newdata = await reader.readline()
            newdata = newdata.decode("utf-8", errors="ignore").strip() #"$GPRMC,194200.00,A,5054.828,N,00124.513,W,2.5,90.0,030625,,,A*41" #

            if newdata[0:6] == "$GPRMC":
                logger.info(newdata)
                nmea_data_line = pynmea2.parse(newdata)
                logger.debug("Parsed GPS data: %s", nmea_data_line)

                try:
                    gps_coords = GpsRedisData(
                        timestamp=nmea_data_line.timestamp,
                        latitude_nmea=nmea_data_line.lat,
                        longitude_nmea=nmea_data_line.lon,
                        instantaneous_speed_over_ground=nmea_data_line.spd_over_grnd,
                    )
                    logger.debug(
                        f"Timestamp: {gps_coords.timestamp}, Latitude: {gps_coords.latitude_nmea}, Longitude: {gps_coords.longitude_nmea}"
                    )

                    return gps_coords

                except ValidationError:
                    msg = "Failed to establish a satilite fix."
                    logging.error(msg)
                    raise GpsException(msg)

        else:
            message = "NMEA GPRMC format not identified on serial port"
            logger.error(message)
            raise GpsException(message)
    except pynmea2.ParseError as error:
        logger.error("Error occured parsing GPS serial output:\n%s", error)
    except RecursionError:
        logger.error("No newline read in GPS serial file, and recusion limit raised")

    except Exception as error:
        message = "An unhandled exception occured while reading gps data. \n%s"
        logger.error(message, error)
        raise GpsException(message)


async def ReadGPSCoords() -> GpsRedisData:
    """
    Reads latest GPS data from Redis seriver.
    """

    ships_status, gps_history = await _read_redis_gps()
    gps_coords = parse_gps_data(ships_status, gps_history)
    return gps_coords


async def _read_redis_gps() -> Tuple[str, str, float, float, float, float, List[str]]:
    """
    Reads and parses redis gps measurments
    """
    try:
        r = redis.Redis(
            host=os.getenv("REDIS_HOST", "localhost"),
            port=int(os.getenv("REDIS_PORT", 6379)),
            decode_responses=True,
        )

        ships_status = r.get("ships_status")
        gps_history = r.lrange("gps:History", 0, GPS_VELOCITY_HISTORY)

    except (ConnectionError, TimeoutError):
        msg = "Connection to redis server failed."
        logger.error(msg)
        raise GpsException(msg)
    except AttributeError:
        msg = "Could not read redis GPS data"
        logger.error(msg)
        raise GpsException(msg)

    if ships_status is None or gps_history is None:
        msg = "The redis response reading keys is None. Check worker is writing successfully."
        logger.error(msg)
        raise GpsException(msg)

    r.close()

    return ships_status, gps_history

def parse_gps_data(ships_status: str, gps_history: List[str]):
    """
    Handles extraction of the gps strings
    """
    gps_history_parsed = [
        gps_history_reading.split("|") for gps_history_reading in gps_history
    ]
    gps_history_validated, measurement_latency = gps_measurement_validator(gps_history_parsed)
    velocity = gps_velocity(gps_history_validated)

    gps_coords = GpsMeasurementData(
        ships_status=ships_status,
        measurement_latency=measurement_latency,
        timestamp=gps_history_parsed[0][0],
        latitude_nmea=gps_history_parsed[0][1],
        longitude_nmea=gps_history_parsed[0][2],
        instantaneous_speed_over_ground=gps_history_parsed[0][3],
        average_speed_over_ground=velocity
    )

    return gps_coords

def gps_measurement_validator(gps_history: List[List[str]]) -> Union[List[Any], datetime]:
    """
    Feauture to support a dynamic temoral range for velocity calculations, based on GPS history quality

    This method checks and cleans missing gps measurements:
        - Ensures most recent gps value was taken with a maximum allowed delay
        - Ensures the gps velocity average was taken within a maximum allowed velocity time
        - Trims the gps history to statisy the allowed velocity time period
    """

    gps_history_times = [parse_timestamp(gps_measurement[0]) for gps_measurement in gps_history]

    latest_timestamp = gps_history_times[0]
    try:
        furtherst_timestamp = gps_history_times[GPS_VELOCITY_HISTORY]
    except IndexError:
        logger.error("Please wait to gather sufficient GPS readings for a time average velocity")

    measurement_latency = time_elapsed_seconds(latest_timestamp)

    if measurement_latency > MAX_DELAY_SECONDS:
        msg = "Last successful GPS measurement occured %s seconds ago"
        logger.warning(msg, measurement_latency)

    gps_history_range = GPS_VELOCITY_HISTORY
    time_range_from_history = time_difference_seconds(latest_timestamp, furtherst_timestamp)
    while time_range_from_history > MAX_VELOCITY_TEMPORAL_CHANGE:
        gps_history_range -= 1
        if gps_history_range > 0:
            time_range_from_history = time_difference_seconds(latest_timestamp, gps_history_times[gps_history_range])
        else:
            msg = "GPS history contains no measurements within a recent threshold for an accurate velocity calculation"
            time_range_from_history = 0
            logger.error(msg)

    return gps_history[0:gps_history_range], measurement_latency