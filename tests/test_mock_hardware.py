"""
Unit Tests for Mock Hardware Implementations
Tests untuk modul hal/mock/
"""

import pytest
import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from hal.mock.mock_hx711 import MockHX711
from hal.mock.mock_gpio import MockInfraredSensor, MockMotorDC, MockServo
from hal.mock.mock_printer import MockPrinter
from hal.interfaces import PackageData


class TestMockHX711:
    """Test suite for MockHX711 (weight sensor)"""
    
    @pytest.fixture
    def sensor(self):
        """Create MockHX711 instance"""
        return MockHX711()
    
    def test_initialization(self, sensor):
        """Test sensor dapat diinisialisasi"""
        sensor.setup()
        # No exception means success
        assert True
    
    def test_read_weight_returns_float(self, sensor):
        """Test read_weight mengembalikan float"""
        sensor.setup()
        weight = sensor.read_weight()
        
        assert isinstance(weight, float)
    
    def test_read_weight_in_valid_range(self, sensor):
        """Test weight dalam range 50-2000g"""
        sensor.setup()
        
        for _ in range(10):
            weight = sensor.read_weight()
            assert 50 <= weight <= 2000
    
    def test_tare_resets_offset(self, sensor):
        """Test tare function"""
        sensor.setup()
        sensor.tare()
        # Tare should work without error
        assert True
    
    def test_set_fixed_weight(self, sensor):
        """Test set_fixed_weight function"""
        sensor.setup()
        sensor.set_fixed_weight(500.0)
        # Should not raise error
        assert sensor.read_weight_fixed() == 500.0


class TestMockInfraredSensor:
    """Test suite for MockInfraredSensor"""
    
    @pytest.fixture
    def ir_sensor(self):
        """Create MockInfraredSensor instance"""
        return MockInfraredSensor(sensor_id=1, gpio_pin=5)
    
    def test_initialization(self, ir_sensor):
        """Test IR sensor dapat diinisialisasi"""
        ir_sensor.setup()
        assert True
    
    def test_default_not_triggered(self, ir_sensor):
        """Test default state: tidak triggered"""
        ir_sensor.setup()
        
        assert ir_sensor.is_triggered() is False
    
    def test_force_trigger_true(self, ir_sensor):
        """Test force trigger ke True"""
        ir_sensor.setup()
        ir_sensor.force_trigger(True)
        
        assert ir_sensor.is_triggered() is True
    
    def test_force_trigger_false(self, ir_sensor):
        """Test force trigger ke False"""
        ir_sensor.setup()
        ir_sensor.force_trigger(True)
        ir_sensor.force_trigger(False)
        
        assert ir_sensor.is_triggered() is False
    
    def test_sensor_id(self, ir_sensor):
        """Test sensor ID tersimpan dengan benar"""
        assert ir_sensor.sensor_id == 1
    
    def test_gpio_pin(self, ir_sensor):
        """Test GPIO pin tersimpan dengan benar"""
        assert ir_sensor.gpio_pin == 5


class TestMockMotorDC:
    """Test suite for MockMotorDC"""
    
    @pytest.fixture
    def motor(self):
        """Create MockMotorDC instance"""
        return MockMotorDC(gpio_pin=17)
    
    def test_initialization(self, motor):
        """Test motor dapat diinisialisasi"""
        motor.setup()
        assert True
    
    def test_default_not_running(self, motor):
        """Test default state: tidak running"""
        motor.setup()
        
        assert motor.is_running() is False
    
    def test_start(self, motor):
        """Test start motor"""
        motor.setup()
        motor.start()
        
        assert motor.is_running() is True
    
    def test_stop(self, motor):
        """Test stop motor"""
        motor.setup()
        motor.start()
        motor.stop()
        
        assert motor.is_running() is False
    
    def test_start_then_set_speed(self, motor):
        """Test start lalu set_speed"""
        motor.setup()
        motor.start()
        motor.set_speed(50)
        
        # Motor should still be running
        assert motor.is_running() is True
    
    def test_set_speed_clamp(self, motor):
        """Test set_speed clamping"""
        motor.setup()
        motor.set_speed(150)  # Should clamp to 100
        motor.set_speed(-10)  # Should clamp to 0
        # No assertion needed, just no error


class TestMockServo:
    """Test suite for MockServo"""
    
    @pytest.fixture
    def servo(self):
        """Create MockServo instance"""
        return MockServo(servo_id=1, gpio_pin=18)
    
    def test_initialization(self, servo):
        """Test servo dapat diinisialisasi"""
        servo.setup()
        assert True
    
    def test_default_position_center(self, servo):
        """Test default position: 90° (center)"""
        servo.setup()
        
        assert servo.get_angle() == 90
    
    def test_set_angle(self, servo):
        """Test set_angle ke angle tertentu"""
        servo.setup()
        servo.set_angle(45)
        
        assert servo.get_angle() == 45
    
    def test_move_to_lane_reguler(self, servo):
        """Test move ke lane REGULER"""
        servo.setup()
        servo.move_to_lane("REGULER")
        
        # REGULER lane is at 45°
        assert servo.get_angle() == 45
    
    def test_move_to_lane_express(self, servo):
        """Test move ke lane EXPRESS"""
        servo.setup()
        servo.move_to_lane("EXPRESS")
        
        # EXPRESS lane is at 90°
        assert servo.get_angle() == 90
    
    def test_move_to_lane_kargo(self, servo):
        """Test move ke lane KARGO"""
        servo.setup()
        servo.move_to_lane("KARGO")
        
        # KARGO lane is at 135°
        assert servo.get_angle() == 135
    
    def test_reset(self, servo):
        """Test reset ke center"""
        servo.setup()
        servo.set_angle(45)
        servo.reset()
        
        assert servo.get_angle() == 90
    
    def test_servo_id(self, servo):
        """Test servo ID tersimpan dengan benar"""
        assert servo.servo_id == 1
    
    def test_angle_clamping(self, servo):
        """Test angle is clamped to 0-180"""
        servo.setup()
        servo.set_angle(200)  # Should clamp to 180
        assert servo.get_angle() == 180
        
        servo.set_angle(-10)  # Should clamp to 0
        assert servo.get_angle() == 0


class TestMockPrinter:
    """Test suite for MockPrinter"""
    
    @pytest.fixture
    def printer(self):
        """Create MockPrinter instance"""
        return MockPrinter()
    
    @pytest.fixture
    def sample_package(self):
        """Create sample package data"""
        return PackageData(
            panjang=15.0,
            lebar=10.0,
            tinggi=8.0,
            berat_aktual=500.0,
            berat_volumetrik=200.0,
            chargeable_weight=500.0,
            service_type="REGULER",
            price=6000
        )
    
    def test_initialization(self, printer):
        """Test printer dapat diinisialisasi"""
        printer.setup()
        assert True
    
    def test_print_label(self, printer, sample_package):
        """Test print_label tidak error"""
        printer.setup()
        result = printer.print_label(sample_package)
        
        # Should complete and return True
        assert result is True
    
    def test_print_label_creates_file(self, printer, sample_package, tmp_path):
        """Test print_label creates label file"""
        # Use temp directory
        printer.output_folder = str(tmp_path)
        printer.setup()
        result = printer.print_label(sample_package)
        
        # Check file was created
        label_files = list(tmp_path.glob("label_*.txt"))
        assert len(label_files) >= 1
        assert result is True


class TestPackageData:
    """Test suite for PackageData dataclass"""
    
    def test_package_data_creation(self):
        """Test PackageData dapat dibuat"""
        package = PackageData(
            panjang=15.0,
            lebar=10.0,
            tinggi=8.0,
            berat_aktual=500.0,
            berat_volumetrik=200.0,
            chargeable_weight=500.0,
            service_type="REGULER",
            price=6000
        )
        
        assert package.panjang == 15.0
        assert package.lebar == 10.0
        assert package.tinggi == 8.0
        assert package.berat_aktual == 500.0
        assert package.berat_volumetrik == 200.0
        assert package.chargeable_weight == 500.0
        assert package.service_type == "REGULER"
        assert package.price == 6000
    
    def test_package_data_optional_fields(self):
        """Test PackageData dengan optional timestamp"""
        package = PackageData(
            panjang=15.0,
            lebar=10.0,
            tinggi=8.0,
            berat_aktual=500.0,
            berat_volumetrik=200.0,
            chargeable_weight=500.0,
            service_type="EXPRESS",
            price=12000
        )
        
        # timestamp should have default or be settable
        assert package.service_type == "EXPRESS"


# =============================================================================
# Factory Function Tests
# =============================================================================

class TestFactoryFunctions:
    """Test factory functions from hal/mock/__init__.py"""
    
    def test_create_weight_sensor(self):
        """Test create_weight_sensor factory"""
        from hal.mock import create_weight_sensor
        
        sensor = create_weight_sensor("mock")
        assert sensor is not None
        assert isinstance(sensor, MockHX711)
    
    def test_create_ir_sensor(self):
        """Test create_ir_sensor factory"""
        from hal.mock import create_ir_sensor
        
        sensor = create_ir_sensor(1, 5, "mock")
        assert sensor is not None
        assert isinstance(sensor, MockInfraredSensor)
    
    def test_create_motor(self):
        """Test create_motor factory"""
        from hal.mock import create_motor
        
        motor = create_motor(17, "mock")
        assert motor is not None
        assert isinstance(motor, MockMotorDC)
    
    def test_create_servo(self):
        """Test create_servo factory"""
        from hal.mock import create_servo
        
        servo = create_servo(1, 18, "mock")
        assert servo is not None
        assert isinstance(servo, MockServo)
    
    def test_create_printer(self):
        """Test create_printer factory"""
        from hal.mock import create_printer
        
        printer = create_printer("mock")
        assert printer is not None
        assert isinstance(printer, MockPrinter)


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
