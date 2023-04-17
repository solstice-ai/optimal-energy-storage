import pandas as pd

import oes.util.conversions
from oes.controllers.abstract_battery_controller import AbstractBatteryController
import oes.util.general as utility


class SolarSelfConsumption(AbstractBatteryController):
    """
    Battery controller for solar self consumption
    """

    def __init__(self, params: dict = {}) -> None:
        super().__init__(name="SolarSelfConsumptionController", params=params)

    def solve_one_interval(self, scenario_interval, battery, current_soc, controller_params):
        # Solar self consumption: charge with any excess solar / discharge to meet any excess demand
        charge_rate = scenario_interval['generation'] - scenario_interval['demand']

        # Ensure charge rate is feasible
        if self.params['constrain_charge_rate']:
            charge_rate = utility.feasible_charge_rate(charge_rate,
                                                       current_soc,
                                                       battery,
                                                       controller_params['time_interval_in_hours'])

        return charge_rate

    def solve(self, scenario, battery):
        """ See parent AbstractBatteryController class for parameter descriptions """
        super().solve(scenario, battery)

        # Keep track of relevant values
        current_soc = battery.soc
        all_soc = []  # [current_soc]
        all_charge_rates = []  # [0]

        controller_params = {'time_interval_in_hours': self.time_interval_in_hours}

        # Iterate from 2nd row onwards
        for index, row in scenario.iterrows():  # scenario.iloc[1:].iterrows():

            charge_rate = self.solve_one_interval(row, battery, current_soc, controller_params)

            # Update running variables
            all_charge_rates.append(charge_rate)
            all_soc.append(current_soc)
            current_soc = current_soc + oes.util.conversions.charge_rate_to_soc(charge_rate,
                                                                                battery.params['capacity'],
                                                                                self.time_interval_in_hours)

        return pd.DataFrame(data={
            'timestamp': scenario.index,
            'charge_rate': all_charge_rates,
            'soc': all_soc
        }).set_index('timestamp')
