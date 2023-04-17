# optimal-energy-storage
Multiple solutions for optimal energy storage operation

---

##### Table of Contents
  * [Install](#install)
  * [Usage](#usage)
  * [Battery Model](#battery-model)
  * [Scenario](#scenario)
  * [Units](#units)
  * [Controllers](#controllers)
  * [Testing](#testing)
  * [Release History](#release-history)

---

<a name="install"/>

## Install
To install this locally, simply run:

```bash
make local-install
```

---

## Usage
Some simple examples of how this library can be used are included in the jupyter notebook
[example_usage.ipynb](examples/example_usage.ipynb).

---

## Battery Model

A simple battery model is provided that keeps track of battery-specific 
parameters, and the battery's state.

Here are some example parameters:

```python
default_battery_params = {
    'capacity': 13500,                              # battery capacity, in Wh
    'max_charge_rate': 7000,                        # peak charge rate, in W
    'max_discharge_rate': 7000,                     # peak discharge rate, in W
    'max_soc': 94.0,                                # max soc we can charge to, in %
    'min_soc': 20.0,                                # min soc we can discharge to, in %
    'soc': 50.0,                                    # current soc, in %
    'degradation_cost_per_kWh_charge': 0.0,         # degradation cost per kWh of charge, in $
    'degradation_cost_per_kWh_discharge': 0.0,      # degradation cost per kWh of discharge, in $
    'efficiency_charging': 100.0,                   # efficiency of charging, in %
    'efficiency_discharging': 100.0,                # efficiency of discharging, in %
}
```

A battery model can be instantiated for example as follows:

```python
from oes import BatteryModel, default_battery_params

battery = BatteryModel(default_battery_params)
```

---

## Scenario

A scenario is a set of values for some given horizon (for example the next 24 hours), and includes the following:
- demand (W)
- generation (W)
- import_tariff ($/kWh)
- export_tariff  ($/kWh)

The scenario must be provided as a pandas DataFrame having an index of timestamps.

Any handling of time varying import and export tariffs, or forecasts of generation and demand, 
must be done outside of this package.  Likewise this package assumes regularly spaced intervals, 
and assumes that any gaps or interpolation are handled outside of this package.

Here is some example data (provided with this package) showing how a "scenario" should look:

```python
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
charge_controller = ChargeController()
```

If we want to set a specific charge rate (7000W), and avoid constraining it by battery max/min soc, we can
instead instantiate it like this:
```python
params = {
    'charge_rate': 7000,
    'constrain_charge_rate': False
}
charge_controller = ChargeController(params)
```



The following controllers have been implemented:

| Controller | Description |
| ---------- | ----------- |
| DoNothing  | Do nothing (no charge or discharge).  This controller can be helpful as a baseline.
| Charge     | Charge at a static rate    |
| Discharge  | Discharge at a static rate |
| SolarSelfConsumption | Charge rate is generation minus demand. In other words, when there is more generation than demand, charge with the excess generation; when there is more demand, discharge to meet this. |
| ImportTariffOptimisation | Discharge battery to meet demand when the import tariff is higher than average; charge battery at maximum possible rate when the import tariff is lower than average |







---

## Testing
The following command will run the test suite (tests still to be written):

```
python -m pytest -s tests
```

---

## Release History

- **0.2.0** - Multiple bugfixes and refactoring for cleaner passing of parameters
- **0.1.0** - First release with basic and rule-based controllers, and a first scheduler
