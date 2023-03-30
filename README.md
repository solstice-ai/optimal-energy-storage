# optimal-energy-storage
Multiple solutions for optimal energy storage operation

---

## Install
To install this locally, simply run:

```bash
make local-install
```

---

## Usage
Some simple examples of how this library can be used are included in the jupyter notebook
[example_usage.ipynb](example_usage.ipynb).

---

## Battery Model

A simple battery model is provided as a separate class.  This model keeps track of battery-specific 
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
from oes import BasicBatteryModel, default_battery_params
battery = BasicBatteryModel(default_battery_params)
```


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
