from oes.util.general import fix_decimal_issue, get_discretisation_offset, get_feasible_charge_rate
from oes import BatteryModel, get_default_battery_params


def test_fix_decimal_issue():
    assert fix_decimal_issue(0.111, precision=2) == 0.11
    assert fix_decimal_issue(0.111, precision=3) == 0.111
    assert fix_decimal_issue(0.111, precision=4) == 0.111

    assert fix_decimal_issue(1, precision=3) == 1.000
    assert fix_decimal_issue(1.05, precision=2) == 1.05
    assert fix_decimal_issue(1.006, precision=2) == 1.01


def test_get_discretisation_offset():
    assert get_discretisation_offset(state_of_charge=50, soc_interval=1, precision=2) == 0
    assert get_discretisation_offset(state_of_charge=51, soc_interval=2, precision=2) == 1
    assert get_discretisation_offset(state_of_charge=52, soc_interval=5, precision=2) == 2
    assert get_discretisation_offset(state_of_charge=52.8, soc_interval=0.1, precision=1) == 0
    assert get_discretisation_offset(state_of_charge=52.8, soc_interval=0.5, precision=2) == 0.3


def test_get_feasible_charge_rate_max_rates():
    bm = BatteryModel({
        "capacity": 100000,
        "max_charge_rate": 1000,
        "max_discharge_rate": 1000,
        "max_soc": 80,
        "min_soc": 20,
    })
    # test limit on charge rate
    assert get_feasible_charge_rate(charge_rate=1000, battery_model=bm, current_soc=50, time_interval=5) == 1000
    assert get_feasible_charge_rate(charge_rate=8000, battery_model=bm, current_soc=50, time_interval=5) == 1000

    # test limit on discharge
    assert get_feasible_charge_rate(charge_rate=-1000, battery_model=bm, current_soc=50, time_interval=5) == -1000
    assert get_feasible_charge_rate(charge_rate=-8000, battery_model=bm, current_soc=50, time_interval=5) == -1000


def test_get_feasible_charge_rate_min_max_soc():
    # test max soc exceeded
    bm = BatteryModel({
        "capacity": 10000,
        "max_charge_rate": 1000,
        "max_discharge_rate": 1000,
        "max_soc": 80,
        "min_soc": 20,
    })
    assert get_feasible_charge_rate(charge_rate=1000, battery_model=bm, current_soc=50, time_interval=5) == 600
    assert get_feasible_charge_rate(charge_rate=8000, battery_model=bm, current_soc=50, time_interval=5) == 600
