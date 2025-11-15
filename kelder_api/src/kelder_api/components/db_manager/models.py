from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, Optional, Tuple

from pydantic import BaseModel, Field, computed_field

if TYPE_CHECKING:
    from src.kelder_api.components.log.models import JourneyData


class JourneyLocation(BaseModel):
    """Typed wrapper for storing latitude/longitude pairs in the database."""

    latitude: str = Field(description="Latitude (usually NMEA) for the waypoint")
    longitude: str = Field(description="Longitude (usually NMEA) for the waypoint")

    def to_db_value(self) -> str:
        """Compact comma separated representation used when persisting."""
        return f"{self.latitude},{self.longitude}"

    @classmethod
    def from_db_value(cls, value: str) -> "JourneyLocation":
        parts = value.split(",", 1)
        if len(parts) != 2:
            raise ValueError("Location values must contain a comma separator.")
        latitude, longitude = (segment.strip() for segment in parts)
        return cls(latitude=latitude, longitude=longitude)


class JourneyHistoryRecord(BaseModel):
    """Represents a single entry in the journey_history table."""

    unique_key: Optional[int] = Field(
        default=None,
        description="Primary key assigned by SQLite when the record is stored.",
    )
    departure_time: datetime = Field(description="Time the journey started")
    arrival_time: datetime = Field(description="Time the journey finished")
    departure_location: JourneyLocation = Field(
        description="Starting coordinates stored as latitude/longitude",
    )
    arrival_location: JourneyLocation = Field(
        description="Arrival coordinates stored as latitude/longitude",
    )

    @computed_field
    @property
    def duration_seconds(self) -> int:
        """Convenient computed field for total journey duration."""
        return int((self.arrival_time - self.departure_time).total_seconds())

    def as_db_values(self) -> Tuple[str, str, str, str]:
        """Return the tuple used by sqlite bindings."""
        return (
            self.departure_time.isoformat(),
            self.arrival_time.isoformat(),
            self.departure_location.to_db_value(),
            self.arrival_location.to_db_value(),
        )

    @classmethod
    def from_row(cls, row: Tuple) -> "JourneyHistoryRecord":
        (
            unique_key,
            departure_time,
            arrival_time,
            departure_location,
            arrival_location,
        ) = row
        return cls(
            unique_key=unique_key,
            departure_time=datetime.fromisoformat(departure_time),
            arrival_time=datetime.fromisoformat(arrival_time),
            departure_location=JourneyLocation.from_db_value(departure_location),
            arrival_location=JourneyLocation.from_db_value(arrival_location),
        )

    def with_unique_key(self, unique_key: int) -> "JourneyHistoryRecord":
        """Return a copy with the database generated primary key."""
        return self.model_copy(update={"unique_key": unique_key})

    @classmethod
    def from_journey_data(cls, journey: "JourneyData") -> "JourneyHistoryRecord":
        """Helper to build a DB record from the in-memory JourneyData model."""
        return cls(
            departure_time=journey.timestamp,
            arrival_time=journey.end_datetime,
            departure_location=JourneyLocation(
                latitude=journey.start_latitude,
                longitude=journey.start_longitude,
            ),
            arrival_location=JourneyLocation(
                latitude=journey.end_latitude,
                longitude=journey.end_longitude,
            ),
        )
