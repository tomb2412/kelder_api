from datetime import datetime
from typing import List

import numpy as np
from pydantic import BaseModel, Field, computed_field


class HeadingData(BaseModel):
    heading_history: List[str] = Field(
        description="Heading history for format timestamp|heading"
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
