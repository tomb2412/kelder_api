from typing import List, Dict

from src.kelder_api.components.redis_client.redis_client import RedisClient
from src.kelder_api.components.background_ochestractor.enums import VesselState


class StationaryStrategy:
    """
    A logic flow determinging the sensing and calculating performed each iteration
    which is implemented when the boat is read stationary.

    Operations are not always computable! - GPS and Velocity
    """

    def required_sensors(self) -> List[str]:
        """Defines which sensors are processed and in what order"""
        return ["GPS"]

    def required_calculators(self) -> List[str]:
        """Defines which calcuations are required and in what order"""
        return ["VELOCITY"]

    async def execute(self, components: Dict[str, dict]) -> None:
        for sensor in self.required_sensors():
            await getattr(
                components[sensor]["instance"], components[sensor]["method"]
            )()

        for calculator in self.required_calculators():
            await getattr(
                components[sensor]["instance"], components[sensor]["method"]
            )()
