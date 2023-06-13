import pandas as pd
from typing import Optional
from oes.battery.battery import AbstractBattery
from oes.controllers.abstract_battery_controller import AbstractBatteryController


class SpotPriceArbitrageNaiveController(AbstractBatteryController):
    """
    Battery controller for naive spot price arbitrage:
    Assumes that both import and export tariff represent whole-sale market price (plus maybe a network charge).
    It takes the average of max export, min import, and discharges when below, charges when above.
    It ignores demand and generation.
    (This is intentionally a controller that is not very smart.  For a better version of spot price arbitrage,
    have a look at SpotPriceArbitrageOptimalController in optimisation_based/spotprice_arbitrage_optimal.py.)
    """

    def __init__(self, params: dict = {}, debug: bool = False) -> None:
        super().__init__(name=self.__class__.__name__, debug=debug)

        # Arbitrage threshold will depend on scenario.  Initialise to 0.0 for now.
        self.arbitrage_mean = 0.0

        # Update all params with those that were passed in
        self.update_params(params)

    def solve_one_interval(self, scenario_interval: pd.DataFrame) -> float:
        """ See parent AbstractBatteryController class for parameter descriptions """

        if scenario_interval["tariff_import"] < self.arbitrage_mean:
            return self.battery.model.max_charge_rate
        elif scenario_interval["tariff_export"] > self.arbitrage_mean:
            return -1 * self.battery.model.max_discharge_rate

        return 0

    def solve(self, scenario: pd.DataFrame, battery: Optional[AbstractBattery] = None) -> pd.DataFrame:
        """ See parent AbstractBatteryController class for parameter descriptions """

        # Calculate arbitrage threshold of this scenario
        import_threshold = scenario["tariff_export"].max()
        export_threshold = scenario["tariff_import"].min()
        self.arbitrage_mean = export_threshold + (import_threshold - export_threshold) / 2

        return super().solve(scenario, battery)
