import pandas as pd
from oes.battery.battery import AbstractBattery
from oes.controllers.abstract_battery_controller import AbstractBatteryController


class DoNothingController(AbstractBatteryController):
    """
    Controller that does nothing.  Battery does not charge or discharge.
    (This is useful e.g. as baseline for comparison, or to build up a scheduler)
    """

    def __init__(self, params: dict = {}, battery: AbstractBattery = None, debug: bool = False):
        super().__init__(name=self.__class__.__name__, battery=battery, debug=debug)

        # Update all params with those that were passed in
        self.update_params(params)

    def solve_one_interval(self, scenario_interval: pd.DataFrame) -> float:
        """ See parent AbstractBatteryController class for parameter descriptions """
        return 0.0

    def solve(self, scenario: pd.DataFrame) -> pd.DataFrame:
        """ See parent AbstractBatteryController class for parameter descriptions """
        return super().solve(scenario)
