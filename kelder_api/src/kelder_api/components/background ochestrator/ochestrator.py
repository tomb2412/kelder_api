from src.kelder_api.configuration.settings import get_settings
from src.kelder_api.components.redis_client.redis_client import RedisClient
from src.kelder_api.components.gps_new.interface import GPSInterface
from src.kelder_api.components.compass_new.interface import CompassInterface
from src.kelder_api.components.velocity.service import VelocityCalculator
from src.kelder_api.components.background_ochestractor.stationary_strategy import (
    SationaryStrategy,
)
from src.kelder_api.components.background_ochestractor.stationary_strategy import (
    UnderwayStrategy,
)
from src.kelder_api.components.background_ochestractor.enums import VesselState


class BackgroundTaskManager:
    """Task manager to sequence sensor measurements and calculations."""

    def __init__(self):
        """Initialisation of the sensors and components"""
        self.redis_client = RedisClient()

        # Initialise components and their writing functions
        self.components = self.register_components()

        self.strategies = {
            VesselState.UNDERWAY: UnderwayStrategy,
            VesselState.STATIONARY: SationaryStrategy,
            # TODO: add other strategies like achored, moored, motoring
        }

        self.settings = get_settings().ochestrator

    def register_components(self):
        # Initialise sensors
        gps_interface = GPSInterface(self.redis_client)
        compass_interface = CompassInterface(self.redis_client)

        # Initialise velocity which i
        velocity_calculator = VelocityCalculator(
            gps_interface=gps_interface, redis_client=self.redis_client
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
        }

    async def calculate_new_state(self) -> VesselState:
        """A general method to define the vessels new state each iteration"""
        velocity = self.components["VELOCITY"].read_velocity_latest(active=True)

        if velocity.speed_over_ground >= self.settings.sog_threshold:
            return VesselState.UNDERWAY
        else:
            return VesselState.STATIONARY

    async def run(self):
        vessel_state = VesselState.STATIONARY
        while True:
            # Run the strategy matching the vessel state
            # previous_vessel_state = vessel_state
            await self.strategies[vessel_state].execute(self.components)

            vessel_state = self.calculate_new_state()

            # Logic triggered when vessel changes state: record trip, save trip ect
