from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, Optional, Tuple

from pydantic import BaseModel, Field, computed_field

from src.kelder_api.components.coordinate import Coordinate

if TYPE_CHECKING:
    from src.kelder_api.components.log.models import JourneyData


class JourneyLocation(BaseModel):
    """Typed wrapper for storing a coordinate pair in the database.

    Stored in SQLite as ``"<lat_decimal>,<lon_decimal>"`` (decimal degrees).
    The ``Coordinate`` validator transparently accepts legacy NMEA strings
    stored by older versions of the application.
    """

    coordinate: Coordinate = Field(description="Geographic position")

    def to_db_value(self) -> str:
        """Decimal-degree comma-separated string for SQLite persistence."""
        return f"{self.coordinate.latitude},{self.coordinate.longitude}"

    @classmethod
    def from_db_value(cls, value: str) -> "JourneyLocation":
        parts = value.split(",", 1)
        if len(parts) != 2:
            raise ValueError("Location values must contain a comma separator.")
        lat_str, lon_str = (segment.strip() for segment in parts)
        return cls(coordinate=Coordinate(latitude=lat_str, longitude=lon_str))


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
    distance_travelled: float = Field(
        description="Distance covered in nautical miles for this journey"
    )
    gps_data: str = Field(
        description="Raw GPS data captured for the trip; can be JSON string",
    )

    @computed_field
    @property
    def duration_seconds(self) -> int:
        """Convenient computed field for total journey duration."""
        return int((self.arrival_time - self.departure_time).total_seconds())

    def as_db_values(self) -> Tuple[str, str, str, str, float, Optional[str]]:
        """Return the tuple used by sqlite bindings."""
        return (
            self.departure_time.isoformat(),
            self.arrival_time.isoformat(),
            self.departure_location.to_db_value(),
            self.arrival_location.to_db_value(),
            self.distance_travelled,
            self.gps_data,
        )

    @classmethod
    def from_row(cls, row: Tuple) -> "JourneyHistoryRecord":
        (
            unique_key,
            departure_time,
            arrival_time,
            departure_location,
            arrival_location,
            distance_travelled,
            gps_data,
        ) = row
        return cls(
            unique_key=unique_key,
            departure_time=datetime.fromisoformat(departure_time),
            arrival_time=datetime.fromisoformat(arrival_time),
            departure_location=JourneyLocation.from_db_value(departure_location),
            arrival_location=JourneyLocation.from_db_value(arrival_location),
            distance_travelled=float(distance_travelled),
            gps_data=gps_data,
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
            departure_location=JourneyLocation(coordinate=journey.start_coordinate),
            arrival_location=JourneyLocation(coordinate=journey.end_coordinate),
            distance_travelled=journey.distance_travelled,
            gps_data=journey.gps_data,
        )
