from functools import lru_cache
from pathlib import Path

from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings, SettingsConfigDict

from src.kelder_api.components.velocity.models import CalculationType

model_config = SettingsConfigDict(
    env_file=str(Path(__file__).resolve().parent.parent.parent.parent / ".env"),
    env_file_encoding="utf-8",
    extra="allow",
)


class SleepTimes(BaseSettings):
    UNDER_WAY_SLEEP: float = Field(
        description="Seconds between samples, when sailing + 1 second for reading ~ 6 seconds",
        default=1,
    )
    STATIONARY_SLEEP: float = Field(
        description="Seconds between samples, when stationary + 1 second for reading ~ 6 seconds",
        default=5,
    )

    model_config = model_config


class Redis(BaseSettings):
    redis_host: str = Field(
        description="The host name of the redis client", default="localhost"
    )
    redis_port: int = Field(description="Redis port name", default=6379)

    model_config = model_config


class GPS(BaseSettings):
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

    model_config = model_config


class Velocity(BaseSettings):
    velocity_calculation_type: CalculationType = Field(
        description="Method of retrieving GPS history in the velocity calculation",
        default=CalculationType.TIMESERIES,
    )
    gps_velocity_history: int = Field(
        description="Number of GPS measurements or number of seconds since now to average over in a velocity calculation",
        default=2,
    )
    max_velocity_temporal_change: int = Field(
        description="Maximum seconds between GPS measurements to give for a velocity measurement",
        default=15,
    )
    max_delay_seconds: int = Field(
        description="Maximum latency between a gps measurement without a quality warning",
        default=200,
    )

    model_config = model_config


class LogTracker(BaseSettings):
    time_window_length: int = Field(
        description="The number of gps history measurements to retrieve in the log calculation, or seconds history",
        default=60,
    )
    tack_bearing_tolerance: int = Field(
        description="The bearing tolerance before a new tack is calculated", default=15
    )


class Compass(BaseSettings):
    # TODO: remove?
    model_config = model_config


class Orchestrator(BaseSettings):
    sog_threshold: float = Field(
        description="The >= speed over ground which sets the VesselState as underway",
        default=0.2,
    )

    model_config = model_config


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
    velocity: Velocity = Field(
        description="Velocity settings", default_factory=Velocity
    )
    orchestrator: Orchestrator = Field(
        description="The background ochestrator settings", default_factory=Orchestrator
    )
    log_tracker: LogTracker = Field(
        description="All log tracking config", default_factory=LogTracker
    )


@lru_cache(maxsize=1)
def get_settings():
    return Settings()
