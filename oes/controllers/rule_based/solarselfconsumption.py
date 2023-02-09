import pandas as pd

from oes.controllers.abstract_battery_controller import BatteryController
import oes.util.utility as utility


class SolarSelfConsumption(BatteryController):
    """
    Battery controller for solar self consumption
    """

    def __init__(self, params=None):
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
        super().solve(scenario, battery)

        # Keep track of relevant values
        current_soc = battery.params['current_soc']
        all_soc = []  # [current_soc]
        all_charge_rates = []  # [0]

        controller_params = {
            'time_interval_in_hours': self.time_interval_in_hours,
        }

        # Iterate from 2nd row onwards
        for index, row in scenario.iterrows():  # scenario.iloc[1:].iterrows():

            charge_rate = self.solve_one_interval(row, battery, current_soc, controller_params)

            # Update running variables
            all_charge_rates.append(charge_rate)
            all_soc.append(current_soc)
            current_soc = current_soc + utility.chargerate_to_soc(charge_rate,
                                                                  battery.params['capacity'],
                                                                  self.time_interval_in_hours)

        return pd.DataFrame(data={
            'timestamp': scenario.index,
            'charge_rate': all_charge_rates,
            'soc': all_soc
        }).set_index('timestamp')
