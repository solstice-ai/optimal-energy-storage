import pandas as pd
import sys
from oes.battery.battery_model import BatteryModel
from oes.controllers.abstract_battery_controller import AbstractBatteryController


class DischargeController(AbstractBatteryController):
    """ Basic battery controller that only discharges battery at a static rate """

    def __init__(self, params: dict = {}, battery_model: BatteryModel = None, debug: bool = False):
        super().__init__(name=self.__class__.__name__, params=params, battery_model=battery_model, debug=debug)

        # Set default discharge rate to be maximum possible
        self.discharge_rate = sys.float_info.max

        # Update all params with those that were passed in
        self.update_params(params)

    def solve_one_interval(self, scenario_interval: pd.DataFrame) -> float:
        """ See parent AbstractBatteryController class for parameter descriptions """
        return -1 * self.discharge_rate

    def solve(self, scenario: pd.DataFrame) -> pd.DataFrame:
        """ See parent AbstractBatteryController class for parameter descriptions """

        # Ensure discharge rate does not exceed battery maximum allowed discharge rate
        self.discharge_rate = min(self.discharge_rate, self.battery.max_discharge_rate)

        return super().solve(scenario)
