from pydantic import BaseModel
from datetime import datetime
import numpy as np

class HeadingData(BaseModel):
    heading_history: List[str] = Field(description="Heading history for format timestamp|heading")

    @computed_field
    @property
    def heading_measurements(self) -> List[int]:
        """ List of heading measurements. """
        return [int(heading.split("|")[1]) for heading in heading_history]
    
    @computed_field
    @property
    def heading_timestamps(self) -> list(datetime):
        """ List of corresponsing measurement timestamps. """
        return [datetime(heading.split("|")[0]).strftime("%Y-%m-%d %H:%M:%S") for heading in heading_history]

    @computed_field
    @property
    def average_heading(self)->float:
        return float(np.mean(self.heading_measurements))
