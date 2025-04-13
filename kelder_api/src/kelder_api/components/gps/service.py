import serial
import time
import string
import pynmea2

import logging

from src.kelder_api.components.gps.models import GpsMeasurementData, GpsException

logger = logging.getLogger(__name__)

GPS_SERIAL_CONF = {
    "port": "/dev/ttyAMA0",
    "baudrate": 9600,
    "timeout": 0.5
}

async def getGpCoords() -> GpsMeasurementData:
    """
    Access latest GPS data via the serial port

    To Do:
        - Time period between gps read outs
        - constants: PORT
        - Initialise the serial class every time?

    Returns:
        gps_coors   custom data model with the latest latitude and long
    """


    try:
        ser=serial.Serial(**GPS_SERIAL_CONF)
        dataout = pynmea2.NMEAStreamReader()
        newdata=ser.readline()
    except serial.SerialException:
        logger.error("Serial connection to the GPS or port cannot be established")
    except pynmea2.ParseError:
        logger.error('Error occured parsing GPS serial output:\n%s', e)
    except RecursionError:
        logger.error("No newline read in GPS serial file, and recusion limit raised")

    try:
        if newdata[0:6] == "$GPRMC":
            nmea_data_line=pynmea2.parse(newdata)
            logger.debug("Parsed GPS data: %s", newmsg)

            gps_coords = GpsMeasurementData(
                timestamp = nmea_data_line.timestamp,
                latitude_nmea = nmea_data_line.lat,
                latitude_dec = nmea_data_line.latitude,
                latitude_fmt = '%02d°%02d′%07.4f″' % (nmea_data_line.latitude, nmea_data_line.latitude_minutes, nmea_data_line.latitude_seconds),
                longitude_nmea = nmea_data_line.lon,
                longitude_dec = nmea_data_line.longitude,
                longitude_fmt = '%02d°%02d′%07.4f″' % (nmea_data_line.longitude, nmea_data_line.longitude_minutes, nmea_data_line.longitude_seconds),
                speed_over_ground= nmea_data_line.spd_over_grnd,
                true_course = nmea_data_line.true_course,
                magnetic_variation_absolute = nmea_data_line.mag_variation,
                magnetic_variation_direction = nmea_data_line.mag_var_dir
                )
            logger.debug(f"Timestamp: {gps_coords.timestamp}, Latitude: {gps_coords.latitude_fmt}, Longitude: {gps_coords.longitude_fmt}")

            return gps_coords

        else:
            message = "NMEA GPRMC format not identified on serial port"
            logger.error(message)
            raise GpsException(message)
    except Exception as error:
        message = "An unhandled exception occured while reading gps data. \n%s"
        logger.error(message, exception)
        raise GpsException(message)