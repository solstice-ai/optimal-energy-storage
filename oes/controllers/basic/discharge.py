import pandas as pd
import sys

from oes.controllers.abstract_battery_controller import BatteryController
import oes.util.utility as utility


class DischargeController(BatteryController):
    """
    Battery controller that discharges battery at a static rate
    """

    def __init__(self, params: dict = {}) -> None:
        super().__init__(name="DischargeController", params=params)

        # Set default discharge rate to be maximum possible
        self.discharge_rate = sys.float_info.max

        # Update all params with those that were passed in
        self.update_params(params)

    def solve(self, scenario, battery):
        """ See parent BatteryController class for parameter descriptions """
        super().solve(scenario, battery)

        # Keep track of relevant values
        current_soc = battery.soc
        all_soc = [current_soc]
        all_charge_rates = [0.0]

        # Find max discharge rate and convert to negative
        max_discharge_rate = -1 * min(self.discharge_rate, battery.max_discharge_rate)

        # Iterate from 2nd row onwards
        for index, row in scenario.iloc[1:].iterrows():

            charge_rate = max_discharge_rate

            # Ensure charge rate is feasible
            if self.constrain_charge_rate:
                charge_rate = utility.feasible_charge_rate(charge_rate,
                                                           current_soc,
                                                           battery,
                                                           self.interval_size_in_hours)

            # Update running variables
            all_charge_rates.append(charge_rate)
            all_soc.append(current_soc)
            current_soc = current_soc + utility.chargerate_to_soc(charge_rate,
                                                                  battery.capacity,
                                                                  self.interval_size_in_hours)

        return pd.DataFrame(data={
            'timestamp': scenario.index,
            'charge_rate': all_charge_rates,
            'soc': all_soc
        }).set_index('timestamp')
