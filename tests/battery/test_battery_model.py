from oes import BatteryModel, get_default_battery_params


def test_battery_model():
    model = BatteryModel(get_default_battery_params())
    model.validate_params()
    assert model.capacity == get_default_battery_params()["capacity"]


def test_battery_degradation():
    model = BatteryModel(get_default_battery_params())
    assert model.compute_degradation_cost(50.0) == 0.0
    model.update_params({"degradation_cost_per_kwh_charge": 2.0})
    assert model.compute_degradation_cost(50.0) == 0.1
    assert model.compute_degradation_cost(-50.0) == 0.0
    model.update_params({"degradation_cost_per_kwh_discharge": 3.0})
    assert model.compute_degradation_cost(-50.0) == 0.15
