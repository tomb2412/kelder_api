from pydantic_settings import BaseSettings
from pydantic import BaseModel, Field


class SleepTimes(BaseSettings):
    UNDER_WAY_SLEEP: float = Field(
        description="Seconds between samples, when sailing + 1 second for reading ~ 6 seconds",
        default=1,
    )
    STATIONARY_SLEEP: float = Field(
        description="Seconds between samples, when stationary + 1 second for reading ~ 6 seconds",
        default=5,
    )


class Redis(BaseSettings):
    redis_host: str = Field(
        description="The host name of the redis client", default="localhost"
    )
    redis_port: int = Field(description="Redis port name", default=6379)


class GPS(BaseSettings):
    gps_velocity_history: int = Field(
        description="Number of GPS measurements to average over in a velocity calculation",
        default=10,
    )
    max_velocity_temporal_change: int = Field(
        description="Maximum seconds between GPS measurements to give for a velocity measurement",
        default=15,
    )
    max_delay_seconds: int = Field(
        description="Maximum latency between a gps measurement without a quality warning",
        default=30,
    )

    gps_serial_port: str = Field(
        description="Serial port for the GPS", default="/dev/ttyAMA0"
    )
    gps_baudrate: int = Field(
        description="Baudrate for the GPS transmission", default=9600
    )
    gps_timeout: float = Field(description="UART timeout period", default=1)
    velocity_threshold: float = Field(
        description="speed in kts exceeding to define underway", default=1.5
    )


class Compass(BaseModel):
    pass


class Settings(BaseModel):
    redis: Redis = Field(
        description="Redis server connection config", default_factory=Redis
    )
    sleep_times: SleepTimes = Field(
        description="Sleep times depending on ships motion", default_factory=SleepTimes
    )
    gps: GPS = Field(description="All gps configuration settings", default_factory=GPS)
    compass: Compass = Field(
        description="All compass configuration", default_factory=Compass
    )
