import logging
from typing import Dict, List
import asyncio

from src.kelder_api.components.background_orchestrator.enums import VesselState

logger = logging.getLogger(__name__)


class UnderwayStrategy:
    """
    A logic flow determinging the sensing and calculating performed each iteration
    which is implemented when the boat is underway.

    Operations are not always computable! - GPS and Velocity
    """

    def required_sensors() -> List[str]:
        """Defines which sensors are processed and in what order"""
        return ["GPS", "COMPASS"]

    def required_calculators() -> List[str]:
        """Defines which calcuations are required and in what order"""
        return ["VELOCITY", "LOG"]

    @classmethod
    async def execute(
        self, components: Dict[str, dict], previous_vessel_state: VesselState
    ) -> None:
        for sensor in self.required_sensors():
            await getattr(
                components[sensor]["instance"], components[sensor]["method"]
            )()

        for calculator in self.required_calculators():
            await getattr(
                components[calculator]["instance"], components[calculator]["method"]
            )()

        if previous_vessel_state == VesselState.STATIONARY:
            logger.info("Journey finishing")
            await components["LOG"]["instance"].finish_journey()

        await asyncio.sleep(5)