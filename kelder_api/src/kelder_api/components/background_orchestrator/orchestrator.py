import logging

from src.kelder_api.components.background_orchestrator.enums import VesselState
from src.kelder_api.components.background_orchestrator.stationary_strategy import (
    StationaryStrategy,
)
from src.kelder_api.components.background_orchestrator.underway_strategy import (
    UnderwayStrategy,
)
from src.kelder_api.components.compass_new.interface import CompassInterface
from src.kelder_api.components.gps_new.interface import GPSInterface
from src.kelder_api.components.log.service import LogTracker
from src.kelder_api.components.redis_client.redis_client import RedisClient
from src.kelder_api.components.velocity.service import VelocityCalculator
from src.kelder_api.configuration.settings import get_settings

logger = logging.getLogger(__name__)


class BackgroundTaskManager:
    """Task manager to sequence sensor measurements and calculations."""

    def __init__(self):
        """Initialisation of the sensors and components"""
        self.redis_client = RedisClient()

        # Initialise components and their writing functions
        self.components = self.register_components()

        self.strategies = {
            VesselState.UNDERWAY: UnderwayStrategy.execute,
            VesselState.STATIONARY: StationaryStrategy.execute,
        }

        self.settings = get_settings().orchestrator

    def register_components(self):
        # Initialise sensors
        gps_interface = GPSInterface(self.redis_client)
        compass_interface = CompassInterface(self.redis_client)

        # Initialise velocity which i
        velocity_calculator = VelocityCalculator(
            gps_interface=gps_interface, redis_client=self.redis_client
        )

        log_tracker = LogTracker(
            gps_interface=gps_interface,
            redis_client=self.redis_client,
            velocity_calculator=velocity_calculator,
        )

        return {
            "GPS": {"instance": gps_interface, "method": "stream_serial_data"},
            "COMPASS": {
                "instance": compass_interface,
                "method": "read_heading_from_compass",
            },
            "VELOCITY": {
                "instance": velocity_calculator,
                "method": "calculate_gps_velocity",
            },
            "LOG": {
                "instance": log_tracker,
                "method": "increment_log",
            },
        }

    async def calculate_new_state(self, vessel_state: VesselState) -> VesselState:
        """A general method to define the vessels new state each iteration"""
        velocity = await self.components["VELOCITY"]["instance"].read_velocity_latest(
            active=True
        )
        try:
            if velocity.speed_over_ground >= self.settings.sog_threshold:
                return VesselState.UNDERWAY
            else:
                return VesselState.STATIONARY
        except Exception:
            return vessel_state

    async def run(self):
        vessel_state = VesselState.STATIONARY
        while True:
            logger.info("Current vessel state: %s" % vessel_state)
            previous_vessel_state = vessel_state
            # Run the strategy matching the vessel state
            await self.strategies[vessel_state](
                components=self.components, previous_vessel_state=previous_vessel_state
            )

            vessel_state = await self.calculate_new_state(vessel_state)
