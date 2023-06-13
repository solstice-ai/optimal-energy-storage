from abc import ABC
from typing import Optional, List, Dict
import pandas as pd
import copy

from oes.battery.battery_model import BatteryModel
from oes.util.conversions import resolution_in_hours


class BatteryScheduler(ABC):
    """ Base class for any battery scheduler """

    def __init__(self, name: str = 'AbstractBatteryScheduler', params: Optional[Dict] = None) -> None:
        self.name = name

        # Store some objects / vars locally - these will be passed in when solve is called
        self.scenario: Optional[pd.DataFrame] = None
        self.battery: Optional[BatteryModel] = None
        self.controllers: Optional[List] = None
        self.solution_optimal: Optional[pd.DataFrame] = None

    def update_params(self, params: dict) -> None:
        """
        Update battery parameters
        :param params: dictionary of <parameter_name>, <parameter_value> pairs
        :return: None
        """
        for key, value in params.items():
            setattr(self, key, value)

    def solve(self, scenario: pd.DataFrame, battery: BatteryModel, controllers: List,
              solution_optimal: pd.DataFrame) -> pd.DataFrame:
        """
        Determine schedule for which type of controller should be used when
        :param scenario: dataframe consisting of:
                            - index: pandas Timestamps
                            - columns: one for each relevant entity (e.g. generation, demand, tariff_import, etc.)
        :param battery: <battery model>
        :param controllers: <list of (controller_name, controller_type) pairs> to be used when generating schedule
        :param solution_optimal: dataframe containing columns showing optimal "charge_rate" and "soc"
        :return: dataframe consisting of:
                    - index: pandas Timestamps
                    - 'controller': string indicating which controller to start using
        """

        # Keep local copies
        self.scenario = copy.copy(scenario)
        self.battery = copy.copy(battery)
        self.controllers = controllers
        self.solution_optimal = solution_optimal

        # Here in abstract base class, return None - this will be handled in child class
        return None
