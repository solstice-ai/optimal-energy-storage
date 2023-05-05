from abc import ABC
import pandas as pd
import copy
import warnings
from typing import Optional
from oes.battery.battery_model import BatteryModel
from oes.util.general import get_feasible_charge_rate
from oes.util.conversions import charge_rate_to_soc, resolution_in_hours


class AbstractBatteryController(ABC):
    """ Base class for any battery controller """

    def __init__(self, name: str = "AbstractBatteryController", battery_model: Optional[BatteryModel] = None,
                 debug: bool = False):
        self.name = name
        self.debug = debug

        # Battery model
        self.battery = battery_model

        # Default is to keep track of battery SOC and constrain charge rate accordingly
        # When this is set to False, the returned charge rates don't take battery SOC into account
        self.constrain_charge_rate = True

        # For convenience, store length of interval (in hours) locally. This is detected when scenario
        # is passed in self.solve(scenario, battery)
        self.interval_size_in_hours = None

    def update_params(self, params: dict) -> None:
        """
        Update parameters -- overrides any defaults set in __init__
        :param params: dictionary of <parameter_name>, <parameter_value> pairs
        :return: None
        """
        protected_params = ["name", "debug", "battery"]
        for key, value in params.items():
            if key in protected_params:
                warnings.warn(f"Cannot update parameter {key} as it is protected")
                continue
            if hasattr(self, key):
                setattr(self, key, value)
            else:
                warnings.warn(f"{self.__class__.__name__} does not have an attribute {key}")

    def solve_one_interval(self, scenario_interval: pd.DataFrame) -> float:
        """
        Solve a single interval: determine charge rate chosen by this controller in this interval.
        This function determines controller functionality and will be implemented differently in all child instances
        :param scenario_interval: pd.DataFrame having only a single row (one interval in scenario)
        :return: charge rate for this interval
        """
        pass

    def solve(self, scenario: pd.DataFrame) -> pd.DataFrame:
        """
        Determine charge / discharge rates and resulting battery soc for every interval in the horizon
        :param scenario: dataframe consisting of:
                            - index: pandas Timestamps
                            - columns: generation, demand, tariff_import, tariff_export, all floats
        :return: dataframe consisting of:
                    - index: pandas Timestamps
                    - 'charge_rate': float indicating charging rate for this interval in W
                    - 'soc': float indicating resulting state of charge in %
        """

        # Keep local copy of battery model (avoid changing original battery object)
        self.battery = copy.copy(self.battery)

        # Store interval size in hours locally - required for later computations
        self.interval_size_in_hours = resolution_in_hours(scenario)

        # Keep track of relevant values
        all_soc = [self.battery.soc]
        all_charge_rates = [0.0]

        # Iterate from 2nd row onwards
        for index, row in scenario.iloc[1:].iterrows():

            charge_rate = self.solve_one_interval(row)

            # Ensure charge rate is feasible
            if self.constrain_charge_rate:
                charge_rate = get_feasible_charge_rate(charge_rate, self.battery, self.interval_size_in_hours)

            # Update running variables.  Note that change in battery soc is reflected in next interval.
            all_charge_rates.append(charge_rate)
            all_soc.append(self.battery.soc)
            self.battery.soc = self.battery.soc + charge_rate_to_soc(charge_rate, self.battery.capacity,
                                                                     self.interval_size_in_hours)

        return pd.DataFrame(data={
            "timestamp": scenario.index,
            "charge_rate": all_charge_rates,
            "soc": all_soc
        }).set_index("timestamp")

    def debug_message(self, *message):
        if self.debug:
            print(*message)
