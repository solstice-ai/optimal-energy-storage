import oes.util.conversions
import oes.util.general as utility
from abc import ABC


class BatteryControllerException(Exception):
    """ Error arising during battery control """

    def __init__(self, msg, err=None):
        if msg is None:
            msg = "An error occurred with the battery controller"
        super(BatteryControllerException, self).__init__(msg)
        self.error = err


class BatteryController(ABC):
    """ Base class for any battery controller """

    def __init__(self, name: str = 'BatteryController', params: dict = {}) -> None:
        self.name = name

        # Default is to keep track of battery SOC and constrain charge rate accordingly
        # When this is set to False, the returned charge rates don't take battery SOC into account
        self.constrain_charge_rate = True

        # Every controller needs to know length of interval, this is detected when scenario
        # is passed in self.solve(scenario, battery)
        self.interval_size_in_hours = None

    def update_params(self, params: dict) -> None:
        """
        Update parameters -- overrides any defaults set in __init__
        :param params: dictionary of <parameter_name>, <parameter_value> pairs
        :return: None
        """
        for key, value in params.items():
            setattr(self, key, value)

    def solve(self, scenario, battery):
        """
        Determine charge / discharge rates and resulting battery soc for every interval in the horizon
        :param scenario: dataframe consisting of:
                            - index: pandas Timestamps
                            - columns: generation, demand, tariff_import, tariff_export
        :param battery: <battery model>
        :return: dataframe consisting of:
                    - index: pandas Timestamps
                    - 'charge_rate': float indicating charging rate for this interval in W
                    - 'soc': float indicating resulting state of charge
        """

        self.interval_size_in_hours = oes.util.conversions.resolution_in_hours(scenario)

        # Any remaining steps to solve this scenario must be implemented by child controller
