from pydantic import BaseModel, computed_field, Field

class gpsCoords(BaseModel):
    lat: float = Field(description="Latitude")
    long: float = Field(description="Longitude")