from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field, computed_field, field_validator

from src.kelder_api.components.coordinate.utils import convert_to_decimal_degrees, haversine


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _nmea_to_decimal(value: str) -> float:
    """Delegate NMEA DDMM.MMMM / DDDMM.MMMM parsing to the shared utility."""
    return convert_to_decimal_degrees(value)


def _coerce_latitude(value: Any) -> float:
    """Coerce any coordinate representation to a decimal-degree latitude float.

    Accepted input formats
    ----------------------
    * ``float`` / ``int`` in decimal degrees (e.g. ``50.737``)
    * ``float`` / ``int`` that is actually NMEA-encoded (abs > 90, e.g. ``5044.20``)
    * Decimal-degree string (e.g. ``"50.737"``)
    * NMEA string with 4+ integer digits (e.g. ``"5044.20"``, ``"-5044.20"``)
    """
    if isinstance(value, (int, float)):
        val = float(value)
        # Valid decimal latitude is -90..90; anything outside must be NMEA
        if abs(val) > 90.0:
            return _nmea_to_decimal(str(val))
        return val

    if isinstance(value, str):
        stripped = value.strip()
        # NMEA DDMM has at least 4 integer digits before the decimal point.
        integer_part = stripped.lstrip("+-").split(".")[0]
        if len(integer_part) >= 4:
            return _nmea_to_decimal(stripped)
        return float(stripped)

    raise TypeError(f"Cannot coerce {type(value).__name__!r} to latitude")


def _coerce_longitude(value: Any) -> float:
    """Coerce any coordinate representation to a decimal-degree longitude float.

    The tricky case is a small NMEA longitude such as ``"00118.90"`` (1°18.9'W)
    whose float value (118.9) is within the valid decimal range (±180).  The
    digit-count check (≥5 integer digits) catches it reliably.

    Accepted input formats
    ----------------------
    * ``float`` / ``int`` in decimal degrees (e.g. ``-1.315``)
    * ``float`` / ``int`` out of ±180 range (clearly NMEA)
    * Decimal-degree string (e.g. ``"-1.315"``)
    * NMEA string with 5+ integer digits (e.g. ``"00118.90"``, ``"-00118.90"``)
    """
    if isinstance(value, (int, float)):
        val = float(value)
        if abs(val) > 180.0:
            return _nmea_to_decimal(str(val))
        return val

    if isinstance(value, str):
        stripped = value.strip()
        # NMEA DDDMM has at least 5 integer digits before the decimal point.
        integer_part = stripped.lstrip("+-").split(".")[0]
        if len(integer_part) >= 5:
            return _nmea_to_decimal(stripped)
        return float(stripped)

    raise TypeError(f"Cannot coerce {type(value).__name__!r} to longitude")


def _format_ddm(decimal_deg: float, *, is_lat: bool) -> str:
    """Format a decimal-degree value as degrees-decimal-minutes.

    Latitude  example: ``50°44.20'N``
    Longitude example: ``001°18.90'W``
    """
    if is_lat:
        hemi = "N" if decimal_deg >= 0 else "S"
        deg_width = 2
    else:
        hemi = "E" if decimal_deg >= 0 else "W"
        deg_width = 3

    abs_deg = abs(decimal_deg)
    degrees = int(abs_deg)
    minutes = (abs_deg - degrees) * 60.0
    return f"{degrees:0{deg_width}d}\u00b0{minutes:05.2f}'{hemi}"


# ---------------------------------------------------------------------------
# Public class
# ---------------------------------------------------------------------------


class Coordinate(BaseModel):
    """A geographic coordinate stored internally as decimal degrees.

    The constructor accepts decimal degrees (float or string) **or** NMEA
    DDMM.MMMM / DDDMM.MMMM strings — the format is detected automatically.
    Internally everything is normalised to decimal degrees so arithmetic and
    comparisons are straightforward.

    ``str(coord)`` returns degrees-decimal-minutes, e.g.::

        50°44.20'N 001°18.90'W

    Latitude is formatted with a 2-digit degree field and an N/S suffix;
    longitude uses a 3-digit degree field and an E/W suffix.

    ``coord_a - coord_b`` returns the haversine distance in nautical miles.
    """

    latitude: float = Field(description="Latitude in decimal degrees (-90 to 90)")
    longitude: float = Field(description="Longitude in decimal degrees (-180 to 180)")

    @field_validator("latitude", mode="before")
    @classmethod
    def _parse_latitude(cls, v: Any) -> float:
        return _coerce_latitude(v)

    @field_validator("longitude", mode="before")
    @classmethod
    def _parse_longitude(cls, v: Any) -> float:
        return _coerce_longitude(v)

    # ------------------------------------------------------------------
    # Computed / display
    # ------------------------------------------------------------------

    @computed_field
    @property
    def ddm(self) -> str:
        """Degrees-decimal-minutes string, e.g. ``50°44.20'N 001°18.90'W``."""
        return str(self)

    def __str__(self) -> str:
        lat_part = _format_ddm(self.latitude, is_lat=True)
        lon_part = _format_ddm(self.longitude, is_lat=False)
        return f"{lat_part} {lon_part}"

    def __repr__(self) -> str:
        return f"Coordinate(lat={self.latitude:.6f}, lon={self.longitude:.6f})"

    # ------------------------------------------------------------------
    # Arithmetic
    # ------------------------------------------------------------------

    def __sub__(self, other: Coordinate) -> float:
        """Return the haversine distance to *other* in nautical miles."""
        return haversine(
            latitude_start=self.latitude,
            latitude_end=other.latitude,
            longitude_start=self.longitude,
            longitude_end=other.longitude,
        )
