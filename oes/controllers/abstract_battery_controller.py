import pandas as pd
from abc import ABC

from oes.util import utility


class BatteryControllerException(Exception):
    """ Error arising during battery control """

    def __init__(self, msg, err=None):
        if msg is None:
            msg = "An error occurred with the battery controller"
        super(BatteryControllerException, self).__init__(msg)
        self.error = err


class BatteryController(ABC):
    """ Base class for any battery controller """

    def __init__(self, name='BatteryController', params=None):
        self.name = name

        # Set default parameters
        self.params = {
            'time_interval': '30 minutes',  # Time discretisation
            'constrain_charge_rate': True,  # Whether to choose charge/discharge rates that stay within allowable SOC
        }

        # Overwrite default params with custom params that were passed
        if params is not None:
            for param in params:
                self.params[param] = params[param]

        # Store time_interval as a float representing number of hours
        self.time_interval_in_hours = utility.timedelta_to_hours(pd.Timedelta(self.params['time_interval']))

    def solve(self, scenario, battery):
        """
        Determine charge / discharge rates and resulting battery soc for every interval in the horizon
        :param scenario: dataframe consisting of:
                            - index: pandas Timestamps
                            - columns: one for each relevant entity (e.g. generation, demand, tariff_import, etc.)
        :param battery: <battery model>
        :return: dataframe consisting of:
                    - index: pandas Timestamps
                    - 'charge_rate': float indicating charging rate for this interval in W
                    - 'soc': float indicating resulting state of charge
        """
        pass
