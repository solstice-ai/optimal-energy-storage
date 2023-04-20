import pandas as pd
import numpy
import sys
import datetime as dt
import warnings

from oes.util.conversions import soc_to_charge_rate
from oes.util.output import pretty_time
from oes import AbstractBatteryController
from oes.util.cost_function_helpers import compute_state_transition_cost
import oes.util.general as utility


class DynamicProgramController(AbstractBatteryController):
    """ Optimal battery control using dynamic programming """

    def __init__(self, name='DynamicProgramController', params: dict = {}, debug: bool = False):
        """
        Creates a new instance of this controller
        :param name: the name of the controller
        :param params: the parameters for the optimisation
        :param debug: boolean flag indicating whether to print out debug messages
        """
        super().__init__(name=name, params=params)

        self.debug = debug

        # Set default values for params
        self.soc_interval: float = 1.0  # soc discretisation (in %)
        self.constrain_final_soc: bool = True  # Do we want to specify final soc
        self.final_soc: float = 50.0  # Desired final soc
        self.minimize_activity: bool = False  # Whether to minimise number of intervals in which there is charging
        self.prioritize_early_charge = False  # Whether to try to charge battery earlier rather than later
        self.include_battery_degradation_cost = False  # Whether to include consideration of battery degradation cost
        self.limit_import: float = None  # Whether to avoid exceeding static import limits.  None means no limit.
        self.limit_export: float = None  # Whether to avoid exceeding static export limits.  None means no limit.
        self.include_charge_loss: bool = False  # Whether to multiply by a loss factor for (dis-)charging of battery
        self.allow_solar_curtailment: bool = False  # Allow consideration of solar curtailment at each interval

        # Update the above with input params, which also validates the params
        self.update_params(params)

        # Validate the parameters
        self.validate_params()

        # Initialise local variables
        self.generation = None  # Generation data
        self.demand = None  # Demand data
        self.tariff_import = None  # Import tariff data
        self.tariff_export = None  # Export tariff data
        self.import_limit = None  # Import limits
        self.export_limit = None  # Export limits

        self.battery = None  # Battery model

    def validate_params(self):
        """ Run a number of checks to make sure parameters are valid """

        # sanity check for soc_interval, multiply by 100 to avoid floating point issues
        if utility.get_discretisation_offset(100, self.soc_interval) != 0.0:
            raise ValueError("Invalid 'soc_interval' parameter passed. It needs to be able to divide 100% state of "
                             "charge without residue")

        # TODO Need more check here

    def _initialise_dp(self):
        """
        Initialise grid, parameters before running actual dynamic program
        :return: None
        """
        if self.debug:
            print('Initialising dynamic program ...')

        # Determine size of DP
        self.num_time_intervals = len(self.generation)
        self.num_soc_intervals = int((self.battery.params['max_soc'] -
                                      self.battery.params['min_soc']) / self.params['soc_interval'] + 1)
        if self.debug:
            print("DP grid has size " +
                  str(self.num_soc_intervals) + " (num soc intervals) x " +
                  str(self.num_time_intervals) + " (num time intervals)")

        # Determine max / min change in soc from one time interval to the next
        self.max_soc_increase = self.battery.params['max_charge_rate'] * self.time_interval_in_hours / \
                                self.battery.params['capacity']
        self.max_soc_increase_interval = round(self.max_soc_increase / self.params['soc_interval'] * 100)
        self.max_soc_decrease = -1 * self.battery.params['max_discharge_rate'] * self.time_interval_in_hours / \
                                self.battery.params['capacity']
        self.max_soc_decrease_interval = round(self.max_soc_decrease / self.params['soc_interval'] * 100)

        if self.debug:
            print("At each time step, ")
            print(" - battery may    charge at most {0:.0f}Wh, a change in soc of {1:.3f}% ({2:d} intervals)".format(
                self.battery.params['max_charge_rate'] * self.time_interval_in_hours,
                self.max_soc_increase * 100, self.max_soc_increase_interval))
            print(" - battery may discharge at most {0:.0f}Wh, a change in soc of {1:.3f}% ({2:d} intervals)".format(
                self.battery.params['max_discharge_rate'] * self.time_interval_in_hours,
                self.max_soc_decrease * 100, self.max_soc_decrease_interval))

        # Initialise CTG (cost to go), CF (came from), SC (solar curtail) matrices
        self.CTG = numpy.full((self.num_soc_intervals, self.num_time_intervals), sys.float_info.max)
        self.SC = numpy.full((self.num_soc_intervals, self.num_time_intervals - 1), 0.0)
        self.CF = numpy.empty((self.num_soc_intervals, self.num_time_intervals - 1))
        for i in range(0, self.num_soc_intervals):
            for j in range(0, self.num_time_intervals - 1):
                self.CF[i][j] = i

        # CTG last column must be zeros
        for i in range(0, self.num_soc_intervals):
            self.CTG[i][self.num_time_intervals - 1] = 0

    def _constrain_final_soc(self):
        """
        Sets up CTG matrix to be biased towards a desired final state of charge,
        by initialising it with a very low cost
        :return:
        """
        final_soc_index = int((self.params['final_soc'] - self.battery.params['min_soc']) / self.params['soc_interval'])
        self.CTG[final_soc_index, self.num_time_intervals - 1] = -100000

    def _run_dynamic_program(self):
        """
        Run the actual dynamic program that calculates all values in both matrices
        :return: None
        """

        # Progress updates if running with self.debug=True
        interval_size_ten_percent = int(self.num_time_intervals / 10)
        if self.debug:
            print('Running dynamic program ...')
            print("  0% ...")

        # Work our way backwards from last column of matrix to first column
        for col in range(self.num_time_intervals - 2, -1, -1):

            # Progress update
            if self.debug:
                cols_completed = self.num_time_intervals - col
                if (cols_completed % interval_size_ten_percent) == 0:
                    print(f" {int(cols_completed / interval_size_ten_percent) * 10}% ...")

            # Work our way up through all possible soc states
            for row in range(0, self.num_soc_intervals):

                prev_row_min = int(max(0, row + self.max_soc_decrease_interval))
                prev_row_max = int(min(self.num_soc_intervals - 1, row + self.max_soc_increase_interval))

                for prev_row in range(prev_row_min, prev_row_max + 1):

                    change_soc = (row - prev_row) * self.params['soc_interval']  # Will be positive when charging
                    change_soc_in_kwh = self.battery.compute_soc_change_kwh(change_soc)

                    # If we are taking losses into account, multiply by relevant (dis-)charge loss factor
                    battery_impact_kwh = change_soc_in_kwh
                    if self.params['include_charge_loss']:
                        battery_impact_kwh = self.battery.determine_impact_soc_change_efficiency(change_soc_in_kwh)

                    # Positive means importing from grid
                    # Negative means exporting to grid
                    # Remember that dem, gen are in kW, change_soc is in kWh
                    net_grid_impact_kw = (self.demand[col] - self.generation[col]) + \
                                         battery_impact_kwh / self.time_interval_in_hours
                    net_grid_impact_kwh = net_grid_impact_kw * self.time_interval_in_hours

                    # DOE version
                    if net_grid_impact_kw < -1 * self.export_limit[col]:
                        continue
                    if net_grid_impact_kw > self.import_limit[col]:
                        continue

                    # State transition cost is calculated using net grid impact in kWh
                    state_transition_cost = compute_state_transition_cost(
                        net_grid_impact_kwh,
                        self.tariff_import[col],
                        self.tariff_export[col])

                    # If we are taking battery degradation cost into account, add relevant amount
                    if self.params['include_battery_degradation_cost']:
                        degradation_cost = self.battery.compute_degradation_cost(change_soc_in_kwh)
                        state_transition_cost = state_transition_cost + degradation_cost

                    # If we want to minimise charging activity, add a small cost when charging or discharging
                    if self.params['minimize_activity']:
                        if not prev_row == row:
                            # TODO this should not be an absolute amount, rather it should be scaled by
                            #      some value proportional to size of discretisation
                            state_transition_cost = state_transition_cost + 0.001

                    # If we want to prioritise full charge earlier, add small cost to later intervals
                    if self.params['prioritize_early_charge']:
                        # TODO here too the actual penalty should be proportional to discretisation
                        state_transition_cost = state_transition_cost + \
                                                (self.num_soc_intervals - row) / self.num_soc_intervals / 500

                    # Calculate total cost to get there including this state transition
                    this_cost_to_get_there = self.CTG[row][col + 1] + state_transition_cost

                    # print(col, row, prev_row, state_transition_cost, this_cost_to_get_there)

                    # If this is better than existing entry, update
                    if (this_cost_to_get_there + 0.0001) < self.CTG[prev_row][col]:
                        self.CTG[prev_row][col] = this_cost_to_get_there
                        self.CF[prev_row][col] = row
                        self.SC[prev_row][col] = this_solar_curtailment

                    # Else if this is similar but has higher soc, update
                    elif (abs(this_cost_to_get_there - self.CTG[prev_row][col]) < 0.001) and (row > prev_row):
                        self.CTG[prev_row][col] = this_cost_to_get_there
                        self.CF[prev_row][col] = row
                        self.SC[prev_row][col] = this_solar_curtailment

    def _calculate_optimal_profile(self):
        """
        Assuming dynamic program has been solved, calculate optimal profile by walking through
        solved matrix.
        :return: None
        """
        if self.debug:
            print('Calculating optimal profile ...')

        # Now determine best route from starting soc, and track some values of interest
        next_soc = self.params['initial_soc']
        self.optimal_profile = [next_soc]
        self.charge_rate = []
        self.solar_curtailment = []

        next_index = int((self.params['initial_soc'] - self.battery.params['min_soc']) / self.params['soc_interval'])

        # Traveling forwards through DP solution
        for i in range(0, self.num_time_intervals - 1):
            next_index = int(self.CF[next_index, i])
            this_soc = next_soc
            next_soc = (next_index * self.params['soc_interval']) + self.battery.params['min_soc']
            next_charge_rate = soc_to_charge_rate(next_soc - this_soc,
                                                  self.battery.params['capacity'],
                                                  self.time_interval_in_hours)

            # Update optimal profile
            self.optimal_profile.append(next_soc)

            # Update charge rate
            self.charge_rate.append(next_charge_rate)

            # Update solar curtailment
            self.solar_curtailment.append(self.SC[next_index, i])

        self.solar_curtailment.append(0)
        self.charge_rate.append(0)

    def solve(self, scenario, battery):
        """ See parent AbstractBatteryController class for parameter descriptions """

        starting_soc = battery.soc

        # check if the initial state of charge is within the soc_interval
        interval = self.params["soc_interval"]
        offset = utility.get_discretisation_offset(starting_soc, interval)
        if offset != 0.0:
            warnings.warn(f"Adjusting starting_soc by -{offset} to fit into the 'soc_interval' of {interval}")
            battery_copy = battery.copy()
            battery_copy.params['current_soc'] = battery_copy['current_soc'] - offset
            return self.solve(scenario, battery_copy)

        # check battery min_soc/max_soc within soc_interval
        battery_min_soc_offset = utility.get_discretisation_offset(battery.params["min_soc"], interval)
        if battery_min_soc_offset != 0.0:
            warnings.warn(
                f"Adjusting battery min_soc parameter by +{battery_min_soc_offset} to fit into the 'soc_interval' "
                f"of {interval}")
            battery.update_params({"min_soc": battery.params["min_soc"] + battery_min_soc_offset})
        battery_max_soc_offset = utility.get_discretisation_offset(battery.params["max_soc"], interval)
        if battery_max_soc_offset != 0.0:
            warnings.warn(
                f"Adjusting battery max_soc parameter by -{battery_max_soc_offset} to fit into the 'soc_interval' "
                f"of {interval}")
            battery.update_params({"max_soc": battery.params["max_soc"] - battery_max_soc_offset})

        # Out of interest, keep track of timing
        ts_dpstart = dt.datetime.now().timestamp()

        # For more readable code, store individual entities locally
        self.generation = scenario['generation']
        self.demand = scenario['demand']
        self.tariff_import = scenario['tariff_import']
        self.tariff_export = scenario['tariff_export']

        # TODO Differentiate between static and dynamic import/export limits
        self.import_limit = scenario['import_limit']
        self.export_limit = scenario['export_limit']

        self.battery = battery

        self.params['initial_soc'] = battery.params['current_soc']

        # Initialise dynamic program grid and parameters
        self._initialise_dp()

        # If we want a specific final soc then bias starting conditions
        if self.params['constrain_final_soc']:
            self._constrain_final_soc()

        # Run actual DP
        self._run_dynamic_program()

        # Calculate optimal profile
        self._calculate_optimal_profile()

        # TODO Consider adding subfunction to ensure all charge rates and SOCs are feasible

        # Output total run time
        ts_dp_total = dt.datetime.now().timestamp() - ts_dpstart
        if self.debug:
            print("Total run time:", pretty_time(ts_dp_total))

        return pd.DataFrame(data={
            'timestamp': scenario.index,
            'charge_rate': self.charge_rate,
            'soc': self.optimal_profile,
            'solar_curtailment': self.solar_curtailment,
        }).set_index('timestamp')
