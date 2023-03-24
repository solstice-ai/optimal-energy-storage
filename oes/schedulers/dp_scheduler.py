import pandas as pd
import pickle
import sys

from oes.schedulers.abstract_battery_scheduler import BatteryScheduler
import oes.util.utility as utility


class DPScheduler(BatteryScheduler):
    """
    Base class for battery scheduler that tries to emulate the dynamic program solution in terms of
    rule-based controllers
    """

    def __init__(self, name='DPScheduler', params=None):
        super().__init__(name=name, params=params)

        # Define class variables
        self.scenario = None
        self.battery = None
        self.controllers = None
        self.starting_soc = None

        self.solution_optimal = None

        self.charge_rates = None
        self.near_optimal = None
        # self.full_schedule_initial = None
        self.full_schedule = None
        self.short_schedule = None

    def _find_all_charge_rates(self):
        """ For all controllers, calculate their charge rates over full horizon """
        self.charge_rates = pd.DataFrame()
        
        for (c_name, c_type) in self.controllers.items():
            print("Finding solution for", c_name, "...")

            # TODO This is a clumsy way to pass value of constrain_charge_rate, should clean this up
            self.params['constrain_charge_rate'] = False
            controller = c_type(params=self.params)
            solution = controller.solve(self.scenario,
                                        self.battery)
            solution = utility.calculate_values_of_interest(self.scenario, solution)

            # Add to dataframe of all solutions
            self.charge_rates[c_name] = solution['charge_rate']

        # While developing this schedule, read optimal DP based solution from file.
        # TODO later this will need to be calculated here!
        # solution_optimal = pickle.load(open('../data/result_dp_30min.pickle', 'rb'))

        # Need to shift optimal by one interval ?
        # charge_rates_DP = [0] + list(solution_optimal['charge_rate'])
        # charge_rates_DP = charge_rates_DP[:-1]
        # charge_rates_DP = list(solution_optimal['charge_rate'])
        # self.charge_rates['DP'] = charge_rates_DP

        self.charge_rates['timestamp'] = self.solution_optimal.index
        self.charge_rates = self.charge_rates.set_index('timestamp')

    def _find_nearest_optimal(self):
        """
        For all controllers, across all intervals, determine which ones are close (within threshold) to optimal.
        This function assumes that self._find_all_charge_rates has been previously run.
        """
        self.near_optimal = pd.DataFrame()

        # Use same time stamps as charge_rates
        self.near_optimal['timestamp'] = self.charge_rates.index
        self.near_optimal = self.near_optimal.set_index('timestamp')

        # Loop through all controllers
        for c_name in self.charge_rates:
            near_optimal = []

            # For each interval, check if this controller is close to optimal DP solution
            for c_val, opt_val in zip(self.charge_rates[c_name], self.solution_optimal['charge_rate']):
                if abs(c_val - opt_val) < self.params['threshold_near_optimal']:
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
            if full_schedule_clean.iloc[i - 1, 0] == full_schedule_clean.iloc[i + 1, 0]:
                full_schedule_clean.iloc[i, 0] = full_schedule_clean.iloc[i + 1, 0]

        # Any remaining DNs, find closest controller
        for ts in full_schedule_clean.index:
            if full_schedule_clean.loc[ts, 'full_schedule'] == 'DN':
                cont_keys = list(self.controllers)
                closest_controller = self.controllers[cont_keys[0]]
                closest_controller_value = abs(self.charge_rates.loc[ts, cont_keys[0]] -
                                               self.solution_optimal.charge_rate[ts])
                for cont_key in cont_keys[1:]:
                    this_controller_value = abs(self.charge_rates.loc[ts, cont_key] -
                                                self.solution_optimal.charge_rate[ts])
                    if this_controller_value < closest_controller_value:
                        closest_controller = self.controllers[cont_key]
                        closest_controller_value = this_controller_value

                full_schedule_clean.loc[ts, 'full_schedule'] = closest_controller.__name__

        ###  OLD CODE MAYBE STILL USEFUL LATER
        # Fill any individual gaps
        #for i in range(1, len(full_schedule_clean.index) - 1):
        #    if full_schedule_clean.iloc[i - 1, 0] == full_schedule_clean.iloc[i + 1, 0]:
        #        full_schedule_clean.iloc[i, 0] = full_schedule_clean.iloc[i + 1, 0]
        #full_schedule_clean.rename(columns={'full_schedule': 'full_schedule'}, inplace=True)

        self.full_schedule_clean = full_schedule_clean

    def _generate_full_schedule(self):
        """
        Using 'near-optimal' binary values, generate a schedule of controllers
        for every time interval
        """
        print("Generating initial full schedule ...")

        resolution = pd.Timedelta(self.near_optimal.index[1] - self.near_optimal.index[0])

        # TODO:  Why is this a dataframe?  Should be a series.
        self.full_schedule = pd.DataFrame()

        # Use same time stamps as charge_rates
        self.full_schedule['timestamp'] = self.charge_rates.index
        self.full_schedule = self.full_schedule.set_index('timestamp')

        best_controller = []

        for ts in self.near_optimal.index:

            # Find all controllers that are optimal at this timestamp (ignoring DN)
            multiple_best_controllers = []
            for (c_name, _) in self.controllers.items():
                if c_name == 'DN':
                    continue
                if self.near_optimal.loc[ts, c_name] == 1:
                    multiple_best_controllers.append(c_name)

            # If none found, then use 'do nothing', 'DN' for now -- this is cleaned up later
            if len(multiple_best_controllers) == 0:
                best_controller.append('DN')

            # If one found, use that
            elif len(multiple_best_controllers) == 1:
                best_controller.append(multiple_best_controllers[0])

            # If multiple found, choose the one that runs the longest
            else:
                # Initialise curr finish, curr best controller
                curr_finish = ts + resolution
                curr_best_controller = multiple_best_controllers[0]
                for c_name in multiple_best_controllers:
                    this_finish = self._find_controller_finish(self.near_optimal,
                                                               c_name,
                                                               time_from=ts)
                    if this_finish > curr_finish:
                        curr_finish = this_finish
                        curr_best_controller = c_name
                best_controller.append(curr_best_controller)

        self.full_schedule['full_schedule'] = best_controller

    def _generate_short_schedule(self):
        """
        Generate a shortened version of full schedule that only keeps track of changes to a new controller
        Assumes that a full schedule has previously been calculated.
        """

        timestamps = []
        controller = []

        curr_controller = None

        for ts in self.full_schedule.index:
            this_controller = self.full_schedule.loc[ts, 'full_schedule']
            if this_controller != curr_controller:
                timestamps.append(ts)
                controller.append(this_controller)
                curr_controller = this_controller

        self.short_schedule = pd.DataFrame(
            data={
                'timestamp': timestamps,
                'controller': controller
            }).set_index('timestamp')

    def calculate_schedule_charge_rates(self, resolution, scenario):
        """
        Calculate charge rates that this schedule would generate at this resolution
        Assumes that a full schedule has been previously calculated
        :param resolution: timedelta indicating at which resolution the charge rates should be calculated
        """

        # Initialise charge_rates dataframe using timestamps from scenario
        schedule_charge_rates = pd.DataFrame(data={'timestamp': scenario.index}).set_index('timestamp')

        # Resample to desired resolution
        schedule_charge_rates = schedule_charge_rates.resample(resolution).interpolate()

        # Use controllers specified by full schedule and fill forward if needed
        controllers = self.full_schedule.copy()
        controllers = controllers.resample(resolution).ffill()
        schedule_charge_rates['controller'] = controllers['full_schedule']

        # Calculate some params that the controllers need
        # TODO THIS IS SUPER MESSY and not a great way to do it. Clean up soon.
        controller_params = {
            'tariff_min': min(scenario['tariff_import']),
            'tariff_avg': sum(scenario['tariff_import']) / len(scenario.index)
        }
        time_interval_in_hours = utility.timedelta_to_hours(scenario.index[1]-scenario.index[0])

        # For every interval, calculate what the charge rate would be
        current_soc = self.starting_soc
        all_soc = [current_soc]
        all_charge_rates = [0]

        # TODO Do we really need to do all this?  Can we not just calculate rates found for each controller previously?
        # (and constrain SOC as needed)

        for ts, row in schedule_charge_rates.iloc[1:].iterrows():
            curr_controller_txt = row['controller']

            # Use correct controller as specified by schedule
            curr_controller_type = self.controllers[0][1]
            for (c_name, c_type) in self.controllers:
                if c_name == curr_controller_txt:
                    curr_controller_type = c_type

            curr_controller = curr_controller_type(params=self.params)

            # Calculate charge rate for this interval
            # TODO This is a clumsy way to pass value of constrain_charge_rate, should clean this up
            self.params['constrain_charge_rate'] = True
            controller_params['time_interval_in_hours'] = self.time_interval_in_hours
            charge_rate = curr_controller.solve_one_interval(scenario.loc[ts, :],
                                                             self.battery,
                                                             current_soc,
                                                             controller_params)
            # Update running variables
            all_charge_rates.append(charge_rate)
            all_soc.append(current_soc)
            current_soc = current_soc + utility.chargerate_to_soc(charge_rate,
                                                                  self.battery.params['capacity'],
                                                                  time_interval_in_hours)

        schedule_charge_rates['charge_rate'] = all_charge_rates
        schedule_charge_rates['soc'] = all_soc
        schedule_charge_rates.drop(columns=['controller'], inplace=True)

        return schedule_charge_rates

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
        self.starting_soc = battery.params['current_soc']
        self.solution_optimal = solution_optimal

        # If params were not set when instantiating, set defaults
        if 'threshold_near_optimal' not in self.params:
            # use 10% of max charge rate as threshold
            self.params['threshold_near_optimal'] = battery.params['max_charge_rate'] * 0.1
        if 'resample_length' not in self.params:
            self.params['resample_length'] = '30 minutes'
        if 'fill_individual_gaps' not in self.params:
            self.params['fill_individual_gaps'] = False

        # Determine charge rates for all controllers
        self._find_all_charge_rates()

        # Determine which controllers match optimal (DP) most closely
        self._find_nearest_optimal()

        # Clean up nearest optimal by filling gaps
        if self.params['fill_individual_gaps']:
            self._fill_individual_gaps()

        # Convert to a full schedule (one controller for every interval)
        self._generate_full_schedule()

        # Clean full schedule (handle intervals where no near-optimal controller was found)
        self._clean_full_schedule()

        # Convert to a short schedule
        self._generate_short_schedule()

        print("Complete.")
