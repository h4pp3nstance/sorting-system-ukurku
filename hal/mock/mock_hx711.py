"""
Mock Weight Sensor (Load Cell + HX711)
Simulator untuk testing tanpa hardware
"""

import random
import time
from typing import Optional
from hal.interfaces import IWeightSensor


class MockHX711(IWeightSensor):
    """
    Mock implementation of Load Cell + HX711 sensor
    Generates random weight values for testing
    """
    
    def __init__(
        self,
        min_weight: float = 50.0,
        max_weight: float = 2000.0,
        noise: float = 5.0
    ):
        """
        Args:
            min_weight: Minimum weight to generate (gram)
            max_weight: Maximum weight to generate (gram)
            noise: Random noise to add (gram)
        """
        self.min_weight = min_weight
        self.max_weight = max_weight
        self.noise = noise
        self.tare_offset = 0.0
        self.current_weight: Optional[float] = None
        self._initialized = False
    
    def setup(self) -> None:
        """Inisialisasi mock sensor"""
        print("[MockHX711] Initializing mock weight sensor...")
        time.sleep(0.5)  # Simulate startup delay
        self._initialized = True
        print("[MockHX711] Mock weight sensor ready!")
    
    def read_weight(self) -> float:
        """
        Generate random weight value
        Returns:
            float: Simulated weight in grams
        """
        if not self._initialized:
            raise RuntimeError("Sensor not initialized. Call setup() first.")
        
        # Generate base weight
        base_weight = random.uniform(self.min_weight, self.max_weight)
        
        # Add noise
        noise = random.uniform(-self.noise, self.noise)
        
        # Apply tare offset
        weight = base_weight + noise - self.tare_offset
        
        # Ensure non-negative
        weight = max(0.0, weight)
        
        # Round to 1 decimal
        self.current_weight = round(weight, 1)
        
        print(f"[MockHX711] Weight reading: {self.current_weight}g")
        return self.current_weight
    
    def tare(self) -> None:
        """Set current weight as zero point"""
        if self.current_weight is not None:
            self.tare_offset = self.current_weight
            print(f"[MockHX711] Tare set to {self.tare_offset}g")
        else:
            self.tare_offset = 0.0
            print("[MockHX711] Tare reset to 0g")
    
    def set_fixed_weight(self, weight: float) -> None:
        """
        Set a fixed weight for deterministic testing
        Args:
            weight: Fixed weight value in grams
        """
        self._fixed_weight = weight
        print(f"[MockHX711] Fixed weight set to {weight}g")
    
    def read_weight_fixed(self) -> float:
        """Read fixed weight (for deterministic tests)"""
        if hasattr(self, '_fixed_weight'):
            return self._fixed_weight
        return self.read_weight()


# Factory function
def create_weight_sensor(mode: str = "mock") -> IWeightSensor:
    """
    Factory untuk membuat weight sensor
    Args:
        mode: "mock" atau "real"
    Returns:
        IWeightSensor implementation
    """
    if mode == "mock":
        return MockHX711()
    else:
        # TODO: Import dan return RealHX711
        raise NotImplementedError("Real HX711 not implemented yet")
