from datetime import datetime
from typing import List, Any

import numpy as np
from pydantic import BaseModel, Field, computed_field

from src.kelder_api.components.gps.utils import convert_to_decimal_degrees


class CompassHeadingBackground(BaseModel):
    """
    Model used privately by the background worker to store the compass and heading data
    """

    gps_timestamp: datetime = Field("Timestamp from the gps measurement")
    latitude_nmea: str = Field("Latitude output from the gps DDMM.MMMM")
    longitude_nmea: str = Field("Longitude output from the gps DDMM.MMMM")
    compass_heading: float = Field(
        description="Compass heading read directly from the board"
    )

    # Optional fields not known upon initialisation, but required in the redis string
    drift_speed: Optional[float] = Field(
        description="Component of speed perpendicular to heading.", default=None
    )
    drift_bearing: Optional[float] = Field(
        description="Direction of motion perpendicular to heading.", default=None
    )
    tack_index: Optional[int] = Field(
        description="The most recent index in the compass history where a tack was detected",
        default=None,
    )

    @computed_field
    @property
    def redis_string(self) -> str:
        return "|".join(
            [
                self.gps_timestamp.strftime("%Y-%m-%d %H:%M:%S"),
                self.compass_heading,
                self.latitude_nmea,
                self.longitude_nmea,
                self.drift_speed,
                self.drift_bearing,
            ]
        )


class HeadingData(BaseModel):
    heading_history: List[str] = Field(
        description="Heading history for format timestamp|heading|latitude|longitude"
    )

    @computed_field
    @property
    def heading_timestamps(self) -> List[datetime]:
        """List of corresponsing measurement timestamps."""
        return [
            datetime.strptime(heading.split("|")[0], "%Y-%m-%d %H:%M:%S")
            for heading in self.heading_history
        ]

    @computed_field
    @property
    def heading_measurements(self) -> List[int]:
        """List of heading measurements."""
        return [int(heading.split("|")[1]) for heading in self.heading_history]

    @computed_field
    @property
    def average_heading(self) -> float:
        return float(np.mean(self.heading_measurements))

    @computed_field
    @property
    def start_of_tack_latitude(self) -> str:
        """The furthest back heading recording - third element is latitude"""
        return self.heading_history[-1].split("|")[2]

    @computed_field
    @property
    def start_of_tack_longitude(self) -> str:
        """The furthest back heading recording - fourth element is longitude"""
        return self.heading_history[-1].split("|")[3]

    @computed_field
    @property
    def end_of_tack_latitude(self) -> str:
        """The most recent heading recording - third element is latitude"""
        return self.heading_history[0].split("|")[2]

    @computed_field
    @property
    def end_of_tack_longitude(self) -> str:
        """The most recent heading recording - fourth element is longitude"""
        return self.heading_history[0].split("|")[3]
