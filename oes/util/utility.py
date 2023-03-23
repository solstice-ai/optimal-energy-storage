import pandas as pd
from typing import Union
import sys


def timedelta_to_hours(time_delta):
    """ Convert a time delta to a float representing hours """
    return time_delta.total_seconds() / 3600


def power_to_energy(watts: Union[int, float], interval_minutes: Union[int, float]):
    """
    Converts power (given in watts) into energy (given in watt-hours)
    :param watts: the number of watts of power
    :param interval_minutes: the number of minutes to which the watts apply
    :return: the number of watt-hours this power output over the given interval represents.
    """
    return watts * (interval_minutes / 60)


def soc_to_chargerate(soc, capacity, time_interval):
    """ Convert change in soc to charge rate over one interval """
    return soc / 100 * capacity / time_interval


def chargerate_to_soc(charge_rate, capacity, time_interval):
    """ Convert charge rate to change in soc in one interval """
    return charge_rate * time_interval / capacity * 100


def fix_decimal_issue(float_number: float, precision: int = 100) -> float:
    """
    Fixes decimal issues with floating point numbers. Imagine having a float of 10.8, but the system interprets it as
    10.800000001. This function will ensure that we round properly according to the provided precision.
    :param float_number: the float number to fix
    :param precision: the precision of the number (100 fixes up to 2 decimal places)
    """
    return round(float_number * precision) / precision


def get_discretisation_offset(state_of_charge: float, soc_interval: float, precision: int = 100) -> float:
    """
    Finds out if a state of charge fits into a given state of charge interval and returns the offset from the discrete
    steps the interval defines. As an example, if you have a soc_interval of 0.5, but a state_of_charge of 10.8, then
    the offset is 0.3 (10.8 % 0.5 = 0.3). In order to avoid rounding issues, the soc_interval and state_of_charge are
    multiplied with the provided precision.
    :param state_of_charge: the battery state of charge in % that is checked against the soc_interval
    :param soc_interval: the discretisation interval of the state of charge
    :param precision: The precision should ensure that the soc_interval can be converted to an int without loss of
    information. If your soc_interval is 0.005, then the precision would have to be increased to 1000.
    :return: the module between the provided state_of_charge and the soc_interval
    """
    residue = fix_decimal_issue(state_of_charge % soc_interval, precision)
    if fix_decimal_issue(residue - soc_interval, precision) == 0.0:
        return 0.0
    return residue


def feasible_charge_rate(charge_rate, soc, battery, time_interval):
    """
    Check to make sure charge rate is feasible, adjust as needed
    :param charge_rate: <float> max (dis-)charge rate in W
    :param soc: <float> state of charge of battery
    :param battery: <battery_model>
    :param deltaT: <int> time discretisation in minutes
    :return: <float> feasible (dis-)charge rate
    """

    # Charging
    if charge_rate >= 0:
        c_tofull = soc_to_chargerate(battery.params['max_soc'] - soc,
                                     battery.params['capacity'],
                                     time_interval)
        c_max = min(battery.params['max_charge_rate'], c_tofull)
        return min(charge_rate, c_max)

    # Discharging
    else:
        c_toempty = soc_to_chargerate(soc - battery.params['min_soc'],
                                      battery.params['capacity'],
                                      time_interval)
        c_max = min(battery.params['max_discharge_rate'], c_toempty)
        return -1 * min(-1 * charge_rate, c_max)


def pretty_time(t):
    """ Outputs user-friendly time as string """

    # Less than a minute?
    if t < 60:
        return str(int(t)) + "s"

    # Less than an hour, more than a minute?
    elif t < 60 * 60:
        return str(int(t / 60)) + "m " + str(int(t % 60)) + "s"

    # More than an hour?
    else:
        return str(int(t / (60 * 60))) + "h " + str(int(int(t / 60) % 60)) + "m " + str(int(t % 60)) + "s"


def convert_resolution(df, resolution):
    """
    Convert every column in a dataframe to a given resolution
    :param df: the pandas dataframe to be converted (must have datetime-like index and numeric-only data)
    :param resolution: timedelta representing the desired resolution
    :return: a pandas dataframe having same structure as original df, but at desired resolution
    """
    resampled = pd.DataFrame()

    # convert dataframe to numeric, resample, use mean for each interval
    for col in df:
        series = pd.to_numeric(df[col], errors='coerce')
        resampled[col] = series.resample(resolution, label='right', closed='right').mean()

    return resampled


def convert_schedule_to_solution(scenario, schedule, battery, controllers, init_soc, column_name='schedule'):
    """
    Calculate values of interest for a provided schedule throughout a scenario
    :param scenario: <pandas dataframe> consisting of all or some of the following:
                        - index: pandas Timestamps
                        - column 'generation': forecasted solar generation in W
                        - column 'demand': forecasted demand in W
                        - column 'tariff_import': forecasted cost of importing electricity in $
                        - column 'tariff_export': forecasted reqard for exporting electricity in $
                        - column 'market_price': forecasted reward for exporting electricity at wholesale market value in $
    :param schedule: <pandas dataframe> consisting of the following:
                        - index: pandas Timestamps
                        - column 'schedule': names of controllers to be used
    :param battery: <battery model>
    :param controllers: <dict> of name, controller pairs
    :param init_soc: <float> initial battery state of charge
    :param column_name: <str> indicating which column in schedule to use
    :return: <pandas dataframe> solution containing charge_rate, soc
    """

    # Check that first timestamp in scenario matches first time stamp in schedule
    if scenario.index[0] != schedule.index[0]:
        print("Error!  First time stamps in scenario and schedule must match!")
        raise AssertionError()  # TODO should create package-specific errors

    # Generate scenario copy so we don't mess with original scenario
    scenario_copy = scenario.copy()

    # Utility variable
    time_interval_in_hours = timedelta_to_hours(scenario.index[1] - scenario.index[0])

    # Determine initial controller
    curr_controller_txt = schedule[column_name].values[0]
    curr_controller = controllers[curr_controller_txt]

    # Set up controller params
    controller_params = {
        'time_interval_in_hours': time_interval_in_hours,
        'tariff_min': min(scenario['tariff_import']),
        'tariff_avg': sum(scenario['tariff_import']) / len(scenario.index)
    }

    # Keep track of charge_rate, soc
    current_soc = init_soc
    all_soc = [current_soc]
    all_charge_rates = [0]

    # Iterate from 2nd row onwards
    for index, row in scenario.iloc[1:].iterrows():

        # print(index, curr_controller_txt)

        charge_rate = curr_controller.solve_one_interval(
            row, battery, current_soc, controller_params, constrain_charge_rate=True)

        # Update running variables
        all_charge_rates.append(charge_rate)
        all_soc.append(current_soc)
        current_soc = current_soc + chargerate_to_soc(charge_rate,
                                                      battery.params['capacity'],
                                                      time_interval_in_hours)

        # Check if we need to change to a different controller
        if index in schedule.index:
            curr_controller_txt = schedule.loc[index, column_name]
            curr_controller = controllers[curr_controller_txt]

    return pd.DataFrame(data={
        'timestamp': scenario.index,
        'charge_rate': all_charge_rates,
        'soc': all_soc
    }).set_index('timestamp')


def detect_resolution(data: Union[pd.Series, pd.DataFrame]) -> pd.Timedelta:
    """
    Detects the resolution of the provided data set, by determining the most common difference between
    adjacent data points
    :param data: the provided series or data frame, having index of timestamps
    :return: a timedelta of the likely resolution
    :raise ValueError: in case a dataset is provided that is too small
    """
    if len(data) < 2:
        raise ValueError("Insufficient data points available for forecast in provided data frame")

    # keep track of differences between adjacent data points
    res = (pd.Series(data.index[1:]) - pd.Series(data.index[:-1])).value_counts()

    # most common difference is at index 0
    return res.index[0]


def calculate_solution_performance(scenario, solution=None, battery=None, params=None):
    """
    Calculate several values of interest for a given controller.
    Note: the solution for the controller may have a different resolution than the scenario.  Always only the most
    recent charge rate is used in the evaluation.
    :param scenario: <pandas dataframe> consisting of all or some of the following:
                        - index: pandas Timestamps
                        - column 'generation': forecasted solar generation in W
                        - column 'demand': forecasted demand in W
                        - column 'tariff_import': forecasted cost of importing electricity in $
                        - column 'tariff_export': forecasted reqard for exporting electricity in $
                        - column 'market_price': forecasted reward for exporting electricity at wholesale market value in $
    :param solution: solution output of a controller, in other words a pandas dataframe containing columns:
            'timestamp': pandas Timestamps,
            'charge_rate': chosen rate of (dis)charge,
            'soc': ongoing battery state of charge
            'solar_curtailment': whether solar was curtailed or not, does not always exist as a column
            When solution is None, assumes no battery present.
    :param battery: BasicBatteryModel that can be used to include consideration of (dis-)charge loss
            (No charge or discharge loss considered when no model is provided)
    :param params: dict of custom parameters that may be required to differentiate between different assumptions
    :return: solution with additional columns: 'grid_impact', 'interval_cost', 'accumulated_cost'
    """

    # Generate scenario copy so we don't mess with original scenario
    scenario_copy = scenario.copy()

    # Set any default param values
    if params is None:
        params = {}
    if 'allow_market_participation' not in params:
        params['allow_market_participation'] = False

    # If solution does not contain solar curtailment, add this as a column of zeroes
    if 'solar_curtailment' not in solution.columns:
        solution['solar_curtailment'] = [0.0] * len(solution.index)

    # Calculate time between intervals
    time_interval = pd.Timedelta(scenario_copy.index[1] - scenario_copy.index[0])
    time_interval_size = timedelta_to_hours(time_interval)

    # Initialise arrays of interest
    grid_impact = []
    interval_cost = []
    charge_rate_actual = []
    soc_actual = []
    accumulated_cost = [0]  # Initialise with 0 for cleaner loop below, then remove later

    # Initialise first soc
    if battery is not None:
        soc = battery.params['current_soc']
    else:
        soc = 0.0
    soc_actual.append(soc)

    for index, row in scenario_copy.iterrows():

        # Update battery related variables only when solution and battery are provided
        if (solution is None) or (battery is None):
            this_charge_rate = 0
            soc = 0
            battery_impact = 0

        else:
            requested_charge_rate = solution.loc[index, 'charge_rate']

            # Ensure charge rate is feasible, and adjust if it isn't
            soc_change = chargerate_to_soc(requested_charge_rate, battery.params['capacity'], time_interval_size)
            if ((soc + soc_change) <= battery.params['max_soc']) and \
               ((soc + soc_change) >= battery.params['min_soc']):
                this_charge_rate = requested_charge_rate
                soc = soc + soc_change
            else:
                # We have hit soc limit, so adjust charge_rate to one that is feasible within soc limits
                if soc_change < 0:
                    soc_change = battery.params['min_soc'] - soc
                else:
                    soc_change = battery.params['max_soc'] - soc
                this_charge_rate = soc_to_chargerate(soc_change, battery.params['capacity'], time_interval_size)
                soc = soc + soc_change

            # Take into account impact of charge or discharge loss
            battery_impact = this_charge_rate
            if this_charge_rate > 0:  # charging
                # Avoid divide by zero
                if battery.params['loss_factor_charging'] == 0:
                    battery_impact = this_charge_rate / 0.000001
                else:
                    battery_impact = this_charge_rate / battery.params['loss_factor_charging']
            elif this_charge_rate < 0:  # discharging
                # Avoid divide by zero
                if battery.params['loss_factor_discharging'] == 0:
                    battery_impact = this_charge_rate * 0.000001
                else:
                    battery_impact = this_charge_rate * battery.params['loss_factor_discharging']

        # Calculate grid impact in Watts
        this_grid_impact = row['demand'] - row['generation'] + battery_impact + solution.loc[index, 'solar_curtailment']

        # TODO: Check that the below logic makes sense -- not fully tested
        # Determine values of import, export
        if params['allow_market_participation']:
            import_cost = min(row['tariff_import'], row['market_price'] / 1000)
            export_value = max(row['tariff_export'], row['market_price'] / 1000)
        else:
            import_cost = row['tariff_import']
            export_value = row['tariff_export']

        # Calculate interval cost
        if this_grid_impact < 0:
            this_interval_cost = this_grid_impact / 1000 * time_interval_size * export_value
        else:
            this_interval_cost = this_grid_impact / 1000 * time_interval_size * import_cost

        # Keep running tallies
        grid_impact.append(this_grid_impact)
        interval_cost.append(this_interval_cost)
        charge_rate_actual.append(this_charge_rate)
        soc_actual.append(soc)
        accumulated_cost.append(accumulated_cost[-1] + this_interval_cost)

    # Remove last element from SOC and first element from accumulated cost
    soc_actual = soc_actual[:-1]
    accumulated_cost = accumulated_cost[1:]

    # TODO The below does not work if scenario, solution have different lengths - must fix
    return pd.DataFrame(data={
        'timestamp': scenario_copy.index,
        'charge_rate_predicted': solution['charge_rate'],
        'charge_rate': charge_rate_actual,
        'soc_predicted': solution['soc'],
        'soc': soc_actual,
        'solar_curtailment': solution['solar_curtailment'],
        'grid_impact': grid_impact,
        'interval_cost': interval_cost,
        'accumulated_cost': accumulated_cost,
    }).set_index('timestamp')


def compare_solutions(solutions):
    """
    Compare economic return of multiple controllers
    :param solutions: array of controllers, e.g. solar self consumption, tariff optimisation, etc.
    :return: pandas dataframe having structure:
            'timestamp': index of pandas Timestamps,
            for each solution:
            'solution_name': accumulated cost
    """
    accumulated_cost = {}
    timestamps = None
    for solution in solutions:
        accumulated_cost[solution] = solutions[solution]['accumulated_cost']
        # First time only, store timestamps (should be the same for every solution)
        if timestamps is None:
            timestamps = solutions[solution].index

    accumulated_cost['timestamp'] = timestamps

    return pd.DataFrame(data=accumulated_cost).set_index('timestamp')
