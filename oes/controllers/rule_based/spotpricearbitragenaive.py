import pandas as pd

from oes import BatteryModel, AbstractBatteryController


class SpotPriceArbitrageNaive(AbstractBatteryController):
    """
    Battery controller for naive spot price arbitrage:
    Assumes that both import and export tariff represent whole sale market price (plus maybe a network charge).
    It takes the average of max export, min import, and discharges when below, charges when above.
    It ignores demand and generation.
    (This is intentionally a controller that is not very smart.  For a better version of spot price arbitrage,
    have a look at SpotPriceArbitrageOptimal in optimisation-based/spotpricearbitrageoptimal.py.)
    """

    def __init__(self, params: dict = {}) -> None:
        super().__init__(name="SpotPriceArbitrageNaiveController", params=params)

        # Arbitrage threshold will depend on scenario.  Initialise to 0.0 for now.
        self.arbitrage_mean = 0.0

        # Update all params with those that were passed in
        self.update_params(params)

    def solve_one_interval(self, scenario_interval: pd.DataFrame) -> float:
        """ See parent AbstractBatteryController class for parameter descriptions """

        if scenario_interval['tariff_import'] < self.arbitrage_mean:
            charge_rate = self.battery.params['max_charge_rate']
        elif scenario_interval['tariff_export'] > self.arbitrage_mean:
            charge_rate = -1 * self.battery.params['max_discharge_rate']
        else:
            charge_rate = 0

        return charge_rate

    def solve(self, scenario: pd.DataFrame, battery: BatteryModel) -> pd.DataFrame:
        """ See parent AbstractBatteryController class for parameter descriptions """

        # Calculate arbitrage threshold of this scenario
        import_threshold = scenario['tariff_export'].max()
        export_threshold = scenario['tariff_import'].min()
        self.arbitrage_mean = export_threshold + (import_threshold - export_threshold) / 2

        return super().solve(scenario, battery)
