import pandas as pd

from oes.controllers.abstract_battery_controller import BatteryController


class DoNothingController(BatteryController):
    """
    Controller that does nothing.  Battery does not charge or discharge.
    (This is useful e.g. as baseline for comparison, or to build up a scheduler)
    """

    def __init__(self, params: dict = {}) -> None:
        super().__init__(name="DoNothing", params=params)

        # Update all params with those that were passed in
        self.update_params(params)

    def solve(self, scenario, battery):
        """ See parent BatteryController class for parameter descriptions """
        super().solve(scenario, battery)

        all_soc = [battery.soc] * len(scenario.index)
        all_charge_rates = [0] * len(scenario.index)

        return pd.DataFrame(data={
            'timestamp': scenario.index,
            'charge_rate': all_charge_rates,
            'soc': all_soc
        }).set_index('timestamp')
