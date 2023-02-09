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

        self.params['max_soc'] = 100              # max soc we can charge to in %
        self.params['min_soc'] = 0                # min soc we can discharge to in %
        self.params['current_soc'] = 50           # current soc

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

