from abc import ABC
import pandas as pd

import oes.util.utility as utility


class BatterySchedulerException(Exception):
    """ Error arising during battery scheduling """

    def __init__(self, msg, err=None):
        if msg is None:
            msg = "An error occurred with the battery scheduler"
        super(BatterySchedulerException, self).__init__(msg)
        self.error = err


class BatteryScheduler(ABC):
    """ Base class for any battery scheduler """

    def __init__(self, name='BatteryScheduler', params=None):
        self.name = name

        # Set default parameters
        self.params = {
            'time_interval': '30 minutes',  # Time discretisation
        }

        # Overwrite default params with custom params that were passed
        if params is not None:
            for param in params:
                self.params[param] = params[param]

        # Store time_interval as a float representing number of hours
        self.time_interval_in_hours = utility.timedelta_to_hours(pd.Timedelta(self.params['time_interval']))

    def solve(self, scenario, battery, controllers):
        """
        Determine schedule for which type of controller should be used when
        :param scenario: dataframe consisting of:
                            - index: pandas Timestamps
                            - columns: one for each relevant entity (e.g. generation, demand, tariff_import, etc.)
        :param battery: <battery model>
        :param controllers: <dictionary of controller_name, controller_type pairs>
                        Dictionary of all simple and rule-based controllers to be used when choosing schedule
        :return: dataframe consisting of:
                    - index: pandas Timestamps
                    - 'controller': string indicating which controller to start using
        """
        pass
