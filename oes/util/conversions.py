from typing import Union
import pandas as pd


def timedelta_to_hours(time_delta: pd.Timedelta) -> float:
    """ Convert a time delta to a float representing hours """
    return time_delta.total_seconds() / 3600


def resolution_in_hours(data: pd.DataFrame) -> float:
    """ Determine the resolution of a dataset as a float representing hours """
    # Remember that this package assumes any gaps have been handled prior to data being passed in.
    # Resolution is simply the difference between any two rows.
    return timedelta_to_hours(data.index[1] - data.index[0])


def power_to_energy(watts: Union[int, float], interval_minutes: Union[int, float]):
    """
    Converts power (given in watts) into energy (given in watt-hours)
    :param watts: the number of watts of power
    :param interval_minutes: the number of minutes to which the watts apply
    :return: the number of watt-hours this power output over the given interval represents.
    """
    return watts * (interval_minutes / 60)


def charge_rate_to_change_in_soc(charge_rate: float, capacity: float, interval_hours: float) -> float:
    """
    Convert charge rate to change in soc in given interval size
    :param charge_rate: the charge rate in Watts
    :param capacity: the battery capacity in Watt-hours
    :param interval_hours: the time interval in hours (e.g. 5 mins = 1/12 = 0.08333)
    """
    return charge_rate * interval_hours / capacity * 100


def change_in_soc_to_charge_rate(soc: float, capacity: float, interval_hours: float) -> float:
    """
    Convert change in soc to charge rate over given interval size
    :param soc: the change in state of charge (percent), i.e. value between 0-100
    :param capacity: the battery capacity in Watt-hours
    :param interval_hours: the time interval in hours (e.g. 5 mins = 1/12 = 0.08333)
    """
    return soc / 100 * capacity / interval_hours
