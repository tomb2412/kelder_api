from typing import List, Dict


class UnderwayStrategy:
    """
    A logic flow determinging the sensing and calculating performed each iteration
    which is implemented when the boat is underway.

    Operations are not always computable! - GPS and Velocity
    """

    def required_sensors(self) -> List[str]:
        """Defines which sensors are processed and in what order"""
        return ["GPS", "COMPASS"]

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
                components[calculator]["instance"], components[calculator]["method"]
            )()
