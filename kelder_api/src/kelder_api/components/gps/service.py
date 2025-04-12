import serial
import time
import string
import pynmea2

import logging

from src.kelder_api.components.gps.models import gpsCoords

logger = logging.getLogger(__name__)

GPS_SERIAL_CONF = {
    "port": "/dev/ttyAMA0",
    "baudrate": 9600,
    "timeout": 0.5
}

async def getGpCoords() -> gpsCoords:
    """
    Access latest GPS data via the serial port

    To Do:
        - Time period between gps read outs
        - constants: PORT
        - Initialise the serial class every time?

    Returns:
        gps_coors   custom data model with the latest latitude and long
    """

    ser=serial.Serial(**GPS_SERIAL_CONF)
    dataout = pynmea2.NMEAStreamReader()
    newdata=ser.readline()

    if newdata[0:6] == "$GPRMC":
        newmsg=pynmea2.parse(newdata)

        gps_coords = GpsCoords(lat = newmsg.latitude, long= newmsg.longitude)
        logging.info(f"Latitude={gps_coords.lat} and Longitude={gps_coords.long}")

        return gps_coords

    else:
        return 
