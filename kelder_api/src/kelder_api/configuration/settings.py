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
        description=(
            "Seconds between samples when sailing plus one second for reading "
            "(~6 seconds total)"
        ),
        default=1,
    )
    STATIONARY_SLEEP: float = Field(
        description=(
            "Seconds between samples when stationary plus one second for reading "
            "(~6 seconds total)"
        ),
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

    model_config = model_config


class Velocity(BaseSettings):
    velocity_calculation_type: CalculationType = Field(
        description=(
            "Method used to retrieve GPS history for the velocity calculation"
        ),
        default=CalculationType.TIMESERIES,
    )
    gps_velocity_history: int = Field(
        description=(
            "GPS measurement count or seconds of history used in the velocity "
            "calculation"
        ),
        default=2,
    )
    max_velocity_temporal_change: int = Field(
        description=(
            "Maximum seconds allowed between GPS measurements when producing a "
            "velocity reading"
        ),
        default=15,
    )
    max_delay_seconds: int = Field(
        description=(
            "Maximum latency between GPS measurements before flagging a quality warning"
        ),
        default=200,
    )

    model_config = model_config


class LogTracker(BaseSettings):
    time_window_length: int = Field(
        description=(
            "Number of GPS history measurements or seconds of history used for "
            "log calculations"
        ),
        default=60,
    )
    tack_bearing_tolerance: int = Field(
        description="The bearing tolerance before a new tack is calculated", default=15
    )


class Compass(BaseSettings):
    model_config = model_config


class Orchestrator(BaseSettings):
    sog_threshold: float = Field(
        description=(
            "Speed over ground threshold that sets the vessel state to underway"
        ),
        default=0.5,
    )

    model_config = model_config


class BilgeDepthSettings(BaseSettings):
    max_data_age_minutes: int = Field(
        description="Maximum age (minutes) of bilge depth data before flagging stale",
        default=5,
    )

    model_config = model_config


class Inference(BaseSettings):
    stream_chunk_size: int = Field(
        description="Number of characters per streamed SSE chunk",
        default=10,
    )
    model_config = model_config


class Settings(BaseModel):
    redis: Redis = Field(
        description="Redis server connection config", default_factory=Redis
    )
    sleep_times: SleepTimes = Field(
        description="Sleep times depending on ships motion",
        default_factory=SleepTimes,
    )
    gps: GPS = Field(description="All GPS configuration settings", default_factory=GPS)
    compass: Compass = Field(
        description="All compass configuration", default_factory=Compass
    )
    velocity: Velocity = Field(
        description="Velocity settings", default_factory=Velocity
    )
    orchestrator: Orchestrator = Field(
        description="Background orchestrator settings",
        default_factory=Orchestrator,
    )
    bilge_depth: BilgeDepthSettings = Field(
        description="Bilge depth sensor configuration",
        default_factory=BilgeDepthSettings,
    )
    log_tracker: LogTracker = Field(
        description="All log tracking config", default_factory=LogTracker
    )
    inference: Inference = Field(
        description="Inference service configuration", default_factory=Inference
    )


@lru_cache(maxsize=1)
def get_settings():
    return Settings()
