import pandas as pd
import numpy as np
import sys
import datetime as dt
import warnings
import copy
from typing import Tuple, Optional

from oes.controllers.abstract_battery_controller import AbstractBatteryController
from oes.battery.battery_model import BatteryModel
from oes.util.conversions import soc_to_charge_rate, resolution_in_hours
from oes.util.output import pretty_time
from oes.util.cost_function_helpers import compute_state_transition_cost
from oes.util.general import get_discretisation_offset


class LimitMode:
    """ A class to help standardise import and export limit modes """
    no_limit = "no_limit"
    static_limit = "static_limit"
    dynamic_limit = "dynamic_limit"

    @staticmethod
    def to_list():
        return [LimitMode.no_limit, LimitMode.static_limit, LimitMode.dynamic_limit]


class DynamicProgramController(AbstractBatteryController):
    """ Optimal battery control using dynamic programming """

    def __init__(self, params: dict = {}, battery_model: BatteryModel = None, debug: bool = False):
        """
        Creates a new instance of this controller
        :param params: the parameters for the optimisation
        :param battery_model: the battery model to use
        :param debug: boolean flag indicating whether to print out debug messages
        """
        super().__init__(name=self.__class__.__name__, params=params, battery_model=battery_model, debug=debug)

        # ----------------------------------------------------------------------------
        # Set default values for input params
        self.soc_interval: float = 1.0  # soc discretisation (in %)
        self.constrain_final_soc: bool = True  # Do we want to specify final soc
        self.final_soc: float = 50.0  # Desired final soc
        self.minimize_activity: bool = False  # Whether to minimise number of intervals in which there is charging
        self.prioritize_early_charge = False  # Whether to try to charge battery earlier rather than later
        self.include_battery_degradation_cost = False  # Whether to include consideration of battery degradation cost
        self.limit_import_mode: str = LimitMode.no_limit  # Whether to have no, static, or dynamic import limit
        self.limit_export_mode: str = LimitMode.no_limit  # Whether to have no, static, or dynamic export limit
        self.limit_import_value: Optional[float] = None  # When static import limit, use this value
        self.limit_export_value: Optional[float] = None  # When static export limit, use this value
        self.include_charge_loss: bool = False  # Whether to multiply by a loss factor for (dis-)charging of battery
        self.allow_solar_curtailment: bool = False  # Allow consideration of solar curtailment at each interval

        # ----------------------------------------------------------------------------
        # Update the above with input params, which also validates the params
        self.update_params(params)

        # ----------------------------------------------------------------------------
        # Initialise local variables -- these will all be set when "solve" is called
        self.num_time_intervals: Optional[int] = None  # Number of time intervals in the scenario
        self.interval_size_in_hours: Optional[float] = None  # Helper var representing size of interval in hours
        self.num_soc_states: Optional[int] = None  # Number of possible state of charge states
        self.max_soc_increase: Optional[float] = None
        self.max_soc_increase_interval: Optional[int] = None
        self.max_soc_decrease: Optional[float] = None
        self.max_soc_decrease_interval: Optional[int] = None

        # ----------------------------------------------------------------------------
        # Initialise variables that will hold time series data
        self.generation: Optional[list] = None  # Generation time series data
        self.demand: Optional[list] = None  # Demand time series data
        self.tariff_import: Optional[list] = None  # Import tariff time series data
        self.tariff_export: Optional[list] = None  # Export tariff time series data
        self.limit_import_time_series: Optional[list] = None  # Import limit time series data
        self.limit_export_time_series: Optional[list] = None  # Export limit time series data

        # ----------------------------------------------------------------------------
        # Initialise variable that will hold battery model
        self.initial_soc: Optional[float] = None  # Stored when receiving battery model for later use

        # ----------------------------------------------------------------------------
        # Initialise matrices used when solving the dynamic program
        self.CTG: Optional[np.ndarray] = None  # 2D array that tracks "cost to go" of every state, interval
        self.CF: Optional[np.ndarray] = None  # 2D array that tracks "came from" for every state, interval
        self.SC: Optional[np.ndarray] = None  # 2D array that tracks "solar curtailment" of every state, interval

        # ----------------------------------------------------------------------------
        # Initialise variables that will hold solution outputs of dynamic program
        self.optimal_profile: Optional[list] = None
        self.charge_rate: Optional[list] = None
        self.solar_curtailment: Optional[list] = None

    def update_params(self, params: dict) -> None:
        """
        Update battery parameters
        :param params: dictionary of <parameter_name>, <parameter_value> pairs
        :return: None
        """
        super().update_params(params)
        self.validate_params()

    def validate_params(self):
        """ Run a number of checks to make sure parameters are valid """

        # Sanity check for soc_interval, multiply by 100 to avoid floating point issues
        if get_discretisation_offset(100, self.soc_interval) != 0.0:
            raise ValueError("Invalid 'soc_interval' parameter passed. It needs to be able to divide 100% state of "
                             "charge without residue")

        # Several type and range checks
        if (self.final_soc > 100) | (self.final_soc < 0):
            raise AttributeError("final_soc must be between 0 and 100")
        if self.limit_import_mode not in LimitMode.to_list():
            raise AttributeError(f"limit_import_mode must be one of {LimitMode.to_list()}")
        if self.limit_export_mode not in LimitMode.to_list():
            raise AttributeError(f"limit_export_mode must be one of {LimitMode.to_list()}")

        # When import / export limit is static, a limit value must be specified
        if (self.limit_import_mode == LimitMode.static_limit) & (self.limit_import_value is None):
            raise AttributeError("When using a static import limit, limit_import_value must be set")
        if (self.limit_export_mode == LimitMode.static_limit) & (self.limit_export_value is None):
            raise AttributeError("When using a static export limit, limit_export_value must be set")

    def _process_inputs(self, scenario: pd.DataFrame):
        """ Helper function to process inputs """

        # Number of time intervals and interval size are determined by the resolution of the time series data.
        self.num_time_intervals = len(scenario.index)
        self.interval_size_in_hours = resolution_in_hours(scenario)

        # These four columns will always be provided as time series data.
        # For more readable code, store them locally
        self.generation = scenario["generation"]
        self.demand = scenario["demand"]
        self.tariff_import = scenario["tariff_import"]
        self.tariff_export = scenario["tariff_export"]

        # Import and export limits may be set as no_limit, static_limit, or dynamic_limit
        if self.limit_import_mode == LimitMode.no_limit:
            self.limit_import_time_series = [sys.float_info.max] * self.num_time_intervals
        elif self.limit_import_mode == LimitMode.static_limit:
            self.limit_import_time_series = [self.limit_import_value] * self.num_time_intervals
        elif self.limit_import_mode == LimitMode.dynamic_limit:
            self.limit_import_time_series = scenario["limit_import"]
        if self.limit_export_mode == LimitMode.no_limit:
            self.limit_export_time_series = [sys.float_info.max] * self.num_time_intervals
        elif self.limit_export_mode == LimitMode.static_limit:
            self.limit_export_time_series = [self.limit_export_value] * self.num_time_intervals
        elif self.limit_export_mode == LimitMode.dynamic_limit:
            self.limit_export_time_series = scenario["limit_export"]

        # Store battery locally -- as a copy, in case small changes are made.  Remember initial SOC.
        self.battery = copy.copy(self.battery)
        self.initial_soc = self.battery.soc

    def debug_msg_post_initialisation(self) -> str:
        """ Debug message after dynamic program initialisation """
        self.debug_message(
            f"The dynamic program grid has size {self.num_soc_states} (num soc states) x "
            f"{self.num_time_intervals} (num time intervals) \n"
            f"In each time interval ({self.interval_size_in_hours} hours), \n"
            f" - battery may    charge at most {self.battery.max_charge_rate * self.interval_size_in_hours:.0f}Wh, "
            f"a change in soc of {self.max_soc_increase * 100:.3f}% ({self.max_soc_increase_interval:d} intervals) \n"
            f" - battery may discharge at most {self.battery.max_discharge_rate * self.interval_size_in_hours:.0f}Wh, "
            f"a change in soc of {self.max_soc_decrease * 100:.3f}% ({self.max_soc_decrease_interval:d} intervals) \n"
        )

    def debug_msg_pre_dynamic_program(self) -> None:
        """ Debug message before dynamic program is run, returns current time in ms for timing """
        self.debug_message("Running dynamic program ...")
        self.debug_message("  0% ...")

    def debug_msg_update_dynamic_program(self, col) -> None:
        """ Debug message providing a progress update while dynamic program is running """
        interval_size_ten_percent = int(self.num_time_intervals / 10)
        cols_completed = self.num_time_intervals - col
        if (cols_completed % interval_size_ten_percent) == 0:
            self.debug_message(f" {int(cols_completed / interval_size_ten_percent) * 10}% ...")

    def debug_msg_post_dynamic_program(self, timestamp_start) -> None:
        """ Debug message after dynamic program completed """
        time_total = dt.datetime.now().timestamp() - timestamp_start
        self.debug_message("Total run time:", pretty_time(time_total))

    def _initialise_dp(self) -> None:
        """ Determine some parameters, run some checks, initialise grid, before running actual dynamic program """

        # Determine how many state of charge intervals to use
        self.num_soc_states = int((self.battery.max_soc - self.battery.min_soc) / self.soc_interval + 1)

        # Determine max / min change in soc from one time interval to the next
        self.max_soc_increase = self.battery.max_charge_rate * self.interval_size_in_hours / self.battery.capacity
        self.max_soc_increase_interval = round(self.max_soc_increase / self.soc_interval * 100)
        self.max_soc_decrease = -1 * self.battery.max_discharge_rate * self.interval_size_in_hours / \
                                self.battery.capacity
        self.max_soc_decrease_interval = round(self.max_soc_decrease / self.soc_interval * 100)

        # check if the initial state of charge is within an exact soc_interval, adjust if necessary
        offset = get_discretisation_offset(self.battery.soc, self.soc_interval)
        if offset != 0.0:
            warnings.warn(f"Adjusting starting_soc by -{offset} to fit into the 'soc_interval' of {self.soc_interval}")
            self.battery.soc = self.battery.soc - offset

        # check battery min_soc within soc_interval, increase if necessary
        battery_min_soc_offset = get_discretisation_offset(self.battery.min_soc, self.soc_interval)
        if battery_min_soc_offset != 0.0:
            warnings.warn(
                f"Adjusting battery min_soc parameter by +{self.soc_interval - battery_min_soc_offset}"
                f"to fit into the 'soc_interval' "
                f"of {self.soc_interval}")
            self.battery.min_soc = self.battery.min_soc + self.soc_interval - battery_min_soc_offset

        # check battery max_soc within soc_interval, decrease if necessary
        battery_max_soc_offset = get_discretisation_offset(self.battery.max_soc, self.soc_interval)
        if battery_max_soc_offset != 0.0:
            warnings.warn(
                f"Adjusting battery max_soc parameter by -{battery_max_soc_offset} to fit into the 'soc_interval' "
                f"of {self.soc_interval}")
            self.battery.max_soc = self.battery.max_soc - battery_max_soc_offset

        # Initialise CTG (cost to go), CF (came from), SC (solar curtail) matrices
        self.CTG = np.full((self.num_soc_states, self.num_time_intervals), sys.float_info.max)
        self.SC = np.full((self.num_soc_states, self.num_time_intervals - 1), 0.0)
        self.CF = np.empty((self.num_soc_states, self.num_time_intervals - 1))
        for i in range(0, self.num_soc_states):
            for j in range(0, self.num_time_intervals - 1):
                self.CF[i][j] = i

        # CTG last column must be zeros
        for i in range(0, self.num_soc_states):
            self.CTG[i][self.num_time_intervals - 1] = 0

        # If we want a specific final soc then bias starting conditions
        if self.constrain_final_soc:
            final_soc_index = int((self.final_soc - self.battery.min_soc) / self.soc_interval)
            self.CTG[final_soc_index, self.num_time_intervals - 1] = -1 * sys.float_info.max

        self.debug_msg_post_initialisation()

    def _compute_change_soc(self, soc_state_one: int, soc_state_two: int) -> Tuple[float, float]:
        """
        Helper to compute impact of battery on grid as a result in a change in SOC
        :param soc_state_one: first soc state (in percent)
        :param soc_state_two: second soc state (in percent)
        :return: change in soc as a percentage (float), change in soc as energy (Wh)
        """
        change_soc_percent = (soc_state_two - soc_state_one) * self.soc_interval  # Will be positive when charging
        change_soc_wh = self.battery.compute_soc_change_wh(change_soc_percent)
        return change_soc_percent, change_soc_wh

    def _compute_battery_impact(self, change_soc: float) -> Tuple[float, float]:
        """
        Helper to compute impact of battery on grid as a result in a change in SOC
        :param change_soc: change in battery SOC as percentage
        :return: battery impact in W (float), battery impact in Wh (float)
        """
        change_soc_wh = self.battery.compute_soc_change_wh(change_soc)
        change_soc_w = change_soc_wh / self.interval_size_in_hours

        # Actual battery impact will depend on battery charging efficiency
        battery_impact_w = self.battery.determine_impact_charge_rate_efficiency(change_soc_w)
        battery_impact_wh = battery_impact_w * self.interval_size_in_hours

        return battery_impact_w, battery_impact_wh

    def _compute_solar_curtailment(self, time_interval: int, battery_impact_w) -> Tuple[float, float]:
        """
        Helper to compute solar curtailment in a given time interval.  Assumes battery impact has been determined.
        :param time_interval: which time interval in scenario to consider
        :param battery_impact_w: impact of battery in this interval in W
        :return: solar curtailment in W (float), solar curtailment in Wh (float)
        """

        # If we are not allowing solar curtailment, no need to curtail
        if not self.allow_solar_curtailment:
            return 0.0, 0.0

        # If there is a benefit to exporting (positive export tariff), don't curtail
        if self.tariff_export[time_interval] >= 0:
            return 0.0, 0.0

        net_grid_impact_w = self.demand[time_interval] - self.generation[time_interval] + battery_impact_w

        # If we are anyway not going to net export, no need to curtail
        if net_grid_impact_w >= 0:
            return 0.0, 0.0

        # We only reach this point if solar curtailment allowed, export tariff negative, and we are about to export
        # Allow solar generation only to the point of creating zero net grid impact
        solar_curtailment_w = min(-1 * net_grid_impact_w, self.generation[time_interval])
        solar_curtailment_wh = solar_curtailment_w * self.interval_size_in_hours

        return solar_curtailment_w, solar_curtailment_wh

    def _compute_net_grid_impact(self, time_interval: int, battery_impact_w) -> Tuple[float, float]:
        """
        Helper to compute net grid impact in a given time interval.  Assumes battery impact has been determined.
        :param time_interval: which time interval in scenario to consider
        :param battery_impact_w: impact of battery in this interval in W
        :return: net grid impact in W (float), net grid impact in Wh (float)
        """
        # Positive means importing from grid, negative means exporting to grid
        # Remember that demand, generation are in W, change_soc is in Wh
        net_grid_impact_w = self.demand[time_interval] - self.generation[time_interval] + battery_impact_w
        net_grid_impact_wh = net_grid_impact_w * self.interval_size_in_hours

        return net_grid_impact_w, net_grid_impact_wh

    def _check_state_transition_within_limits(self, time_interval: int, net_grid_impact_w: float) -> bool:
        """
        Helper function to check if a state transition"s net grid impact is within allowed limits
        """
        if net_grid_impact_w < -1 * self.limit_export_time_series[time_interval]:
            return False
        if net_grid_impact_w > self.limit_import_time_series[time_interval]:
            return False
        return True

    def _run_dynamic_program(self) -> None:
        """
        Run the actual dynamic program that calculates all values in all matrices
        :return: None
        """

        timestamp_start = dt.datetime.now().timestamp()
        self.debug_msg_pre_dynamic_program()

        # Work our way backwards from last column of matrix to first column
        for col in range(self.num_time_intervals - 2, -1, -1):

            # Progress update
            self.debug_msg_update_dynamic_program(col)

            # Work our way up through all possible soc states
            for row in range(0, self.num_soc_states):

                # Find range of soc states that could reach this state
                prev_row_min = int(max(0, row + self.max_soc_decrease_interval))
                prev_row_max = int(min(self.num_soc_states - 1, row + self.max_soc_increase_interval))

                for prev_row in range(prev_row_min, prev_row_max + 1):

                    # Calculate change in SOC, battery impact, solar curtailment, net grid impact
                    change_soc_percent, change_soc_wh = self._compute_change_soc(row, prev_row)
                    battery_impact_w, battery_impact_wh = self._compute_battery_impact(change_soc_percent)
                    solar_curtailment_w, solar_curtailment_wh = self._compute_solar_curtailment(col, battery_impact_w)
                    net_grid_impact_w, net_grid_impact_wh = self._compute_net_grid_impact(col, battery_impact_w)

                    # Check if this state transition is ok (no import or export limit exceeded), and ignore it if not
                    if not self._check_state_transition_within_limits(col, net_grid_impact_w):
                        continue

                    # State transition cost is calculated using net grid impact in kWh
                    state_transition_cost = compute_state_transition_cost(
                        net_grid_impact_wh,
                        self.tariff_import[col],
                        self.tariff_export[col]
                    )

                    # If we are taking battery degradation cost into account, add relevant amount
                    if self.include_battery_degradation_cost:
                        degradation_cost = self.battery.compute_degradation_cost(change_soc_wh)
                        state_transition_cost = state_transition_cost + degradation_cost

                    # If we want to minimise charging activity, add a small cost when charging or discharging
                    if self.minimize_activity:
                        if not prev_row == row:
                            state_transition_cost = state_transition_cost + 0.001

                    # If we want to prioritise full charge earlier, add small cost to later intervals
                    if self.prioritize_early_charge:
                        state_transition_cost = state_transition_cost + \
                                                (self.num_soc_states - row) / self.num_soc_states / 500

                    # Calculate total cost to get there including this state transition
                    this_cost_to_get_there = self.CTG[row][col + 1] + state_transition_cost

                    # If this is better than existing entry, update
                    if (this_cost_to_get_there + 0.0001) < self.CTG[prev_row][col]:
                        self.CTG[prev_row][col] = this_cost_to_get_there
                        self.CF[prev_row][col] = row
                        self.SC[prev_row][col] = solar_curtailment_w

                    # Else if this is similar but has higher soc, update
                    elif (abs(this_cost_to_get_there - self.CTG[prev_row][col]) < 0.001) and (row > prev_row):
                        self.CTG[prev_row][col] = this_cost_to_get_there
                        self.CF[prev_row][col] = row
                        self.SC[prev_row][col] = solar_curtailment_w

        # Debug message after dynamic program completed
        self.debug_msg_post_dynamic_program(timestamp_start)

    def _calculate_optimal_profile(self) -> None:
        """
        Assuming dynamic program has been solved, calculate optimal profile by walking through solved matrix.
        :return: None
        """

        # Determine best route from starting soc, and track some values of interest
        next_soc = self.initial_soc
        self.optimal_profile = [next_soc]
        self.charge_rate = []
        self.solar_curtailment = []

        next_index = int((self.initial_soc - self.battery.min_soc) / self.soc_interval)

        # Traveling forwards through DP solution
        for i in range(0, self.num_time_intervals - 1):
            next_index = int(self.CF[next_index, i])
            this_soc = next_soc
            next_soc = (next_index * self.soc_interval) + self.battery.min_soc
            next_charge_rate = soc_to_charge_rate(next_soc - this_soc, self.battery.capacity,
                                                  self.interval_size_in_hours)

            # Update arrays
            self.optimal_profile.append(next_soc)
            self.charge_rate.append(next_charge_rate)
            self.solar_curtailment.append(self.SC[next_index, i])

        # Add zeros to ends of solar_curtailment and charge_rate to ensure same array lengths
        self.solar_curtailment.append(0)
        self.charge_rate.append(0)

    def solve(self, scenario):
        """ See parent AbstractBatteryController class for parameter descriptions """

        # Process input data
        self._process_inputs(scenario)

        # Initialise dynamic program grid and parameters
        self._initialise_dp()

        # Solve the full dynamic program
        self._run_dynamic_program()

        # Calculate optimal profile
        self._calculate_optimal_profile()

        return pd.DataFrame(data={
            "timestamp": scenario.index,
            "charge_rate": self.charge_rate,
            "soc": self.optimal_profile,
            "solar_curtailment": self.solar_curtailment,
        }).set_index("timestamp")
