from abc import ABC, abstractmethod
from typing import Optional
from oes.battery.battery_model import BatteryModel


class AbstractBattery(ABC):
    def __init__(self, battery_model: BatteryModel, initial_soc: Optional[float] = 0.0):
        """
        Initialises a battery instance.
        :param battery_model: a battery model specification
        :param initial_soc: for simulated batteries, this sets the initial state of charge. For real-world batteries,
        the current SOC will always be read from the physical battery (implemented by get_current_soc()).
        """
        self.model = battery_model
        self.last_soc = initial_soc

    def override_soc(self, soc: float):
        self.last_soc = soc

    @abstractmethod
    def get_current_soc(self) -> float:
        pass

    def validate_soc(self) -> bool:
        """
        Check that the current SOC is within the min and max SOC
        :return: True if the current SOC is within the min and max SOC, False otherwise.
        """
        current_soc = self.get_current_soc()
        return self.model.min_soc <= current_soc <= self.model.max_soc


class SimulatedBattery(AbstractBattery):
    def __init__(self, battery_model: BatteryModel, initial_soc: float = 50.0):
        if initial_soc is None:
            raise ValueError("Initial SOC must be set for simulated battery")
        super().__init__(battery_model, initial_soc)

    def get_current_soc(self) -> float:
        return self.last_soc
