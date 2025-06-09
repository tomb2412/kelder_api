from datetime import datetime
from typing import List, Any

import numpy as np
from pydantic import BaseModel, Field, computed_field

from src.kelder_api.components.gps.utils import convert_to_decimal_degrees


class HeadingData(BaseModel):
    heading_history: List[str] = Field(
        description="Heading history for format timestamp|heading|latitude|longitude"
    )

    @computed_field
    @property
    def heading_measurements(self) -> List[int]:
        """List of heading measurements."""
        return [int(heading.split("|")[1]) for heading in self.heading_history]

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
