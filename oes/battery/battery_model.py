from typing import Union


default_battery_params = {
    'capacity': 13500.0,                              # battery capacity, in Wh
    'max_charge_rate': 7000.0,                        # peak charge rate, in W
    'max_discharge_rate': 7000.0,                     # peak discharge rate, in W
    'max_soc': 94.0,                                # max soc we can charge to, in %
    'min_soc': 20.0,                                # min soc we can discharge to, in %
    'soc': 50.0,                                    # current soc, in %
    'degradation_cost_per_kwh_charge': 0.0,         # degradation cost per kWh of charge, in $
    'degradation_cost_per_kwh_discharge': 0.0,      # degradation cost per kWh of discharge, in $
    'efficiency_charging': 100.0,                   # efficiency of charging, in %
    'efficiency_discharging': 100.0,                # efficiency of discharging, in %
}


class BatteryModel:
    """
    Simple battery model to keep track of battery parameters and battery state of charge.
    """

    def __init__(self, params: dict = {}) -> None:
        """
        Initialise battery model.  For some parameters, default values are set if they are not passed in.
        :param params: dictionary of <parameter_name>, <parameter_value> pairs
        :return: None
        """

        # set the defaults, None means that parameter has to be passed in the input params dictionary
        self.capacity: Union[float, None] = None  # battery capacity, in Wh
        self.max_charge_rate: Union[float, None] = None  # peak charge rate, in W
        self.max_discharge_rate: Union[float, None] = None  # peak discharge rate, in W
        self.max_soc: Union[float, None] = None  # max soc we can charge to, in %
        self.min_soc: Union[float, None] = None  # min soc we can discharge to, in %
        self.soc: Union[float, None] = None  # current soc, in %
        self.degradation_cost_per_kwh_charge: float = 0.0  # degradation cost per kWh of charge, in $
        self.degradation_cost_per_kwh_discharge: float = 0.0  # degradation cost per kWh of discharge, in $
        self.efficiency_charging: float = 100.0  # efficiency of charging, in %
        self.efficiency_discharging: float = 100.0  # efficiency of discharging, in %

        # Update the above with input params, which also validates the params
        self.update_params(params)

    def update_params(self, params: dict) -> None:
        """
        Update battery parameters
        :param params: dictionary of <parameter_name>, <parameter_value> pairs
        :return: None
        """
        for key, value in params.items():
            setattr(self, key, value)
        self.validate_params()

    def validate_params(self) -> None:
        """
        Check that all parameters have values (none are None), and perform some sanity checks on value ranges
        """

        # Check for missing attributes
        missing_attributes = []
        for attrib in self.__dict__.keys():
            if getattr(self, attrib) is None:
                missing_attributes.append(attrib)
        if len(missing_attributes) > 0:
            raise AttributeError(f"Input parameters must include {str(missing_attributes)}")

        # Check value ranges are valid
        if self.capacity <= 0:
            raise AttributeError("capacity must be a positive value")
        if self.max_charge_rate <= 0:
            raise AttributeError("max_charge_rate must be a positive value")
        if self.max_discharge_rate <= 0:
            raise AttributeError("max_discharge_rate must be a positive value")
        if (self.max_soc > 100) | (self.max_soc < 0):
            raise AttributeError("max_soc must be between 0 and 100")
        if (self.min_soc > 100) | (self.min_soc < 0):
            raise AttributeError("min_soc must be between 0 and 100")
        if (self.soc > 100) | (self.soc < 0):
            raise AttributeError("soc must be between 0 and 100")
        if (self.soc > self.max_soc) | (self.soc < self.min_soc):
            raise AttributeError("soc must be between min_soc and max_soc")
        if self.max_soc < self.min_soc:
            raise AttributeError("max_soc must be greater than min_soc")
        if self.degradation_cost_per_kwh_charge < 0:
            raise AttributeError("degradation_cost_per_kWh_charge must be >= 0")
        if self.degradation_cost_per_kwh_discharge < 0:
            raise AttributeError("degradation_cost_per_kWh_discharge must be >= 0")
        if (self.efficiency_charging > 100.0) | (self.efficiency_charging <= 0.0):
            raise AttributeError("efficiency_charging must be a positive value between 0 and 100")
        if (self.efficiency_discharging > 100.0) | (self.efficiency_discharging <= 0.0):
            raise AttributeError("efficiency_discharging must be a positive value between 0 and 100")
        return

    def compute_degradation_cost(self, change_soc_in_wh: float) -> float:
        """ Calculate the degradation cost of a change in state of charge """
        if change_soc_in_wh > 0:  # charging
            return abs(change_soc_in_wh * self.degradation_cost_per_kwh_charge/1000)
        else:  # discharging
            return abs(change_soc_in_wh * self.degradation_cost_per_kwh_discharge/1000)

    def determine_impact_charge_rate_efficiency(self, charge_rate: float) -> float:
        """
        Calculate the impact of battery charge/discharge by a specified rate, taking efficiency
        of charging / discharging into account
        :param charge_rate: desired battery charge rate, in W
        :return: the impact of the battery resulting from this change in SOC, in W (float)
        """
        if charge_rate > 0:  # charging
            return charge_rate / (self.efficiency_charging/100)
        else:  # discharging
            return charge_rate * (self.efficiency_discharging/100)

    def compute_soc_change_wh(self, soc_change_percent: float) -> float:
        """
        Convert change in SOC percentage to a change in capacity Wh
        """
        return soc_change_percent / 100.0 * self.capacity
