import pandas as pd
from oes.battery.battery import AbstractBattery
from oes.controllers.abstract_battery_controller import AbstractBatteryController


class ImportTariffOptimisationController(AbstractBatteryController):
    """
    Battery controller for import tariff optimisation:
    discharge battery to meet demand when the import tariff is higher than average;
    charge battery at maximum possible rate when the import tariff is lower than average.
    """

    def __init__(self, params: dict = {}, battery: AbstractBattery = None, debug: bool = False) -> None:
        super().__init__(name=self.__class__.__name__, battery=battery, debug=debug)

        # Import tariff average will depend on scenario.  Initialise to 0.0 for now.
        self.import_tariff_average = 0.0

        # Update all params with those that were passed in
        self.update_params(params)

    def solve_one_interval(self, scenario_interval: pd.DataFrame) -> float:
        """ See parent AbstractBatteryController class for parameter descriptions """

        # if import tariff is higher than average, discharge to meet demand
        if scenario_interval["tariff_import"] >= self.import_tariff_average:
            return -1 * scenario_interval["demand"]
        # otherwise charge
        return self.battery.model.max_charge_rate

    def solve(self, scenario: pd.DataFrame) -> pd.DataFrame:
        """ See parent AbstractBatteryController class for parameter descriptions """

        # Calculate import tariff average of this scenario
        self.import_tariff_average = sum(scenario["tariff_import"]) / len(scenario.index)

        return super().solve(scenario)
