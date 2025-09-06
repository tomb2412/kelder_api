from pydantic import BaseModel, Field, computed_field
from datetime import datetime
from pynmea2 import NMEASentence
from typing import List, Dict

from src.kelder_api.components.gps_new.types import (
    GPSStatus,
    LatitudeHemisphere,
    LongitudeHemisphere,
)


class GPRMCRecommendedCourse(BaseModel):
    """
    Data model containing a compilation of GPS statistics from the GPS stream
    GPRMC: Recommended Minimum Navigation Information

    Requires minimum data from a no fix sentence.
    """

    timestamp: datetime = Field(description="Timestamp taken from the GPRMC sentence")
    status: GPSStatus = Field(description="Status of GPS reading")
    latitude_nmea: str | None = Field(
        description='Latitude NMEA output: DDMM.MMMM ("Degrees, decimal minutes")',
        default=None,
    )
    longitude_nmea: str | None = Field(
        description='Longitude NMEA output: DDDMM.MMMM ("Degrees, decimal minutes")',
        default=None,
    )

    @classmethod
    def from_nmea(cls, nmea_data: NMEASentence) -> "GPSSerialGPRMC":
        return cls(
            timestamp=datetime.combine(nmea_data.datestamp, nmea_data.timestamp),
            status=GPSStatus.ACTIVE if nmea_data.status == "A" else GPSStatus.VOID,
            latitude_nmea=nmea_data.lat,
            latitude_hemisphere=LatitudeHemisphere.NORTH
            if nmea_data.lat_dir == "N"
            else LatitudeHemisphere.SOUTH,
            longitude_nmea=nmea_data.lon,
            longitude_hemisphere=LongitudeHemisphere.WEST
            if nmea_data.lon_dir == "W"
            else LongitudeHemisphere.EAST,
        )


class GPGSAActiveSatellites(BaseModel):
    """
    Tracks data recieved from the Active Satilites nmea sentence
    """

    satilite_prns: List[int] = Field(description="PRN of satilites being used for fix")
    satilite_count: int = Field()
    hdop: float = Field(description="Horizontal dilution of position")

    @classmethod
    def from_nmea(cls, nmea_data: NMEASentence) -> "GPSSerialGPGSA":
        satilite_prns = [
            getattr(nmea_data, sat_prn[1])
            for sat_prn in nmea_data.fields
            if sat_prn[1].startswith("sv_id")
        ]
        satilite_prns = [
            satilite_prn for satilite_prn in satilite_prns if satilite_prn != ""
        ]

        return cls(
            satilite_prns=satilite_prns,
            satilite_count=len(satilite_prns),
            hdop=nmea_data.hdop,
        )


class SatelliteInfomation(BaseModel):
    """Individual satellite data from the satellites in view sentence"""

    prn: int = Field(description="The PRN number identifying the satellite")
    elevation: int = Field(
        description="The elevation in degrees (0-90) above the horizon"
    )
    azimuth: int = Field(
        description="Azimuth in degrees (0-359), relative to true north"
    )
    snr: float | None = Field(
        description="Signal to noise ratio (0-99 dB-Hz). Blank/None if not tracked "
    )


class GPGSVSatellitesInView(BaseModel):
    """
    Tracks satellites in veiw data from the serial datastream
    """

    expected_satellites: int | None = Field(
        description="Total number of satellites in veiw", default=None
    )
    satellites: Dict[int, SatelliteInfomation] = Field(
        description="The satellite information", default={}
    )

    def add_satellite(self, prn: int, elevation: int, azimuth: int, snr: float | None):
        """Adds of updates satellite information by the PRN key"""
        self.satellites[prn] = SatelliteInfomation(
            prn=prn, elevation=elevation, azimuth=azimuth, snr=snr
        )

    def from_nmea(self, nmea_data: NMEASentence):
        # Track the number of satellites expected in the stream
        if not self.expected_satellites:
            self.expected_satellites = nmea_data.num_sv_in_view

        # Each GPGSV contains 4 satellites data
        for i in range(4):
            satellite_prn = getattr(nmea_data, f"sv_prn_num_{i + 1}")
            if satellite_prn:
                snr = getattr(nmea_data, f"snr_{i + 1}")
                self.add_satellite(
                    prn=int(satellite_prn),
                    elevation=getattr(nmea_data, f"elevation_deg_{i + 1}"),
                    azimuth=getattr(nmea_data, f"azimuth_{i + 1}"),
                    snr=float(snr) if snr != "" else None,
                )

    @computed_field
    @property
    def all_messages_read(self) -> bool:
        if self.expected_satellites:
            return int(self.expected_satellites) == len(self.satellites)
        else:
            return False


class GPSRedisData(BaseModel):
    # Required fields
    timestamp: datetime = Field(description="Timestamp taken from the GPRMC sentence")
    status: GPSStatus = Field(description="Status of GPS reading from GPRMC data")

    # Optional fields depending on status
    # Active fix data
    latitude_nmea: str = Field(
        description='Latitude NMEA output: DDMM.MMMM ("Degrees, decimal minutes")',
        default="",
    )
    longitude_nmea: str = Field(
        description='Longitude NMEA output: DDDMM.MMMM ("Degrees, decimal minutes")',
        default="",
    )

    # Active or void fix data
    active_prn: List[int] = Field(
        description="PRN identifiers for the active satellites", default=[]
    )
    hdop: float | str = Field(description="Horizontal dilution of position", default="")

    # Void fix data
    satellites_in_view: Dict[int, SatelliteInfomation] = Field(
        description="The satellite information", default={}
    )
