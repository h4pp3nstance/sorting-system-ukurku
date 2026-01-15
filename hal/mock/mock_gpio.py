"""
Mock GPIO Components
Simulators untuk IR Sensor, Motor DC, dan Servo
"""

import time
import random
from typing import Callable, Optional
from hal.interfaces import IInfraredSensor, IMotor, IServo


class MockInfraredSensor(IInfraredSensor):
    """
    Mock implementation of Infrared Sensor
    Can be triggered manually or randomly for testing
    """
    
    def __init__(self, sensor_id: int, gpio_pin: int):
        """
        Args:
            sensor_id: Sensor number (1-4)
            gpio_pin: GPIO pin number (for reference)
        """
        self.sensor_id = sensor_id
        self.gpio_pin = gpio_pin
        self._initialized = False
        self._forced_state: Optional[bool] = None
        self._trigger_probability = 0.0
    
    def setup(self) -> None:
        """Initialize mock sensor"""
        print(f"[MockIR-{self.sensor_id}] Initializing on GPIO {self.gpio_pin}...")
        self._initialized = True
        print(f"[MockIR-{self.sensor_id}] Ready!")
    
    def is_triggered(self) -> bool:
        """
        Check if sensor is triggered
        Returns:
            bool: True if object detected
        """
        if not self._initialized:
            raise RuntimeError("Sensor not initialized. Call setup() first.")
        
        # Return forced state if set
        if self._forced_state is not None:
            state = self._forced_state
            print(f"[MockIR-{self.sensor_id}] State (forced): {state}")
            return state
        
        # Random trigger based on probability
        if self._trigger_probability > 0:
            state = random.random() < self._trigger_probability
            print(f"[MockIR-{self.sensor_id}] State (random): {state}")
            return state
        
        # Default: not triggered
        return False
    
    def force_trigger(self, state: bool) -> None:
        """Force sensor to return specific state"""
        self._forced_state = state
        print(f"[MockIR-{self.sensor_id}] Forced to: {state}")
    
    def clear_force(self) -> None:
        """Clear forced state"""
        self._forced_state = None
        print(f"[MockIR-{self.sensor_id}] Force cleared")
    
    def set_trigger_probability(self, prob: float) -> None:
        """Set random trigger probability (0.0 to 1.0)"""
        self._trigger_probability = max(0.0, min(1.0, prob))


class MockMotorDC(IMotor):
    """
    Mock implementation of DC Motor (Conveyor)
    Logs motor state changes
    """
    
    def __init__(self, gpio_pin: int = 17):
        """
        Args:
            gpio_pin: GPIO pin for relay control
        """
        self.gpio_pin = gpio_pin
        self._initialized = False
        self._running = False
        self._speed = 100  # Percentage
    
    def setup(self) -> None:
        """Initialize mock motor"""
        print(f"[MockMotorDC] Initializing on GPIO {self.gpio_pin} (via Relay)...")
        self._initialized = True
        print("[MockMotorDC] Ready!")
    
    def start(self) -> None:
        """Start motor"""
        if not self._initialized:
            raise RuntimeError("Motor not initialized. Call setup() first.")
        
        self._running = True
        print(f"[MockMotorDC] ▶ STARTED at {self._speed}% speed")
    
    def stop(self) -> None:
        """Stop motor"""
        self._running = False
        print("[MockMotorDC] ⏹ STOPPED")
    
    def is_running(self) -> bool:
        """Check if motor is running"""
        return self._running
    
    def set_speed(self, speed: int) -> None:
        """Set motor speed (for future PWM implementation)"""
        self._speed = max(0, min(100, speed))
        print(f"[MockMotorDC] Speed set to {self._speed}%")


class MockServo(IServo):
    """
    Mock implementation of Servo Motor
    Logs position changes
    """
    
    # Predefined angles for sorting
    ANGLES = {
        'REGULER': 45,
        'EXPRESS': 90,
        'KARGO': 135,
        'RESET': 90
    }
    
    def __init__(self, servo_id: int, gpio_pin: int):
        """
        Args:
            servo_id: Servo number (1-3)
            gpio_pin: GPIO PWM pin
        """
        self.servo_id = servo_id
        self.gpio_pin = gpio_pin
        self._initialized = False
        self._current_angle = 90  # Default center position
    
    def setup(self) -> None:
        """Initialize mock servo"""
        print(f"[MockServo-{self.servo_id}] Initializing on GPIO {self.gpio_pin} (PWM)...")
        self._initialized = True
        print(f"[MockServo-{self.servo_id}] Ready at {self._current_angle}°")
    
    def set_angle(self, angle: int) -> None:
        """
        Set servo position
        Args:
            angle: Target angle (0-180)
        """
        if not self._initialized:
            raise RuntimeError("Servo not initialized. Call setup() first.")
        
        # Clamp angle
        angle = max(0, min(180, angle))
        
        old_angle = self._current_angle
        self._current_angle = angle
        
        # Simulate movement time
        movement = abs(angle - old_angle)
        delay = movement * 0.005  # ~5ms per degree
        time.sleep(delay)
        
        print(f"[MockServo-{self.servo_id}] ↻ Moved: {old_angle}° → {angle}°")
    
    def reset(self) -> None:
        """Reset to center position"""
        self.set_angle(self.ANGLES['RESET'])
        print(f"[MockServo-{self.servo_id}] ⟲ Reset to center")
    
    def get_angle(self) -> int:
        """Get current angle"""
        return self._current_angle
    
    def move_to_lane(self, lane: str) -> None:
        """
        Move to specific sorting lane
        Args:
            lane: "REGULER", "EXPRESS", atau "KARGO"
        """
        if lane.upper() in self.ANGLES:
            self.set_angle(self.ANGLES[lane.upper()])
        else:
            print(f"[MockServo-{self.servo_id}] Unknown lane: {lane}")


# Factory functions
def create_ir_sensor(sensor_id: int, gpio_pin: int, mode: str = "mock") -> IInfraredSensor:
    """Factory untuk IR sensor"""
    if mode == "mock":
        return MockInfraredSensor(sensor_id, gpio_pin)
    else:
        raise NotImplementedError("Real IR sensor not implemented yet")


def create_motor(gpio_pin: int = 17, mode: str = "mock") -> IMotor:
    """Factory untuk motor DC"""
    if mode == "mock":
        return MockMotorDC(gpio_pin)
    else:
        raise NotImplementedError("Real motor not implemented yet")


def create_servo(servo_id: int, gpio_pin: int, mode: str = "mock") -> IServo:
    """Factory untuk servo"""
    if mode == "mock":
        return MockServo(servo_id, gpio_pin)
    else:
        raise NotImplementedError("Real servo not implemented yet")
