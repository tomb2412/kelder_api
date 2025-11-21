import asyncio
import logging
from typing import Dict, List

from src.kelder_api.components.background_orchestrator.enums import VesselState

logger = logging.getLogger(__name__)


class StationaryStrategy:
    """
    A logic flow determinging the sensing and calculating performed each iteration
    which is implemented when the boat is read stationary.

    Operations are not always computable! - GPS and Velocity
    """

    def required_sensors() -> List[str]:
        """Defines which sensors are processed and in what order"""
        return ["GPS", "BILGE_DEPTH"]

    def required_calculators() -> List[str]:
        """Defines which calcuations are required and in what order"""
        return ["VELOCITY"]

    @classmethod
    async def execute(
        self,
        components: Dict[str, dict],
        previous_vessel_state: VesselState,
        sleep_time: int,
    ) -> None:
        for sensor in self.required_sensors():
            try:
                await getattr(
                    components[sensor]["instance"], components[sensor]["method"]
                )()
            except Exception as error:
                logger.error(
                    f"Exception occured processing {sensor}: {error}", exc_info=True
                )

        for calculator in self.required_calculators():
            try:
                await getattr(
                    components[calculator]["instance"], components[calculator]["method"]
                )()
            except Exception as error:
                logger.error(
                    f"Exception occured processing {calculator}: {error}", exc_info=True
                )

        if previous_vessel_state == VesselState.UNDERWAY:
            logger.info("Journey finishing")
            await components["LOG"]["instance"].finish_journey()

        await asyncio.sleep(sleep_time)
