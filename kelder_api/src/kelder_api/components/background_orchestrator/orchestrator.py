import logging

from src.kelder_api.components.background_orchestrator.enums import VesselState, VesselStateModel
from src.kelder_api.components.background_orchestrator.stationary_strategy import (
    StationaryStrategy,
)
from src.kelder_api.components.background_orchestrator.underway_strategy import (
    UnderwayStrategy,
)
from src.kelder_api.components.background_orchestrator.simulator import Simulator
from src.kelder_api.components.compass_new.interface import CompassInterface
from src.kelder_api.components.db_manager.service import DBManager
from src.kelder_api.components.drift_calculator.serivce import DriftCalculator
from src.kelder_api.components.gps_new.interface import GPSInterface
from src.kelder_api.components.log.service import LogTracker
from src.kelder_api.components.redis_client.redis_client import RedisClient
from src.kelder_api.components.ultrasound.service import BilgeDepthSensor
from src.kelder_api.components.velocity.service import VelocityCalculator
from src.kelder_api.configuration.settings import get_settings

logger = logging.getLogger(__name__)


class BackgroundTaskManager:
    """Task manager to sequence sensor measurements and calculations."""

    def __init__(self):
        """Initialisation of the sensors and components"""
        logger.info("Initialising background task manager components")

        self.settings = get_settings().orchestrator
        self.UNDER_WAY_SLEEP = get_settings().sleep_times.UNDER_WAY_SLEEP
        self.STATIONARY_SLEEP = get_settings().sleep_times.STATIONARY_SLEEP
        self.sleep_time = self.STATIONARY_SLEEP

        self.redis_client = RedisClient()

        # Initialise components and their writing functions
        self.components = self.register_components()

        self.strategies = {
            VesselState.UNDERWAY: UnderwayStrategy.execute,
            VesselState.STATIONARY: StationaryStrategy.execute,
        }

    def register_components(self):
        # Initialise sensors
        if not self.settings.run_simulator:
            gps_interface = GPSInterface(self.redis_client)
            gps_method = "stream_serial_data"
            compass_interface = CompassInterface(self.redis_client)
            compass_method = "read_heading_from_compass"
            bilge_depth_sensor = BilgeDepthSensor(self.redis_client)
            bilge_depth_sensor_method = "record_bilge_depth"
        else:
            self.simulator = Simulator(
                redis_client = self.redis_client,
                simulation_file_name = "straight_line"
                )
            gps_interface = self.simulator
            gps_method = "simulate_gps_sensor"
            compass_interface = self.simulator
            compass_method = "simulate_compass_sensor"
            bilge_depth_sensor = self.simulator
            bilge_depth_sensor_method = "simulate_ultrasound_sensor"

        # Initialise velocity which i
        velocity_calculator = VelocityCalculator(
            gps_interface=gps_interface, redis_client=self.redis_client
        )

        db_manager = DBManager()
        log_tracker = LogTracker(
            gps_interface=gps_interface,
            redis_client=self.redis_client,
            velocity_calculator=velocity_calculator,
            db_manager=db_manager,
        )

        drift_calculator = DriftCalculator(
            redis_client=self.redis_client,
            velocity_calculator=velocity_calculator,
            compass_interface=compass_interface,
        )

        components = {
            "GPS": {"instance": gps_interface, "method": gps_method},
            "COMPASS": {
                "instance": compass_interface,
                "method": compass_method,
            },
            "BILGE_DEPTH": {
                "instance": bilge_depth_sensor,
                "method": bilge_depth_sensor_method,
            },
            "VELOCITY": {
                "instance": velocity_calculator,
                "method": "calculate_gps_velocity",
            },
            "LOG": {
                "instance": log_tracker,
                "method": "increment_log",
            },
            "DRIFT": {
                "instance": drift_calculator,
                "method": "instantaneous_drift_calculator",
            },
        }

        logger.debug("Registered orchestrator components: %s", list(components.keys()))
        return components

    async def calculate_new_state(self, vessel_state: VesselState) -> VesselState:
        """A general method to define the vessels new state each iteration"""
        velocity = await self.components["VELOCITY"]["instance"].read_velocity_latest(
            active=True
        )
        try:
            if velocity.speed_over_ground >= self.settings.sog_threshold:
                self.sleep_time = self.UNDER_WAY_SLEEP
                return VesselState.UNDERWAY
            else:
                self.sleep_time = self.STATIONARY_SLEEP
                return VesselState.STATIONARY
        except Exception:
            logger.exception(
                "Failed to calculate vessel state, preserving %s", vessel_state
            )
            return vessel_state

    async def run(self):
        if self.simulator:
            await self.simulator.clear_redis()

        self.vessel_state = VesselState.STATIONARY
        await self.write_vessel_state()
        while True:
            logger.info("Current vessel state: %s", self.vessel_state)
            previous_vessel_state = self.vessel_state
            # Run the strategy matching the vessel state
            await self.strategies[self.vessel_state](
                components=self.components,
                previous_vessel_state=previous_vessel_state,
                sleep_time=self.sleep_time
            )

            self.vessel_state = await self.calculate_new_state(self.vessel_state)
            if self.vessel_state != previous_vessel_state:
                logger.info(
                    "Vessel state change detected: %s -> %s",
                    previous_vessel_state,
                    self.vessel_state,
                )

    async def write_vessel_state(self) -> None:
        logger.info(f"Writing the vessel state to redis: {self.vessel_state.value}")
        async with self.redis_client.get_connection() as redis:
            await redis.delete(f"sensor:ts:VESSEL_STATE")
        await self.redis_client.write_set(
            "VESSEL_STATE",
            VesselStateModel(
                vessel_state = self.vessel_state
        ))

    async def read_vessel_state(self) -> VesselState | None:
        try:
            return (await self.redis_client.read_set("VESSEL_STATE"))[0].vessel_state
        except IndexError:
            logger.error("No vessel state data available")
            return None
