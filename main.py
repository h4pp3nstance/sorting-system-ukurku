"""
Main Entry Point
Sorting System - Package Measurement and Automatic Sorting
"""

import sys
import time
from datetime import datetime

# Configuration
from config.settings import (
    HARDWARE_MODE,
    is_mock_mode,
    print_config,
    GPIO_RELAY,
    GPIO_SERVO_1,
    GPIO_SERVO_2,
    GPIO_SERVO_3,
    GPIO_IR_1,
    GPIO_IR_2,
    GPIO_IR_3,
    GPIO_IR_4,
)

# HAL
from hal.interfaces import PackageData

# Mock implementations
from hal.mock import (
    create_weight_sensor,
    create_camera,
    create_ir_sensor,
    create_motor,
    create_servo,
    create_printer,
)

# Core logic
from core import (
    calculate_volumetric_weight,
    classify_package,
)

# Computer Vision
from cv import create_dimension_detector


class SortingSystem:
    """
    Main Sorting System Controller
    """
    
    def __init__(self):
        """Initialize the sorting system"""
        self.mode = HARDWARE_MODE
        
        # Initialize components
        self._init_sensors()
        self._init_actuators()
        self._init_output()
        
        # Initialize CV module
        use_mock_cv = self.mode == "mock"
        self.dimension_detector = create_dimension_detector(use_mock=use_mock_cv)
        print(f"[System] CV Module initialized (mock={use_mock_cv})")
    
    def _init_sensors(self):
        """Initialize all sensors"""
        print("\n[System] Initializing sensors...")
        
        # Weight sensor
        self.weight_sensor = create_weight_sensor(self.mode)
        self.weight_sensor.setup()
        
        # Cameras
        self.camera_top = create_camera("top", self.mode)
        self.camera_side = create_camera("side", self.mode)
        self.camera_top.setup()
        self.camera_side.setup()
        
        # IR sensors
        self.ir_sensors = [
            create_ir_sensor(1, GPIO_IR_1, self.mode),
            create_ir_sensor(2, GPIO_IR_2, self.mode),
            create_ir_sensor(3, GPIO_IR_3, self.mode),
            create_ir_sensor(4, GPIO_IR_4, self.mode),
        ]
        for sensor in self.ir_sensors:
            sensor.setup()
    
    def _init_actuators(self):
        """Initialize all actuators"""
        print("\n[System] Initializing actuators...")
        
        # Conveyor motor
        self.motor = create_motor(GPIO_RELAY, self.mode)
        self.motor.setup()
        
        # Sorting servos
        self.servos = {
            'REGULER': create_servo(1, GPIO_SERVO_1, self.mode),
            'EXPRESS': create_servo(2, GPIO_SERVO_2, self.mode),
            'KARGO': create_servo(3, GPIO_SERVO_3, self.mode),
        }
        for servo in self.servos.values():
            servo.setup()
    
    def _init_output(self):
        """Initialize output devices"""
        print("\n[System] Initializing output devices...")
        
        # Printer
        self.printer = create_printer(self.mode)
        self.printer.setup()
    
    def wait_for_package(self) -> bool:
        """
        Wait for package detection
        Returns:
            bool: True if package detected
        """
        print("\n[System] Waiting for package...")
        
        # In mock mode, simulate detection after keypress or auto
        if is_mock_mode():
            # Force trigger for demo
            self.ir_sensors[0].force_trigger(True)
            time.sleep(0.5)
            return self.ir_sensors[0].is_triggered()
        
        # Real mode: poll IR sensor
        return self.ir_sensors[0].is_triggered()
    
    def measure_weight(self) -> float:
        """
        Measure package weight
        Returns:
            float: Weight in grams
        """
        print("\n[System] Measuring weight...")
        return self.weight_sensor.read_weight()
    
    def measure_dimensions(self) -> tuple:
        """
        Measure package dimensions using cameras and CV
        Returns:
            tuple: (panjang, lebar, tinggi) in cm
        """
        print("\n[System] Measuring dimensions with CV...")
        
        # Capture images from cameras
        img_top = self.camera_top.capture()
        img_side = self.camera_side.capture()
        
        # Use CV module to detect dimensions
        result = self.dimension_detector.detect_dimensions(img_top, img_side)
        
        if result.success:
            panjang = result.length_cm
            lebar = result.width_cm
            tinggi = result.height_cm
            confidence = result.confidence
            print(f"[System] CV Detection: {panjang} × {lebar} × {tinggi} cm (confidence: {confidence:.2f})")
        else:
            # Fallback to random values if CV fails
            import random
            panjang = round(random.uniform(5, 23), 1)
            lebar = round(random.uniform(5, 23), 1)
            tinggi = round(random.uniform(5, 23), 1)
            print(f"[System] CV failed ({result.error_message}), using fallback: {panjang} × {lebar} × {tinggi} cm")
        
        return panjang, lebar, tinggi
    
    def process_package(self) -> PackageData:
        """
        Full package processing pipeline
        Returns:
            PackageData: Complete package information
        """
        # 1. Measure weight
        berat_aktual = self.measure_weight()
        
        # 2. Start conveyor
        self.motor.start()
        time.sleep(0.5)  # Simulate movement
        
        # 3. Measure dimensions
        panjang, lebar, tinggi = self.measure_dimensions()
        
        # 4. Calculate volumetric weight
        berat_volumetrik = calculate_volumetric_weight(panjang, lebar, tinggi)
        print(f"[System] Volumetric weight: {berat_volumetrik}g")
        
        # 5. Classify
        result = classify_package(berat_aktual, berat_volumetrik)
        print(f"[System] Classification: {result.service_type} "
              f"(Rp {result.price:,})")
        
        # 6. Create package data
        package = PackageData(
            panjang=panjang,
            lebar=lebar,
            tinggi=tinggi,
            berat_aktual=berat_aktual,
            berat_volumetrik=berat_volumetrik,
            chargeable_weight=result.chargeable_weight,
            service_type=result.service_type,
            price=result.price,
        )
        
        return package
    
    def sort_package(self, service_type: str):
        """
        Activate sorting mechanism
        Args:
            service_type: REGULER, EXPRESS, or KARGO
        """
        print(f"\n[System] Sorting to {service_type} lane...")
        
        # Move appropriate servo
        if service_type in self.servos:
            self.servos[service_type].move_to_lane(service_type)
            time.sleep(0.5)
            self.servos[service_type].reset()
        
        # Stop conveyor
        self.motor.stop()
    
    def print_label(self, package: PackageData):
        """Print package label"""
        print("\n[System] Printing label...")
        self.printer.print_label(package)
    
    def run_single_cycle(self):
        """Run one complete sorting cycle"""
        print("\n" + "=" * 60)
        print("STARTING NEW SORTING CYCLE")
        print("=" * 60)
        
        # Wait for package
        if not self.wait_for_package():
            print("[System] No package detected, skipping...")
            return None
        
        # Process package
        package = self.process_package()
        
        # Sort
        self.sort_package(package.service_type)
        
        # Print label
        self.print_label(package)
        
        print("\n[System] Cycle complete!")
        print("=" * 60)
        
        return package
    
    def run(self, cycles: int = 1):
        """
        Run the sorting system
        Args:
            cycles: Number of cycles to run (0 for infinite)
        """
        print_config()
        
        print("\n" + "=" * 60)
        print("  SORTING SYSTEM STARTED")
        print(f"  Mode: {self.mode.upper()}")
        print("=" * 60)
        
        count = 0
        while cycles == 0 or count < cycles:
            try:
                self.run_single_cycle()
                count += 1
                
                if cycles > 0 and count < cycles:
                    print("\n[System] Next cycle in 2 seconds...")
                    time.sleep(2)
                    
            except KeyboardInterrupt:
                print("\n[System] Interrupted by user")
                break
            except Exception as e:
                print(f"\n[System] Error: {e}")
                break
        
        print("\n[System] Shutting down...")
        self.camera_top.release()
        self.camera_side.release()
        print("[System] Goodbye!")


def main():
    """Main entry point"""
    # Create and run system
    system = SortingSystem()
    
    # Run 3 demo cycles
    system.run(cycles=3)


if __name__ == "__main__":
    main()
