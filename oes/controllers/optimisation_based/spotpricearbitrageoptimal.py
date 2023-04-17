import pandas as pd
import numpy as np

from oes.controllers.optimisation_based.dynamicprogram import DynamicProgram
import oes.util.general as utility


class SpotPriceArbitrageOptimal(DynamicProgram):
    """
    Battery controller for optimal spot price arbitrage.
    """

    def __init__(self, params=None, debug=False):
        super().__init__(name="SpotPriceArbitrageOptimalController", params=params, debug=debug)

    def solve(self, scenario, battery):
        """
        Determine charge / discharge rates and resulting battery soc for every interval in the horizon
        :param scenario: <pandas dataframe> consisting of:
                            - index: pandas Timestamps
                            - column 'generation': forecasted solar generation in W
                            - column 'demand': forecasted demand in W
                            - column 'tariff_import': forecasted cost of importing electricity in $
                            - column 'tariff_export': forecasted reward for exporting electricity in $
        :param battery: <battery model>
        :return: dataframe consisting of:
                    - index: pandas Timestamps
                    - 'charge_rate': float indicating charging rate for this interval in W
                    - 'soc': float indicating resulting state of charge
        """

        # Finding the optimal times to charge and discharge in response to tariffs is basically no different
        # than finding the optimal battery profile for a scenario in which demand and generation are zero

        scenario_copy = scenario.copy()
        scenario_copy['demand'] = [0] * len(scenario_copy.index)
        scenario_copy['generation'] = [0] * len(scenario_copy.index)

        return super().solve(scenario_copy, battery)

