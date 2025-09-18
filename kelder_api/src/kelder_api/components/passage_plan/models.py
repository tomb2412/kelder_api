from pydantic import BaseModel, Field
from typing import List, Optional
from datetime import datetime


class TideInfo(BaseModel):
    high_water: str = Field(..., description="High water times and heights (UTC)")
    low_water: str = Field(..., description="Low water times and heights (UTC)")
    streams: Optional[str] = Field(
        None, description="Tidal stream directions, rates, and timings"
    )


class WeatherInfo(BaseModel):
    wind: str = Field(..., description="Wind direction and strength")
    visibility: str = Field(..., description="Visibility forecast")
    sea_state: Optional[str] = Field(None, description="Sea state description")


class Waypoint(BaseModel):
    name: Optional[str] = Field(None, description="Name of the waypoint")
    coordinates: str = Field(
        ...,
        description="Lat/Long in degrees and minutes (e.g. '50°46.0’N, 001°06.0’W')",
    )
    # TODO: Calculate these, with some validation - maybe a tool?
    # bearing: Optional[str] = Field(None, description="Bearing in degrees true")
    # distance_nm: Optional[float] = Field(None, description="Distance in nautical miles")
    # eta: Optional[str] = Field(None, description="Estimated time of arrival (UTC or local)")


class PilotageInfo(BaseModel):
    departure: str = Field(..., description="Pilotage notes for departure harbour")
    arrival: str = Field(..., description="Pilotage notes for arrival harbour")


class PortOfRefuge(BaseModel):
    name: str = Field(..., description="Port name")
    coordinates: str = Field(..., description="Lat/Long coordinates")


class DepartureETA(BaseModel):
    departure_time: str = Field(..., description="Planned departure time")
    eta: str = Field(..., description="Estimated time of arrival")
    justification: Optional[str] = Field(
        None, description="Reasoning (tidal gate, daylight, etc.)"
    )


class PassagePlan(BaseModel):
    timestamp: datetime = Field(
        description="The timestamp the passage plan was created"
    )
    title: str = Field(
        ..., description="Title of the passage plan, e.g. 'Cowes to Plymouth'"
    )
    tides: TideInfo
    weather: WeatherInfo
    course_to_steer: List[Waypoint] = Field(
        ..., description="List of waypoints forming the course to steer"
    )
    pilotage: PilotageInfo
    ports_of_refuge: Optional[List[PortOfRefuge]] = Field(
        default_factory=list,
        description="Alternative harbours or ports along the route",
    )
    navigational_hazards: List[str] = Field(..., description="Hazards along the route")
    departure_and_eta: DepartureETA
