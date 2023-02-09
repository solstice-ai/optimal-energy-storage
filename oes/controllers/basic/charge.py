import pandas as pd
import sys

from oes.controllers.abstract_battery_controller import BatteryController
import oes.util.utility as utility


class Charge(BatteryController):
    """
    Battery controller that only charges battery
    """

    def __init__(self, params=None):
        super().__init__(name="ChargeController", params=params)

        # Set default charge rate to be maximum possible
        if 'charge_rate' not in self.params:
            self.params['charge_rate'] = sys.float_info.max

    def solve(self, scenario, battery, constrain_charge_rate=True):
        """
        Determine charge / discharge rates and resulting battery soc for every interval in the horizon
        :param scenario: <pandas dataframe> consisting of:
                            - index: pandas Timestamps
                            - column 'generation': forecasted solar generation in W
                            - column 'demand': forecasted demand in W
                            - column 'tariff_import': forecasted cost of importing electricity in $
                            - column 'tariff_export': forecasted reward for exporting electricity in $
        :param battery: <battery model>
        :param constrain_charge_rate: <bool>, whether to ensure that charge rate is feasible within battery constraints
        :return: dataframe consisting of:
                    - index: pandas Timestamps
                    - 'charge_rate': float indicating charging rate for this interval in W
                    - 'soc': float indicating resulting state of charge
        """
        super().solve(scenario, battery, constrain_charge_rate=constrain_charge_rate)

        # Keep track of relevant values
        current_soc = battery.params['current_soc']
        all_soc = [current_soc]
        all_charge_rates = [0]

        # Find max charge rate
        max_charge_rate = min(self.params['charge_rate'], battery.params['max_charge_rate'])

        # Iterate from 2nd row onwards
        for index, row in scenario.iloc[1:].iterrows():

            charge_rate = max_charge_rate

            # Ensure charge rate is feasible
            if constrain_charge_rate:
                charge_rate = utility.feasible_charge_rate(charge_rate,
                                                           current_soc,
                                                           battery,
                                                           self.time_interval_in_hours)

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
