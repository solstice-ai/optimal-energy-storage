import pandas as pd
import numpy as np

from oes import BatteryModel, DynamicProgramController


class SpotPriceArbitrageOptimalController(DynamicProgramController):
    """ Battery controller for optimal spot price arbitrage. """

    def __init__(self, params: dict = {}, debug: bool = False) -> None:
        super().__init__(name="SpotPriceArbitrageOptimalController", params=params, debug=debug)

    def solve(self, scenario: pd.DataFrame, battery: BatteryModel) -> pd.DataFrame:
        """ See parent AbstractBatteryController class for parameter descriptions """

        # Finding the optimal times to charge and discharge in response to tariffs is basically no different
        # than finding the optimal battery profile for a scenario in which demand and generation are zero

        scenario_copy = scenario.copy()
        scenario_copy['demand'] = [0] * len(scenario_copy.index)
        scenario_copy['generation'] = [0] * len(scenario_copy.index)

        return super().solve(scenario_copy, battery)
