import pandas as pd

from oes import BatteryModel, AbstractBatteryController


class SolarSelfConsumption(AbstractBatteryController):
    """
    Battery controller for solar self consumption: charge rate is generation minus demand.
    In other words, when there is more generation than demand, charge with the excess generation;
    when there is more demand, discharge to meet this.
    """

    def __init__(self, params: dict = {}) -> None:
        super().__init__(name="SolarSelfConsumptionController", params=params)

        # Update all params with those that were passed in
        self.update_params(params)

    def solve_one_interval(self, scenario_interval: pd.DataFrame) -> float:
        """ See parent AbstractBatteryController class for parameter descriptions """
        return scenario_interval['generation'] - scenario_interval['demand']

    def solve(self, scenario: pd.DataFrame, battery: BatteryModel) -> pd.DataFrame:
        """ See parent AbstractBatteryController class for parameter descriptions """
        return super().solve(scenario, battery)

