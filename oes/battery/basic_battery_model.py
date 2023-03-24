class BasicBatteryModel:
    """
    Base class for battery models
    """

    def __init__(self, params=None):
        """
        Initialise battery model.  For any parameters that aren't passed, default values are used.
        :param params: dictionary of <parameter_name>, <parameter_value> pairs
        """

        # Set parameters to default values
        self.params = {}

        self.params['capacity'] = 13500           # battery capacity in Wh
        self.params['max_charge_rate'] = 7000     # peak charge rate in W
        self.params['max_discharge_rate'] = 7000  # peak discharge rate in W

        self.params['max_soc'] = 94               # max soc we can charge to in %
        self.params['min_soc'] = 20               # min soc we can discharge to in %
        self.params['current_soc'] = 50           # current soc

        # When integrating lifetime cost of battery, these would be non-zero
        self.params['degradation_cost_per_kWh_charge'] = 0
        self.params['degradation_cost_per_kWh_discharge'] = 0

        # If considering loss factor for charging / discharging, these would be less than one
        self.params['loss_factor_charging'] = 1.0
        self.params['loss_factor_discharging'] = 1.0

        # Override defaults with any params that were passed
        if params is not None:
            for param in params:
                self.params[param] = params[param]

    def update_params(self, params):
        """
        Update battery parameters
        :param params: dictionary of <parameter_name>, <parameter_value> pairs
        :return: None
        """
        for param in params:
            self.params[param] = params[param]

    def compute_degradation_cost(self, change_soc_in_kwh):
        """
        Calculate the degradation cost of a change in state of charge
        """
        if change_soc_in_kwh > 0:  # charging
            cost_rate = self.params['degradation_cost_per_kWh_charge']
        else: cost_rate = self.params['degradation_cost_per_kWh_discharge'] # discharging

        return abs(change_soc_in_kwh * cost_rate)

    def apply_soc_change_loss(self, change_soc_in_kwh):
        """
        Calculate impact on battery taking loss
        factor into account
        Input is the change in SOC in kWh
        """
        if change_soc_in_kwh > 0:  # charging
            # Avoid divide by zero for a crazy bad battery 
            # this is a corner case that should never happen outside testing
            if self.params['loss_factor_charging'] == 0:
                battery_impact_kwh = change_soc_in_kwh / 0.000001
            else:
                battery_impact_kwh = change_soc_in_kwh / self.params['loss_factor_charging']
        else: # discharging
            # Avoid divide by zero for a crazy bad battery 
            if self.params['loss_factor_discharging'] == 0:
                battery_impact_kwh = change_soc_in_kwh * 0.000001
            else:
                battery_impact_kwh = change_soc_in_kwh * self.params['loss_factor_discharging']

        return battery_impact_kwh
    
    def compute_soc_change_kwh(self, soc_change_percent):
        """
        Convert change in SOC percantage to a change in capacity kWh
        """
        return soc_change_percent / 100 * self.params['capacity']