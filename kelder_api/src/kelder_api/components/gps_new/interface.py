from typing import AsyncGenerator, Dict, List
from contextlib import asynccontextmanager
import serial_asyncio
import asyncio
import logging
import pynmea2
import serial
from pynmea2 import NMEASentence
from datetime import datetime, timezone

from time import time

from src.kelder_api.components.redis_client.redis_client import RedisClient
from src.kelder_api.configuration.settings import get_settings
from src.kelder_api.components.gps_new.models import (
    GPGSVSatellitesInView,
    GPGSAActiveSatellites,
    GPRMCRecommendedCourse,
    GPSRedisData,
)

logger = logging.getLogger(__name__)


class GPSInterface:
    """
    Provides a GPS interface, through a serial connection with the sensor
    """

    def __init__(self, redis_client: RedisClient):
        self.redis_client = redis_client

        # Attributes for serial gps connection
        self.PORT = get_settings().gps.gps_serial_port
        self.BAUDRATE = get_settings().gps.gps_baudrate
        self.TIMEOUT = get_settings().gps.gps_timeout

        # Attributes for parsing the serial data stream
        self.sentence_models: Dict[str, callable] = {
            "GPRMC": self._set_gprmc_sentence,
            "GPGSA": self._set_gpgsa_sentence,
            "GPGSV": self._set_gpgsv_sentence,
        }

    @asynccontextmanager
    async def _get_serial_connection(
        self,
    ) -> AsyncGenerator[asyncio.StreamReader, None]:
        reader = None
        writer = None

        try:
            reader, writer = await serial_asyncio.open_serial_connection(
                url=self.PORT, baudrate=self.BAUDRATE, timeout=self.TIMEOUT
            )
            yield reader

        except serial.SerialException as error:
            logger.error(
                "Serial connection to the GPS or port cannot be established. Potentially due to containers with incorrect access. \n {error}"
            )
            raise
        except OSError as error:
            logger.error(f"OS error opening serial port {self.port}: {error}")
            raise

        finally:
            if writer and not writer.is_closing():
                try:
                    writer.close()
                    await writer.wait_closed()
                    # logger.debug(f"GPS serial connection closed on port {self.PORT}")

                except Exception as error:
                    logger.error(
                        f"Failed to properly close the gps serial connection on port {self.PORT}"
                    )
                    raise

    def _set_gprmc_sentence(self, nmea_data: NMEASentence):
        # logger.debug("GPRMC sentence identified")
        self.gprmc_recommended_course = GPRMCRecommendedCourse.from_nmea(nmea_data)

    def _set_gpgsa_sentence(self, nmea_data: NMEASentence):
        # logger.debug("GPGSA sentence identified")
        self.gpgsa_active_satellites = GPGSAActiveSatellites.from_nmea(nmea_data)

    def _set_gpgsv_sentence(self, nmea_data: NMEASentence):
        # logger.debug("GPGSV sentence identified")
        self.gpgsv_satellites_in_view.from_nmea(nmea_data)

    async def write_gps(
        self,
        gpgsv_satellites_in_view,
        gprmc_recommended_course,
        gpgsa_active_satellites,
    ) -> None:
        gps_redis_data = GPSRedisData(
            timestamp=gprmc_recommended_course.timestamp,
            status=gprmc_recommended_course.status,
            latitude_nmea=gprmc_recommended_course.latitude_nmea,
            longitude_nmea=gprmc_recommended_course.longitude_nmea,
            active_prn=gpgsa_active_satellites.satilite_prns,
            hdop=gpgsa_active_satellites.hdop,
            satellites_in_view=gpgsv_satellites_in_view.satellites,
        )
        logger.debug("Writing GPS reading.")
        await self.redis_client.write_set("GPS", gps_redis_data)

    async def read_gps_latest(self, active: bool = False) -> GPSRedisData:
        """Retrieves the lastest gps measurement regardless of status"""
        try:
            if active:
                return (await self.read_active_gps_measurements())[0]
            else:
                return GPSRedisData(**(await self.redis_client.read_set("GPS"))[0])
        except IndexError:
            logger.error("No GPS data available")
            return None

    async def read_gps_history_length(
        self, length: int, active: bool = False
    ) -> List[GPSRedisData]:
        """Retrieves the lastest n gps measurement regardless of status"""
        if active:
            gps_history = await self.read_active_gps_measurements()
        else:
            gps_history = [
                GPSRedisData(**gps_measurement)
                for gps_measurement in await self.redis_client.read_set("GPS")
            ]

        try:
            return gps_history[0:length]
        except IndexError:
            logger.debug(
                f"GPS history shorter than length requested. Returning length: {len(gps_history)}"
            )
            return gps_history

    async def read_gps_history_time_series(
        self,
        start_datetime: datetime,
        end_datetime: datetime = datetime.now(timezone.utc),
        active: bool = False,
    ) -> List[GPSRedisData]:
        """Retrieves the gps measurement within a datetime range"""
        gps_time_series = await self.redis_client.read_set(
            "GPS", [start_datetime, end_datetime]
        )

        if active:
            return [
                GPSRedisData(**gps_measurement)
                for gps_measurement in gps_time_series
                if gps_measurement["status"] == "A"
            ]
        else:
            return [
                GPSRedisData(**gps_measurement) for gps_measurement in gps_time_series
            ]

    async def read_gps_all_history(self, active: bool = False) -> List[GPSRedisData]:
        """Returns all GPS history"""
        if active:
            return await self.read_active_gps_measurements()
        else:
            return [
                GPSRedisData(**gps_measurement)
                for gps_measurement in await self.redis_client.read_set("GPS")
            ]

    async def read_active_gps_measurements(self) -> List[GPSRedisData]:
        """Returns only active GPS measurements from all history"""
        return [
            GPSRedisData(**active_measurement)
            for active_measurement in await self.redis_client.read_set("GPS")
            if active_measurement["status"] == "A"
        ]

    def _parse_serial_gps_string(self, sentence) -> None:
        if "GPRMC" in sentence:
            data_type = "GPRMC"
        elif "GPGSA" in sentence:
            data_type = "GPGSA"
        elif "GPGSV" in sentence:
            data_type = "GPGSV"
        else:
            return None
        try:
            self.sentence_models[data_type](pynmea2.parse(sentence))
        except KeyError as error:
            logger.debug(f"Could not parse unsupported NMEA sentence: {data_type}")
        except Exception as error:
            logger.error(
                f"Failed to parse the nmea string:\nstring: {sentence}\nerror: {error}"
            )
            return None

    async def stream_serial_data(
        self, mock_sentence_stream: List[str] | None = None
    ) -> None:
        """Public method to open the serial connection, and processes the datastream until a gps measurement is identified"""
        logger.debug("GPS reading in progress")
        # Clear the satellites in view and other sentense data before reading the serial stream
        self.gpgsv_satellites_in_view = GPGSVSatellitesInView()
        self.gprmc_recommended_course = None
        self.gpgsa_active_satellites = None
        gps_data_identified = False

        if mock_sentence_stream:
            mock_stream_index = 0

        start_time = time()
        while not gps_data_identified:
            if mock_sentence_stream:
                try:
                    newsentence = mock_sentence_stream[mock_stream_index]
                    mock_stream_index += 1
                except IndexError:
                    mock_stream_index = 0
            else:
                async with self._get_serial_connection() as serial_reader:
                    newsentence = await serial_reader.readline()
                    
                newsentence = newsentence.decode("utf-8", errors="ignore").strip()
                # logger.debug(f"Serial reader returned parsed sentence: {newsentence}")
            
            self._parse_serial_gps_string(newsentence)

            # track sentences complete
            if (
                self.gprmc_recommended_course
                and self.gpgsa_active_satellites
                and self.gpgsv_satellites_in_view.all_messages_read
            ):
                gps_data_identified = True

            elif (time() - start_time) > self.TIMEOUT:
                logger.error("Timeout exceeded reading GPS serial stream.")
                raise TimeoutError("Timeout exceeded reading GPS serial stream.")

        await self.write_gps(
            self.gpgsv_satellites_in_view,
            self.gprmc_recommended_course,
            self.gpgsa_active_satellites,
        )
