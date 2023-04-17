import pandas as pd
import sys

from oes import BatteryModel, AbstractBatteryController


class ChargeController(AbstractBatteryController):
    """ Basic battery controller that only charges battery at a static rate """

    def __init__(self, params: dict = {}) -> None:
        super().__init__(name='ChargeController', params=params)

        # Set default charge rate to be maximum possible
        self.charge_rate = sys.float_info.max

        # Update all params with those that were passed in
        self.update_params(params)

    def solve_one_interval(self, scenario_interval: pd.DataFrame) -> float:
        """ See parent AbstractBatteryController class for parameter descriptions """
        return self.charge_rate

    def solve(self, scenario: pd.DataFrame, battery: BatteryModel) -> pd.DataFrame:
        """ See parent AbstractBatteryController class for parameter descriptions """

        # Ensure charge rate does not exceed battery maximum allowed charge rate
        self.charge_rate = min(self.charge_rate, battery.max_charge_rate)

        return super().solve(scenario, battery)
