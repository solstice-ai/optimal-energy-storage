import pandas as pd

import oes.util.conversions
from oes.controllers.abstract_battery_controller import AbstractBatteryController
import oes.util.general as utility


class MarketParticipation(AbstractBatteryController):
    """
    Battery controller for market participation
    """

    def __init__(self, params=None):
        super().__init__(name="MarketParticipationController", params=params)

    def solve_one_interval(self, scenario_interval, battery, current_soc, controller_params):

        tariff_min = controller_params['tariff_min']

        # if reward for export is higher than lowest price for import, discharge to grid
        if (scenario_interval['market_price'] / 1000) > tariff_min:
            charge_rate = -1 * battery.params['max_discharge_rate']

        # else if price is low now is a good time to charge
        elif scenario_interval['tariff_import'] == tariff_min:
            charge_rate = battery.params['max_charge_rate']

        # otherwise do nothing
        else:
            charge_rate = 0

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

        # Utility variables
        controller_params = {
            'time_interval_in_hours': self.time_interval_in_hours,
            'tariff_min': min(scenario['tariff_import'])
        }

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
