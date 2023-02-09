import pandas as pd
import numpy as np

from oes.controllers.abstract_battery_controller import BatteryController
import oes.util.utility as utility


class SpotPriceArbitrageNaive(BatteryController):
    """
    Battery controller for naive spot price arbitrage.

    There are subtle differences between spot price arbitrage, tariff optimisation, and market participation:

    - spot price arbitrage: Assumes that both import and export tariff represent whole sale market price (plus maybe
      a network charge).  It takes the average of max export, min import, and discharges when below, charges when
      above.  It ignores demand and generation.

    - tariff optimisation: if import tariff is higher than average, discharge to meet demand

    - market participation:  Assumes normal residential tariff structure, and only occasional market price spikes.
      If reward for export is higher than lowest price for import, discharge to grid.
      Else if price is low now is a good time to charge.  Otherwise do nothing.
    """

    def __init__(self, params=None):
        super().__init__(name="MarketParticipationController", params=params)

    @staticmethod
    def solve_one_interval(scenario_interval, battery, current_soc, controller_params, constrain_charge_rate):

        import_threshold = controller_params['import_threshold']
        export_threshold = controller_params['export_threshold']
        arbitrage_mean = export_threshold + (import_threshold - export_threshold) / 2

        # # If spot price is high, discharge
        # if scenario_interval['tariff_import'] > import_threshold:
        #     charge_rate = -1 * battery.params['max_discharge_rate']
        #
        # # Else if spot price is low, charge
        # elif scenario_interval['tariff_export'] < export_threshold:
        #     charge_rate = battery.params['max_charge_rate']
        #
        # # otherwise do nothing
        # else:
        #     charge_rate = 0

        if scenario_interval['tariff_import'] < arbitrage_mean:
            charge_rate = battery.params['max_charge_rate']
        elif scenario_interval['tariff_export'] > arbitrage_mean:
            charge_rate = -1 * battery.params['max_discharge_rate']
        else:
            charge_rate = 0

        # Ensure charge rate is feasible
        if constrain_charge_rate:
            charge_rate = utility.feasible_charge_rate(charge_rate,
                                                       current_soc,
                                                       battery,
                                                       controller_params['time_interval_in_hours'])
        return charge_rate

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

        # TODO Pass more generic params to all battery controllers

        # Keep track of relevant values
        current_soc = battery.params['current_soc']
        all_soc = []  # [current_soc]
        all_charge_rates = []  # [0]

        # Determine import and export thresholds
        # threshold_percentile = 0.5
        # import_threshold = scenario['tariff_import'].min() + \
        #                    threshold_percentile * (scenario['tariff_import'].max() - scenario['tariff_import'].min())
        # export_threshold = scenario['tariff_export'].max() - \
        #                    threshold_percentile * (scenario['tariff_export'].max() - scenario['tariff_export'].min())

        # print(import_threshold, export_threshold)

        import_threshold = scenario['tariff_export'].max()
        export_threshold = scenario['tariff_import'].min()

        # Utility variables
        controller_params = {
            'time_interval_in_hours': self.time_interval_in_hours,
            'import_threshold': import_threshold,
            'export_threshold': export_threshold,
        }

        # Iterate from 2nd row onwards
        for index, row in scenario.iterrows():  # scenario.iloc[1:].iterrows():

            charge_rate = self.solve_one_interval(row, battery, current_soc, controller_params, constrain_charge_rate)

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
