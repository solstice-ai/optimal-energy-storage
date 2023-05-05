import pandas as pd
from oes.schedulers.abstract_battery_scheduler import BatteryScheduler
import oes.util.general as utility


class DPScheduler(BatteryScheduler):
    """
    Base class for battery scheduler that tries to emulate the dynamic program solution in terms of
    rule-based controllers
    """

    def __init__(self, name="DPScheduler", params=None):
        super().__init__(name=name, params=params)

        # Define class variables
        self.scenario = None
        self.battery = None
        self.controllers = None
        self.starting_soc = None

        self.solution_optimal = None

        self.charge_rates_all = None
        self.charge_rates_final = None
        self.near_optimal = None
        self.full_schedule = None
        self.short_schedule = None

    def _find_all_charge_rates(self):
        """ For all controllers, calculate their charge rates over full horizon """
        self.charge_rates_all = pd.DataFrame()

        for (c_name, c_type) in self.controllers:
            print("Finding solution for", c_name, "...")

            self.params["constrain_charge_rate"] = False
            controller = c_type(params=self.params)
            solution = controller.solve(self.scenario,
                                        self.battery)

            # Add to dataframe of all solutions
            self.charge_rates_all[c_name] = solution["charge_rate"]

        self.charge_rates_all["timestamp"] = self.solution_optimal.index
        self.charge_rates_all = self.charge_rates_all.set_index("timestamp")

    def _find_nearest_optimal(self):
        """
        For all controllers, across all intervals, determine which ones are close (within threshold) to optimal.
        This function assumes that self._find_all_charge_rates has been previously run.
        """
        self.near_optimal = pd.DataFrame()

        # Use same time stamps as charge_rates
        self.near_optimal["timestamp"] = self.charge_rates_all.index
        self.near_optimal = self.near_optimal.set_index("timestamp")

        # Loop through all controllers
        for c_name in self.charge_rates_all:
            near_optimal = []

            # For each interval, check if this controller is close to optimal DP solution
            for c_val, opt_val in zip(self.charge_rates_all[c_name], self.solution_optimal["charge_rate"]):
                if abs(c_val - opt_val) < self.params["threshold_near_optimal"]:
                    near_optimal.append(1)
                else:
                    near_optimal.append(0)

            self.near_optimal[c_name] = near_optimal

    def _fill_individual_gaps(self):
        """
        For each controller, fill any gaps smaller than some limit
        """
        near_optimal_filled = self.near_optimal.copy()

        # Fill any individual gaps
        for c in range(0, len(near_optimal_filled.columns)):
            for i in range(1, len(near_optimal_filled) - 1):
                if near_optimal_filled.iloc[i - 1, c] == 1 and near_optimal_filled.iloc[i + 1, c] == 1:
                    near_optimal_filled.iloc[i, c] = 1

        self.near_optimal = near_optimal_filled

    def _find_controller_finish(self, near_optimal, c_name, time_from=None):
        """
        Small helper function to determine how long a near-optimal algorithm should run for (i.e., how many
        consecutive ones does it have)
        :param near_optimal: pandas dataframe with index timestamps, and column for c_name
        :param c_name: name of controller to check
        :param time_from: from when to start checking
        :return: pandas Timestamp indicating until when controller runs for
        """
        if time_from is None:
            time_from = near_optimal.index[0]

        resolution = pd.Timedelta(near_optimal.index[1] - near_optimal.index[0])

        next_interval = time_from + resolution

        while next_interval < near_optimal.index[-1]:
            if near_optimal.loc[next_interval, c_name] == 0:
                return next_interval
            next_interval = next_interval + resolution

        return next_interval

    def _clean_full_schedule(self):
        """ Handle intervals where no near-optimal controller was found """

        print("Cleaning full schedule ...")
        full_schedule_clean = self.full_schedule.copy()

        # TODO handle 'DN' at start of schedule

        # Any DNs that are only one interval and have the same controller either side, just fill with that controller
        for i in range(1, len(full_schedule_clean.index) - 1):
            if full_schedule_clean.iloc[i - 1] == full_schedule_clean.iloc[i + 1]:
                full_schedule_clean.iloc[i] = full_schedule_clean.iloc[i + 1]

        # Any remaining DNs, find the closest controller
        for ts in full_schedule_clean.index:
            if full_schedule_clean[ts] == 'DN':
                closest_controller = self.controllers[0]
                closest_controller_value = abs(self.charge_rates_all.loc[ts, self.controllers[0][0]] -
                                               self.solution_optimal.charge_rate[ts])
                for controller in self.controllers[1:]:
                    this_controller_value = abs(self.charge_rates_all.loc[ts, controller[0]] -
                                                self.solution_optimal.charge_rate[ts])
                    if this_controller_value < closest_controller_value:
                        closest_controller_value = this_controller_value

                full_schedule_clean.loc[ts] = closest_controller[0]

        self.full_schedule_clean = full_schedule_clean

    def _generate_full_schedule(self):
        """
        Using 'near-optimal' binary values, generate a schedule of controllers
        for every time interval
        """
        print("Generating initial full schedule ...")

        resolution = pd.Timedelta(self.near_optimal.index[1] - self.near_optimal.index[0])

        best_controller = []

        for ts in self.near_optimal.index:

            # Find all controllers that are optimal at this timestamp (ignoring DN)
            multiple_best_controllers = []
            for (c_name, _) in self.controllers.items():
                if c_name == "DN":
                    continue
                if self.near_optimal.loc[ts, c_name] == 1:
                    multiple_best_controllers.append(c_name)

            # If none found, then use 'do nothing', 'DN' for now -- this is cleaned up later
            if len(multiple_best_controllers) == 0:
                best_controller.append("DN")

            # If one found, use that
            elif len(multiple_best_controllers) == 1:
                best_controller.append(multiple_best_controllers[0])

            # If multiple found, choose the one that runs the longest
            else:
                # Initialise curr finish, curr best controller
                curr_finish = ts + resolution
                curr_best_controller = multiple_best_controllers[0]
                for c_name in multiple_best_controllers:
                    this_finish = self._find_controller_finish(self.near_optimal, c_name, time_from=ts)
                    if this_finish > curr_finish:
                        curr_finish = this_finish
                        curr_best_controller = c_name
                best_controller.append(curr_best_controller)

        self.full_schedule = pd.Series(index=self.charge_rates_all.index, data=best_controller)

    def _generate_short_schedule(self, use_clean: bool = True):
        """
        Generate a shortened version of full schedule that only keeps track of changes to a new controller
        Assumes that a full schedule has previously been calculated.
        """

        timestamps = []
        controller = []

        curr_controller = None

        # Assuming a clean schedule has been generated, use that by default
        if use_clean:
            schedule = self.full_schedule_clean
        else:
            schedule = self.full_schedule

        for ts in self.full_schedule.index:
            this_controller = schedule[ts]
            if this_controller != curr_controller:
                timestamps.append(ts)
                controller.append(this_controller)
                curr_controller = this_controller

        self.short_schedule = pd.Series(index=timestamps, data=controller)

    def print_schedule(self):
        """
        Print out schedule in easy to read format
        """

        # If short schedule has not yet been calculated, do so
        if self.short_schedule is None:
            self._generate_short_schedule()

        print("Schedule: ")
        for ix in range(0, len(self.short_schedule.index) - 1):
            print(" - from", self.short_schedule.index[ix], "to", self.short_schedule.index[ix + 1],
                  "use", self.short_schedule.iloc[ix])
        print(" - from", self.short_schedule.index[-1], "to", self.full_schedule_clean.index[-1],
              "use", self.short_schedule.iloc[-1])

    def _calculate_schedule_charge_rates(self):
        """
        Determine which charge rate from which controller to use at which interval
        """
        charge_rates_final = []
        for ts in self.full_schedule_clean.index:
            curr_controller = self.full_schedule_clean[ts]
            charge_rates_final.append(self.charge_rates_all.loc[ts, curr_controller])

        self.charge_rates_final = pd.Series(index=self.full_schedule_clean.index, data=charge_rates_final)

    def calculate_performance(self):
        """
        Determine how this schedule would have actually performed in this scenario
        """

        # We can reuse the provided optimal solution (for guess at soc, and for solar curtailment)
        # But we need to use charge rates that result from using this scheduler
        solution = self.solution_optimal.copy()
        solution["charge_rate"] = self.charge_rates_final

        # Now return performance
        return utility.calculate_solution_performance(self.scenario, solution, self.battery)

    def solve(self, scenario, battery, controllers, solution_optimal):
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

        # Store parameters locally
        self.scenario = scenario
        self.battery = battery
        self.controllers = controllers
        self.starting_soc = battery.params["current_soc"]
        self.solution_optimal = solution_optimal

        # If params were not set when instantiating, set defaults
        if "threshold_near_optimal" not in self.params:
            # use 10% of max charge rate as threshold
            self.params["threshold_near_optimal"] = battery.params["max_charge_rate"] * 0.1
        if "resample_length" not in self.params:
            self.params["resample_length"] = "30 minutes"
        if "fill_individual_gaps" not in self.params:
            self.params["fill_individual_gaps"] = False

        # Determine charge rates for all controllers
        self._find_all_charge_rates()

        # Determine which controllers match optimal (DP) most closely
        self._find_nearest_optimal()

        # Clean up nearest optimal by filling gaps
        if self.params["fill_individual_gaps"]:
            self._fill_individual_gaps()

        # Convert to a full schedule (one controller for every interval)
        self._generate_full_schedule()

        # Clean full schedule (handle intervals where no near-optimal controller was found)
        self._clean_full_schedule()

        # Convert to a short schedule
        self._generate_short_schedule()

        # Calculate charge rates resulting from the clean schedule at each interval
        self._calculate_schedule_charge_rates()

        print("Complete.")
