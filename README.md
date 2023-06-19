# Optimal Energy Storage (oes)
Multiple solutions for optimal energy storage operation

---

## Table of Contents
  * [Install](#install)
  * [Usage](#usage)
  * [Battery Model](#battery-model)
  * [Scenario](#scenario)
  * [Units](#units)
  * [Controllers](#controllers)
  * [Schedulers](#schedulers)
  * [Testing](#testing)

---

## Install

To install this package, simply run: 

```pip install oes``` 

If you want to **develop** this package, please install this locally by running:

```bash
make local-install
```

---

## Usage
Some simple examples of how this library can be used are included in the jupyter notebook
[example_usage.ipynb](examples/example_usage.ipynb).

A basic implementation requires a `BatteryModel`, which specifies the [battery parameters](#battery-model), a subclass 
of `AbstractBattery`, which represents the battery instance and has access to its state-of-charge, a 
[scenario](#scenario), which is provided as Pandas `DataFrame` and an [optimisation controller](#controllers). All these 
are explained in more detail below.

---

## Battery Model

A simple battery model is provided that keeps track of battery-specific parameters.

Here are some example parameters if you call `get_default_battery_params()`:

```python
{
    'capacity': 13500,                              # battery capacity, in Wh
    'max_charge_rate': 7000,                        # peak charge rate, in W
    'max_discharge_rate': 7000,                     # peak discharge rate, in W
    'max_soc': 94.0,                                # max soc we can charge to, in %
    'min_soc': 20.0,                                # current soc, in %
    'degradation_cost_per_kWh_charge': 0.0,         # degradation cost per kWh of charge, in $
    'degradation_cost_per_kWh_discharge': 0.0,      # degradation cost per kWh of discharge, in $
    'efficiency_charging': 100.0,                   # efficiency of charging, in %
    'efficiency_discharging': 100.0,                # efficiency of discharging, in %
}
```

A battery model only maintains parameters. To get an instance of an actual battery (which keeps track of state of 
charge, and any other changes in state), we need to pass the model to an object that is a sub-class of `AbstractBattery`
such as `SimulatedBattery` or your own implementation.

```python
from oes import BatteryModel, get_default_battery_params, SimulatedBattery

battery_model = BatteryModel(get_default_battery_params())
battery = SimulatedBattery(battery_model, initial_soc=50.0)
```

If you want to control your own battery, you have to provide an implementation of `AbstractBattery` that provides a
`get_current_soc()` method. This method implementation (that you have to write) can access the actual hardware and 
retrieve the current state-of-charge (provided as number between 0 and 100) and will be called by the optimisation
controller.

---

## Scenario

A scenario is a set of values for some given horizon (for example the next 24 hours), and includes the following:
- demand (W)
- generation (W)
- import_tariff ($/kWh)
- export_tariff  ($/kWh)

The scenario must be provided as a pandas `DataFrame` having an index of timestamps.

Any handling of time varying import and export tariffs, or forecasts of generation and demand, 
must be done outside of this package.  Likewise, this package assumes regularly spaced intervals, 
and assumes that any gaps or interpolation are handled outside of this package.

Here is some example data (provided with this package) showing how a "scenario" should look:

```python
import pickle

scenario = pickle.load(open('oes/data/example_data.pickle', 'rb'))
scenario.head()

	            generation	demand	tariff_import	tariff_export
timestamp				
2017-11-29 00:00:00	0	1370	0.2	        0.08
2017-11-29 00:01:00	0	1370	0.2	        0.08
2017-11-29 00:02:00	0	1360	0.2	        0.08
2017-11-29 00:03:00	0	1420	0.2	        0.08
2017-11-29 00:04:00	0	1380	0.2	        0.08
```


---

## Units

The following conventions regarding units are used throughout this package (chosen to match common industry usage):

- All time series data related to energy demand and generation: W
- All import and export tariffs: $/kWh
- All charge / discharge decisions:  W
- Battery degradation values:  $/kWh

Any time series data representing energy over the course of an interval (Wh) needs to be converted to power (W)
before being used within this package.

---

## Controllers

A number of different "controllers" are provided.  Each controller is instantiated with
its relevant parameters, and can then be used to "solve" a provided scenario.

Controllers use the same temporal resolution as the provided scenario -- in other words,
if half-hourly data is provided, the controller will provide half-hourly charge/discharge values.

The "solution" that a controller provides is a pandas DataFrame having the following structure:
- index of `timestamps` (same as the timestamps in the provided scenario)
- column `charge_rate`: battery charge (positive) or discharge (negative) value at each interval (in W)
- column `soc`: battery state of charge (in percentage) as a result of charge / discharge decisions

By default, a controller will keep track of battery SOC when generating a solution, and will
not return charging values that lead to battery exceeding max/min SOC.  This can be
overridden by passing parameter `'constrain_charge_rate': False`.  This can be useful, for example,
when calculating a schedule (see below).

Here is an example of how to create a very simple controller that only charges at a static rate:
```python
from oes import ChargeController

charge_controller = ChargeController(battery=battery)  # see battery definition above
```

If we want to set a specific charge rate (7000W), and avoid constraining it by battery max/min soc, we can
instead instantiate it like this:
```python
from oes import ChargeController

params = {
    'charge_rate': 7000,
    'constrain_charge_rate': False
}
charge_controller = ChargeController(params, battery=battery)  # see battery definition above
``` 



The following controllers have been implemented:


### Basic controllers

These are very simple controllers that can be used as baselines or to build more complex controllers or schedules.

| Controller | Description |
| ---------- | ----------- |
| DoNothingController  | Do nothing (no charge or discharge).  This controller can be helpful as a baseline, e.g. to determine cost when battery is not used at all.
| ChargeController     | Charge at a static rate    |
| DischargeController  | Discharge at a static rate |


### Rule-based controllers

Rule-based controllers make a decision in each interval based on information available in that interval.  In other words, they do not conduct any kind of optimisation over a longer horizon.

All rule-based controllers (and all basic controllers) must implement a function, `solve_one_interval(self, scenario_interval: pd.DataFrame) -> float` to ensure they can be used to build schedules of controllers later.

| Controller | Description |
| ---------- | ----------- |
| SolarSelfConsumptionController | Charge rate is generation minus demand. In other words, when there is more generation than demand, charge with the excess generation; when there is more demand, discharge to meet this. |
| ImportTariffOptimisationController | Discharge battery to meet demand when the import tariff is higher than average; charge battery at maximum possible rate when the import tariff is lower than average |
| SpotPriceArbitrageNaiveController | Assumes that both import and export tariff represent whole sale market price (plus maybe a network charge). Takes the average of max export tariff and min import tariff, and discharges when the current price is below this value, and charges when the current price is above this value. It ignores demand and generation.


### Optimisation-based controllers

These controllers determine the best possible set of charge and discharge values to minimise cost across the full scenario.

Optimisation-based controllers _do not_ need to implement the `solve_one_interval` function that rule-based controllers do.

| Controller | Description |
| ---------- | ----------- |
| DynamicProgramController | Full optimisation using dynamic programming |
| SpotPriceArbitrageOptimalController | Optimisation taking only import and export tariffs into account.  No consideration of demand and generation |

---

## Schedulers

Optimal controllers will find the best possible set of charge / discharge rates in discrete intervals for the full scenario.
However, in reality circumstances can change in seconds (loads being switched on and off, clouds passing over solar panels, etc.).
Sometimes a discrete solution is not good enough, and what is really needed is real-time fast response using a basic controller.

That's where a scheduler comes in.  The point of a scheduler is to take a number of very basic, simple controllers 
(that can respond to changes instantly), and to find a schedule that specifies which controller should be used when.
The goal is to ultimately emulate an optimal solution, without needing to choose specific charge rates for every
interval.

For now, just a single approach to scheduling has been provided as part of this package, which uses the output
of the optimal dynamic program controller as a way to choose a schedule of simpler controllers.
This can be instantiated simply:

```python
from oes import DPScheduler
scheduler = DPScheduler()
```

The scheduler then needs to be passed the scenario and battery, but also a list of basic controllers that should
be considered when determining the schedule.  Finally, it also needs the outputs of the (previously calculated)
optimal solution:

```python
# Generate list of controllers to use when generating schedule
from oes import DoNothingController, ChargeController, DischargeController, \
                SolarSelfConsumption, ImportTariffOptimisation, SpotPriceArbitrageNaive

controllers = [
    ('DN',  DoNothingController),
    ('C',   ChargeController),
    ('D',   DischargeController),
    ('SSC', SolarSelfConsumption),
    ('TO',  ImportTariffOptimisation),
    ('SPA', SpotPriceArbitrageNaive)
]

scheduler.solve(scenario, battery, controllers, solution_dp)
```

The scheduler subsequently:
1. Determines the charge rates at every interval for all controllers
2. Determines which controllers match optimal (DP) most closely in each interval
3. Generates a full schedule (one specific controller for every interval)
4. Conducts some clean up (handles intervals where no near-optimal controller was found)
5. Converts to a short schedule

This schedule typically performs as well as an optimal solution -- or even sometimes better
(since it can handle changes over very short intervals better).

For some examples, see the provided jupyter notebook
[example_usage.ipynb](examples/example_usage.ipynb).

---

## Testing
The following command will run the test suite (tests still to be written):

```
python -m pytest -s tests
```
