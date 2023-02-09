import pandas as pd

from oes.controllers.abstract_battery_controller import BatteryController


class DoNothing(BatteryController):
    """
    Controller that does nothing.  Battery does not charge or discharge.
    (This is useful e.g. as baseline for comparison, or to build up a scheduler)
    """

    def __init__(self, params=None):
        super().__init__(name="DoNothing", params=params)

    @staticmethod
    def solve_one_interval(scenario_interval, battery, current_soc, controller_params, constrain_charge_rate):
        return 0

    def solve(self, scenario, battery, constrain_charge_rate=True):
        """
        Determine charge / discharge rates and resulting battery soc for every interval in the horizon
        :param scenario: <pandas dataframe> consisting of:
                            - index: pandas Timestamps
                            - column 'generation': forecasted solar generation in W
                            - column 'demand': forecasted demand in W
                            - column 'tariff_import': forecasted cost of importing electricity in $
        :param battery: <battery model>
        :param constrain_charge_rate: <bool>, whether to ensure that charge rate is feasible within battery constraints
        :return: dataframe consisting of:
                    - index: pandas Timestamps
                    - 'charge_rate': float indicating charging rate for this interval in W
                    - 'soc': float indicating resulting state of charge
        """
        super().solve(scenario, battery, constrain_charge_rate)

        starting_soc = battery.params['current_soc']
        all_soc = [starting_soc] * len(scenario.index)
        all_charge_rates = [0] * len(scenario.index)

        return pd.DataFrame(data={
            'timestamp': scenario.index,
            'charge_rate': all_charge_rates,
            'soc': all_soc
        }).set_index('timestamp')
