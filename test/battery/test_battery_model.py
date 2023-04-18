from oes import BatteryModel, default_battery_params


def test_battery_model():
    model = BatteryModel(default_battery_params)
    model.validate_params()
    assert model.soc == default_battery_params["soc"]
    assert model.capacity == default_battery_params["capacity"]


def test_battery_degradation():
    model = BatteryModel(default_battery_params)
    assert model.compute_degradation_cost(50.0) == 0.0
    model.update_params({"degradation_cost_per_kwh_charge": 2.0})
    assert model.compute_degradation_cost(50.0) == 100.0
    assert model.compute_degradation_cost(-50.0) == 0.0
    model.update_params({"degradation_cost_per_kwh_discharge": 3.0})
    assert model.compute_degradation_cost(-50.0) == 150.0
