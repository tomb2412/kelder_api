import asyncio
import serial_asyncio
import pynmea2
import serial

import logging

from src.kelder_api.components.gps.models import GpsMeasurementData, GpsException, GpsRedisData

logger = logging.getLogger(__name__)

GPS_SERIAL_CONF = {
    "url": "/dev/ttyAMA0",
    "baudrate": 9600,
    "timeout": 0.5
}

async def SerialConnection():
    try:
        reader, _ = await serial_asyncio.open_serial_connection(**GPS_SERIAL_CONF)
        return reader

    except serial.SerialException:
        logger.error("Serial connection to the GPS or port cannot be established")

    except RecursionError:
        logger.error("No newline read in GPS serial file, and recusion limit raised")


async def getGpCoords(serial_reader) -> GpsMeasurementData:
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
        while gps_data_found:
            newdata = await serial_reader.readline()
            newdata = newdata.decode("utf-8", errors="ignore").strip()

            if newdata[0:6] == "$GPRMC":
                nmea_data_line=pynmea2.parse(newdata)
                logger.debug("Parsed GPS data: %s", nmea_data_line)

                gps_coords = GpsRedisData(
                    timestamp = nmea_data_line.timestamp,
                    latitude_nmea = nmea_data_line.lat,
                    longitude_nmea = nmea_data_line.lon,
                    speed_over_ground= nmea_data_line.spd_over_grnd,
                )

                logger.debug(f"Timestamp: {gps_coords.timestamp}, Latitude: {gps_coords.latitude_nmea}, Longitude: {gps_coords.longitude_nmea}")

                return gps_coords

        else:
            message = "NMEA GPRMC format not identified on serial port"
            logger.error(message)
            raise GpsException(message)
    except pynmea2.ParseError:
        logger.error('Error occured parsing GPS serial output:\n%s', e)
    except Exception as error:
        message = "An unhandled exception occured while reading gps data. \n%s"
        logger.error(message, error)
        raise GpsException(message)