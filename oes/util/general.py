import pandas as pd
from typing import Dict, Optional
from oes.battery.battery import AbstractBattery, BatteryModel
import oes.util.cost_function_helpers as cost_function_helpers
from oes.util.conversions import timedelta_to_hours, resolution_in_hours
from oes.util.conversions import charge_rate_to_change_in_soc, change_in_soc_to_charge_rate


def find_resolution(df: pd.DataFrame) -> pd.Timedelta:
    """ Find resolution of provided dataframe, as a timedelta """
    # Remember that this package assumes clean input data (gaps etc. handled outside package)
    # Resolution is simply difference between adjacent intervals in the dataframe.
    return df.index[1] - df.index[0]


def fix_decimal_issue(float_number: float, precision: int = 2) -> float:
    """
    Fixes decimal issues with floating point numbers. Imagine having a float of 10.8, but the system interprets it as
    10.800000001. This function will ensure that we round properly according to the provided precision.
    :param float_number: the float number to fix
    :param precision: the precision of the number (in decimal places)
    """
    precision_factor = 10 ** precision
    return round(float_number * precision_factor) / precision_factor


def get_discretisation_offset(state_of_charge: float, soc_interval: float, precision: int = 2) -> float:
    """
    Finds out if a state of charge fits into a given state of charge interval and returns the offset from the discrete
    steps the interval defines. As an example, if you have a soc_interval of 0.5, but a state_of_charge of 10.8, then
    the offset is 0.3 (10.8 % 0.5 = 0.3). In order to avoid rounding issues, the soc_interval and state_of_charge are
    multiplied with the provided precision.
    :param state_of_charge: the battery state of charge in % that is checked against the soc_interval
    :param soc_interval: the discretisation interval of the state of charge
    :param precision: The precision should ensure that the soc_interval can be converted to an int without loss of
    information. If your soc_interval is 0.005, then the precision would have to be increased to 3.
    :return: the remainder after dividing the provided state_of_charge by the soc_interval
    """
    remainder = fix_decimal_issue(state_of_charge % soc_interval, precision)
    if fix_decimal_issue(remainder - soc_interval, precision) == 0.0:
        return 0.0
    return remainder


def get_feasible_charge_rate(charge_rate: float, battery_model: BatteryModel, current_soc: float,
                             time_interval: int) -> float:
    """
    Check if the provided charge rate is feasible for this time interval, given battery charge rate and soc constraints.
    If it isn't, return an adjust charge rate that is feasible.
    :param charge_rate: <float> requested (dis-)charge rate in W
    :param battery_model: <battery_model>
    :param current_soc: <float> current state of charge in %
    :param time_interval: <int> time discretisation in minutes
    :return: <float> feasible (dis-)charge rate
    """

    # Charging
    if charge_rate >= 0:
        # Find maximum allowable charge rate, ensure that chosen charge rate is not higher
        charge_rate_to_full = change_in_soc_to_charge_rate(battery_model.max_soc - current_soc,
                                                           battery_model.capacity, time_interval)
        charge_rate_max = min(battery_model.max_charge_rate, charge_rate_to_full)
        return min(charge_rate, charge_rate_max)

    # Discharging
    else:
        # Find maximum allowable discharge rate, ensure chosen charge rate is not lower
        discharge_rate_to_empty = change_in_soc_to_charge_rate(current_soc - battery_model.min_soc,
                                                               battery_model.capacity, time_interval)
        discharge_rate_max = min(battery_model.max_discharge_rate, discharge_rate_to_empty)
        return -1 * min(-1 * charge_rate, discharge_rate_max)


# TODO: is this function actually used?
# TODO Check if schedule should be DataFrame or Series?  Check if column_name needed?
def convert_schedule_to_solution(scenario: pd.DataFrame, schedule: pd.Series,
                                 battery: AbstractBattery, controllers: dict, init_soc: float,
                                 column_name: str = 'schedule'):
    """
    Calculate values of interest for a provided schedule throughout a scenario
    :param scenario: <pandas DataFrame> consisting of the following:
                        - index: pandas Timestamps
                        - column 'generation': forecasted solar generation in W
                        - column 'demand': forecasted demand in W
                        - column 'tariff_import': forecasted cost of importing electricity in $/kWh
                        - column 'tariff_export': forecasted reward for exporting electricity in $/kWh
    :param schedule: <pandas Series> consisting of the following:
                        - index: pandas Timestamps
                        - values: names of controllers to be used
    :param battery: <AbstractBattery>
    :param controllers: <dict> of name, controller pairs
    :param init_soc: <float> initial battery state of charge
    :param column_name: <str> indicating which column in schedule to use
    :return: <pandas dataframe> solution containing charge_rate, soc
    """

    # Check that first timestamp in scenario matches first time stamp in schedule
    if scenario.index[0] != schedule.index[0]:
        print("Error!  First time stamps in scenario and schedule must match!")
        raise AssertionError()  # TODO should create package-specific errors

    # Generate scenario copy, so we don't mess with original scenario
    scenario_copy = scenario.copy()

    # Utility variable
    time_interval_in_hours = resolution_in_hours(scenario_copy)

    # Determine initial controller
    curr_controller_txt = schedule[column_name].values[0]
    curr_controller = controllers[curr_controller_txt]

    # Set up controller params
    controller_params = {
        'time_interval_in_hours': time_interval_in_hours,
        'tariff_min': min(scenario_copy['tariff_import']),
        'tariff_avg': sum(scenario_copy['tariff_import']) / len(scenario_copy.index)
    }

    # Keep track of charge_rate, soc
    current_soc = init_soc
    all_soc = [current_soc]
    all_charge_rates = [0]

    # Iterate from 2nd row onwards
    for index, row in scenario_copy.iloc[1:].iterrows():

        # print(index, curr_controller_txt)

        charge_rate = curr_controller.solve_one_interval(row)

        # Update running variables
        all_charge_rates.append(charge_rate)
        all_soc.append(current_soc)
        current_soc = current_soc + charge_rate_to_change_in_soc(charge_rate,
                                                                 battery.model.capacity,
                                                                 time_interval_in_hours)

        # Check if we need to change to a different controller
        if index in schedule.index:
            curr_controller_txt = schedule.loc[index, column_name]
            curr_controller = controllers[curr_controller_txt]

    return pd.DataFrame(data={
        'timestamp': scenario_copy.index,
        'charge_rate': all_charge_rates,
        'soc': all_soc
    }).set_index('timestamp')


def calculate_solution_performance(scenario: pd.DataFrame, solution: pd.DataFrame = None,
                                   battery: Optional[AbstractBattery] = None, params: dict = None) -> pd.DataFrame:
    """
    Calculate several values of interest for a given controller.
    Note: the solution for the controller may have a different resolution than the scenario.  Always only the most
    recent charge rate is used in the evaluation.
    :param scenario: <pandas dataframe> consisting of all or some of the following:
                        - index: pandas Timestamps
                        - column 'generation': forecasted solar generation in W
                        - column 'demand': forecasted demand in W
                        - column 'tariff_import': forecasted cost of importing electricity in $
                        - column 'tariff_export': forecasted reward for exporting electricity in $
    :param solution: solution output of a controller, in other words a pandas dataframe containing columns:
            'timestamp': pandas Timestamps,
            'charge_rate': chosen rate of (dis)charge,
            'soc': ongoing battery state of charge
            'solar_curtailment': whether solar was curtailed or not, does not always exist as a column
            When solution is None, assumes no battery present.
    :param battery: a Battery instance with attached battery model that can be used to include consideration of
            (dis-)charge loss (No charge or discharge loss considered when no model is provided)
    :param params: dict of custom parameters that may be required to differentiate between different assumptions
    :return: solution with additional columns: 'grid_impact', 'interval_cost', 'accumulated_cost'
    """

    # Generate scenario copy, so we don't mess with original scenario
    scenario_copy = scenario.copy()

    # TODO is the below even needed?
    # Set any default param values
    if params is None:
        params = {}

    # If solution does not contain solar curtailment, add this as a column of zeroes
    if 'solar_curtailment' not in solution.columns:
        solution['solar_curtailment'] = [0.0] * len(solution.index)

    # Time between intervals is just the scenario's resolution
    time_interval = scenario.index[1] - scenario.index[0]
    time_interval_size = timedelta_to_hours(time_interval)

    # Initialise arrays of interest
    grid_impact = []
    interval_cost = []
    charge_rate_actual = []
    soc_actual = []
    accumulated_cost = [0.0]  # Initialise with 0 for cleaner loop below, then remove later

    # Initialise first soc
    if battery is not None:
        soc = battery.get_current_soc()
    else:
        soc = 0.0
    soc_actual.append(soc)

    for index, row in scenario_copy.iterrows():

        # Update battery-related variables only when solution and battery are provided
        if (solution is None) or (battery is None):
            this_charge_rate = 0.0
            soc = 0.0
            battery_impact = 0

        else:
            requested_charge_rate = solution.loc[index, 'charge_rate']

            # Ensure charge rate is feasible, and adjust if it isn't
            soc_change = charge_rate_to_change_in_soc(requested_charge_rate, battery.model.capacity, time_interval_size)
            if ((soc + soc_change) <= battery.model.max_soc) and \
                    ((soc + soc_change) >= battery.model.min_soc):
                this_charge_rate = requested_charge_rate
                soc = soc + soc_change
            else:
                # We have hit soc limit, so adjust charge_rate to one that is feasible within soc limits
                if soc_change < 0:
                    soc_change = battery.model.min_soc - soc
                else:
                    soc_change = battery.model.max_soc - soc
                this_charge_rate = change_in_soc_to_charge_rate(soc_change, battery.model.capacity, time_interval_size)
                soc = soc + soc_change

            # Take into account impact of charge or discharge efficiency
            battery_impact = battery.model.determine_impact_charge_rate_efficiency(this_charge_rate)

        # Calculate grid impact in Watts
        this_grid_impact = row['demand'] - row['generation'] + battery_impact + solution.loc[index, 'solar_curtailment']

        # Compute cost associated to the grid impact in the interval
        this_interval_cost = cost_function_helpers.compute_interval_cost(
            this_grid_impact,
            time_interval_size,
            row['tariff_import'],
            row['tariff_export']
        )

        # Keep running tallies
        grid_impact.append(this_grid_impact)
        interval_cost.append(this_interval_cost)
        charge_rate_actual.append(this_charge_rate)
        soc_actual.append(soc)
        accumulated_cost.append(accumulated_cost[-1] + this_interval_cost)

    # Remove last element from SOC and first element from accumulated cost
    soc_actual = soc_actual[:-1]
    accumulated_cost = accumulated_cost[1:]

    return pd.DataFrame(data={
        'timestamp': scenario_copy.index,
        'charge_rate_predicted': solution['charge_rate'],
        'charge_rate_actual': charge_rate_actual,
        'soc_predicted': solution['soc'],
        'soc_actual': soc_actual,
        'solar_curtailment': solution['solar_curtailment'],
        'grid_impact': grid_impact,
        'interval_cost': interval_cost,
        'accumulated_cost': accumulated_cost,
    }).set_index('timestamp')


def compare_solutions(solutions: Dict[str, pd.DataFrame]) -> pd.DataFrame:
    """
    Compare economic return of multiple controllers
    :param solutions: dictionary of solutions where the key identifies the solution and the value is the pd.DataFrame
    :return: pandas dataframe having structure:
            'timestamp': index of pandas Timestamps,
            for each solution key:
            '<key_in_solutions_parameter>': accumulated cost
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
