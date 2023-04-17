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


def charge_rate_to_soc(charge_rate: float, capacity: float, time_interval: int) -> float:
    """ Convert charge rate to change in soc in one interval """
    return charge_rate * time_interval / capacity * 100


def soc_to_charge_rate(soc: float, capacity: float, time_interval: int) -> float:
    """ Convert change in soc to charge rate over one interval """
    return soc / 100 * capacity / time_interval
