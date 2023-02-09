import pandas as pd

from oes.controllers.abstract_battery_controller import BatteryController


class DoNothing(BatteryController):
    """
    Controller that does nothing.  Battery does not charge or discharge.
    (This is useful e.g. as baseline for comparison, or to build up a scheduler)
    """

    def __init__(self, params=None):
        super().__init__(name="DoNothing", params=params)

    def solve(self, scenario, battery):
        """
        Determine charge / discharge rates and resulting battery soc for every interval in the horizon
        :param scenario: <pandas dataframe> consisting of:
                            - index: pandas Timestamps
                            - column 'generation': forecasted solar generation in W
                            - column 'demand': forecasted demand in W
                            - column 'tariff_import': forecasted cost of importing electricity in $
        :param battery: <battery model>
        :return: dataframe consisting of:
                    - index: pandas Timestamps
                    - 'charge_rate': float indicating charging rate for this interval in W
                    - 'soc': float indicating resulting state of charge
        """
        super().solve(scenario, battery)

        starting_soc = battery.params['current_soc']
        all_soc = [starting_soc] * len(scenario.index)
        all_charge_rates = [0] * len(scenario.index)

        return pd.DataFrame(data={
            'timestamp': scenario.index,
            'charge_rate': all_charge_rates,
            'soc': all_soc
        }).set_index('timestamp')
