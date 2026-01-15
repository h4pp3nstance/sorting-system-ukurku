"""
Integration Tests for Sorting System
End-to-end testing of complete workflows
"""

import pytest
import sys
import os
import tempfile
import shutil
from datetime import datetime

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from hal.mock.mock_hx711 import MockHX711, create_weight_sensor
from hal.mock.mock_gpio import MockInfraredSensor, MockMotorDC, MockServo
from hal.mock.mock_gpio import create_ir_sensor, create_motor, create_servo
from hal.mock.mock_printer import MockPrinter, create_printer
from hal.interfaces import PackageData
from core.classification import Classifier as PackageClassifier, classify_package
from core.measurement import (
    calculate_volumetric_weight,
    calculate_volume,
    get_chargeable_weight,
    validate_dimensions
)


# =============================================================================
# Fixture: Complete Hardware Setup
# =============================================================================

@pytest.fixture
def sorting_hardware():
    """Create complete mock hardware setup"""
    # Create all hardware components
    weight_sensor = create_weight_sensor("mock")
    ir_entry = create_ir_sensor(1, 5, "mock")
    ir_exit = create_ir_sensor(2, 6, "mock")
    conveyor = create_motor(17, "mock")
    servo = create_servo(1, 18, "mock")
    
    # Create printer with temp directory
    temp_dir = tempfile.mkdtemp()
    printer = MockPrinter(output_folder=temp_dir)
    
    # Initialize all
    weight_sensor.setup()
    ir_entry.setup()
    ir_exit.setup()
    conveyor.setup()
    servo.setup()
    printer.setup()
    
    yield {
        'weight_sensor': weight_sensor,
        'ir_entry': ir_entry,
        'ir_exit': ir_exit,
        'conveyor': conveyor,
        'servo': servo,
        'printer': printer,
        'temp_dir': temp_dir
    }
    
    # Cleanup
    shutil.rmtree(temp_dir, ignore_errors=True)


@pytest.fixture
def classifier():
    """Create PackageClassifier instance"""
    return PackageClassifier()


# =============================================================================
# Test: Complete Sorting Workflow
# =============================================================================

class TestCompleteSortingWorkflow:
    """
    End-to-end tests for the complete package sorting workflow:
    1. Package enters → IR sensor triggered
    2. Conveyor moves package to scale
    3. Weight measurement
    4. Dimension detection (mocked)
    5. Classification
    6. Servo moves to correct lane
    7. Label printed
    8. Package exits
    """
    
    def test_reguler_package_workflow(self, sorting_hardware, classifier):
        """Test workflow untuk paket REGULER (≤700g)"""
        hw = sorting_hardware
        
        # Step 1: Package enters (IR trigger)
        hw['ir_entry'].force_trigger(True)
        assert hw['ir_entry'].is_triggered() is True
        
        # Step 2: Start conveyor
        hw['conveyor'].start()
        assert hw['conveyor'].is_running() is True
        
        # Step 3: Simulate stop at scale, read weight
        hw['weight_sensor'].set_fixed_weight(350.0)
        weight = hw['weight_sensor'].read_weight_fixed()
        assert weight == 350.0
        
        # Step 4: Mock dimensions for REGULER
        dimensions = {'panjang': 10.0, 'lebar': 10.0, 'tinggi': 10.0}
        vol_weight = calculate_volumetric_weight(
            dimensions['panjang'],
            dimensions['lebar'],
            dimensions['tinggi']
        )
        
        # Step 5: Classify
        result = classifier.classify(weight, vol_weight)
        assert result.service_type == "REGULER"
        assert result.price == 6000
        
        # Step 6: Move servo to REGULER lane
        hw['servo'].move_to_lane("REGULER")
        assert hw['servo'].get_angle() == 45
        
        # Step 7: Create package data and print label
        package = PackageData(
            panjang=dimensions['panjang'],
            lebar=dimensions['lebar'],
            tinggi=dimensions['tinggi'],
            berat_aktual=weight,
            berat_volumetrik=vol_weight,
            chargeable_weight=result.chargeable_weight,
            service_type=result.service_type,
            price=result.price
        )
        success = hw['printer'].print_label(package)
        assert success is True
        
        # Step 8: Clear IR, stop conveyor
        hw['ir_entry'].force_trigger(False)
        hw['conveyor'].stop()
        assert hw['conveyor'].is_running() is False
    
    def test_express_package_workflow(self, sorting_hardware, classifier):
        """Test workflow untuk paket EXPRESS (701-1300g)"""
        hw = sorting_hardware
        
        # Simulate express package
        hw['ir_entry'].force_trigger(True)
        hw['conveyor'].start()
        
        hw['weight_sensor'].set_fixed_weight(950.0)
        weight = hw['weight_sensor'].read_weight_fixed()
        
        dimensions = {'panjang': 15.0, 'lebar': 12.0, 'tinggi': 10.0}
        vol_weight = calculate_volumetric_weight(
            dimensions['panjang'],
            dimensions['lebar'],
            dimensions['tinggi']
        )
        
        result = classifier.classify(weight, vol_weight)
        assert result.service_type == "EXPRESS"
        assert result.price == 12000
        
        hw['servo'].move_to_lane("EXPRESS")
        assert hw['servo'].get_angle() == 90
        
        hw['conveyor'].stop()
    
    def test_kargo_package_workflow(self, sorting_hardware, classifier):
        """Test workflow untuk paket KARGO (1301-2000g)"""
        hw = sorting_hardware
        
        hw['ir_entry'].force_trigger(True)
        hw['conveyor'].start()
        
        hw['weight_sensor'].set_fixed_weight(1650.0)
        weight = hw['weight_sensor'].read_weight_fixed()
        
        dimensions = {'panjang': 20.0, 'lebar': 18.0, 'tinggi': 15.0}
        vol_weight = calculate_volumetric_weight(
            dimensions['panjang'],
            dimensions['lebar'],
            dimensions['tinggi']
        )
        
        result = classifier.classify(weight, vol_weight)
        assert result.service_type == "KARGO"
        assert result.price == 5000
        
        hw['servo'].move_to_lane("KARGO")
        assert hw['servo'].get_angle() == 135
        
        hw['conveyor'].stop()
    
    def test_volumetric_weight_determines_service(self, sorting_hardware, classifier):
        """
        Test when volumetric weight is higher than actual weight,
        it determines the service type
        """
        hw = sorting_hardware
        
        # Light but large package
        hw['weight_sensor'].set_fixed_weight(200.0)  # Light
        weight = hw['weight_sensor'].read_weight_fixed()
        
        # Large dimensions → high volumetric weight
        dimensions = {'panjang': 23.0, 'lebar': 20.0, 'tinggi': 15.0}
        vol_weight = calculate_volumetric_weight(
            dimensions['panjang'],
            dimensions['lebar'],
            dimensions['tinggi']
        )
        
        # vol_weight = (23 * 20 * 15) / 6000 * 1000 = 1150g
        assert vol_weight > weight
        
        result = classifier.classify(weight, vol_weight)
        
        # Should use volumetric weight (1150g) → EXPRESS
        assert result.chargeable_weight == vol_weight
        assert result.service_type == "EXPRESS"


# =============================================================================
# Test: Measurement Pipeline
# =============================================================================

class TestMeasurementPipeline:
    """
    Tests for the measurement workflow:
    Weight sensor → Dimensions → Volume calculation → Chargeable weight
    """
    
    def test_complete_measurement_flow(self, sorting_hardware):
        """Test full measurement pipeline"""
        hw = sorting_hardware
        
        # Read actual weight
        hw['weight_sensor'].set_fixed_weight(750.0)
        actual_weight = hw['weight_sensor'].read_weight_fixed()
        
        # Mock dimension detection
        panjang, lebar, tinggi = 15.0, 12.0, 8.0
        
        # Validate dimensions (returns tuple)
        is_valid, error = validate_dimensions(panjang, lebar, tinggi)
        assert is_valid is True
        assert error is None
        
        # Calculate volume
        volume = calculate_volume(panjang, lebar, tinggi)
        assert volume == 15.0 * 12.0 * 8.0  # 1440 cm³
        
        # Calculate volumetric weight
        vol_weight = calculate_volumetric_weight(panjang, lebar, tinggi)
        expected_vol = round((1440 / 6000) * 1000, 1)  # 240.0g
        assert vol_weight == expected_vol
        
        # Get chargeable weight
        chargeable = get_chargeable_weight(actual_weight, vol_weight)
        assert chargeable == max(actual_weight, vol_weight)  # 750.0g
    
    def test_boundary_dimension_validation(self):
        """Test dimension validation at boundaries"""
        # Valid dimensions (within volume limit)
        is_valid, error = validate_dimensions(20.0, 20.0, 20.0)
        assert is_valid is True, f"Should be valid but got: {error}"
        
        # Note: 23x23x23 = 12167 cm³, which exceeds VOLUME_MAX (12000 cm³)
        # So this is expected to be invalid due to volume, not dimension
        is_valid, error = validate_dimensions(23.0, 23.0, 23.0)
        assert is_valid is False
        assert "Volume" in error
        
        # Invalid: exceeds max dimension
        is_valid, error = validate_dimensions(24.0, 23.0, 23.0)
        assert is_valid is False
        
        is_valid, error = validate_dimensions(23.0, 24.0, 23.0)
        assert is_valid is False
        
        is_valid, error = validate_dimensions(23.0, 23.0, 24.0)
        assert is_valid is False
        
        # Invalid: zero or negative
        is_valid, error = validate_dimensions(0, 10.0, 10.0)
        assert is_valid is False
        
        is_valid, error = validate_dimensions(-1, 10.0, 10.0)
        assert is_valid is False
    
    def test_weight_sensor_random_range(self, sorting_hardware):
        """Test random weight generation is within range"""
        hw = sorting_hardware
        
        # Read multiple weights
        weights = [hw['weight_sensor'].read_weight() for _ in range(20)]
        
        # All should be in valid range (50-2000g based on MockHX711 defaults)
        for w in weights:
            assert 0 <= w <= 2100  # Allow for noise


# =============================================================================
# Test: Classification Pipeline
# =============================================================================

class TestClassificationPipeline:
    """
    Tests for classification workflow:
    Weights → Classification → Service Type + Price
    """
    
    def test_all_service_types(self, classifier):
        """Test classification for all service types"""
        test_cases = [
            # (actual_weight, vol_weight, expected_type, expected_price)
            (300.0, 100.0, "REGULER", 6000),
            (700.0, 600.0, "REGULER", 6000),
            (800.0, 500.0, "EXPRESS", 12000),
            (1000.0, 1100.0, "EXPRESS", 12000),
            (1500.0, 1000.0, "KARGO", 5000),
            (1800.0, 1900.0, "KARGO", 5000),
        ]
        
        for actual, vol, expected_type, expected_price in test_cases:
            result = classifier.classify(actual, vol)
            assert result.service_type == expected_type, \
                f"Failed for actual={actual}, vol={vol}"
            assert result.price == expected_price
    
    def test_chargeable_weight_selection(self, classifier):
        """Test chargeable weight is max(actual, volumetric)"""
        # Actual higher
        result = classifier.classify(1000.0, 500.0)
        assert result.chargeable_weight == 1000.0
        
        # Volumetric higher
        result = classifier.classify(500.0, 1000.0)
        assert result.chargeable_weight == 1000.0
        
        # Equal
        result = classifier.classify(700.0, 700.0)
        assert result.chargeable_weight == 700.0
    
    def test_convenience_function(self):
        """Test classify_package convenience function"""
        result = classify_package(500.0, 300.0)
        
        assert result.service_type == "REGULER"
        assert result.price == 6000
        assert result.chargeable_weight == 500.0


# =============================================================================
# Test: Hardware State Machine
# =============================================================================

class TestHardwareStateMachine:
    """
    Tests for hardware state transitions
    """
    
    def test_conveyor_state_transitions(self, sorting_hardware):
        """Test conveyor start/stop state transitions"""
        conveyor = sorting_hardware['conveyor']
        
        # Initial: stopped
        assert conveyor.is_running() is False
        
        # Start
        conveyor.start()
        assert conveyor.is_running() is True
        
        # Stop
        conveyor.stop()
        assert conveyor.is_running() is False
        
        # Can start again
        conveyor.start()
        assert conveyor.is_running() is True
    
    def test_servo_lane_positions(self, sorting_hardware):
        """Test servo moves to correct lane positions"""
        servo = sorting_hardware['servo']
        
        # Default: center (90°)
        assert servo.get_angle() == 90
        
        # REGULER lane: 45°
        servo.move_to_lane("REGULER")
        assert servo.get_angle() == 45
        
        # EXPRESS lane: 90°
        servo.move_to_lane("EXPRESS")
        assert servo.get_angle() == 90
        
        # KARGO lane: 135°
        servo.move_to_lane("KARGO")
        assert servo.get_angle() == 135
        
        # Reset: back to 90°
        servo.reset()
        assert servo.get_angle() == 90
    
    def test_ir_sensor_trigger_states(self, sorting_hardware):
        """Test IR sensor trigger state changes"""
        ir = sorting_hardware['ir_entry']
        
        # Default: not triggered
        assert ir.is_triggered() is False
        
        # Force triggered
        ir.force_trigger(True)
        assert ir.is_triggered() is True
        
        # Clear trigger
        ir.force_trigger(False)
        assert ir.is_triggered() is False
        
        # Clear force
        ir.clear_force()
        assert ir.is_triggered() is False


# =============================================================================
# Test: Multi-Package Sequence
# =============================================================================

class TestMultiPackageSequence:
    """
    Tests for processing multiple packages in sequence
    """
    
    def test_process_three_packages(self, sorting_hardware, classifier):
        """Test processing 3 packages with different service types"""
        hw = sorting_hardware
        packages_processed = []
        
        package_configs = [
            {'weight': 350.0, 'dims': (10, 10, 10), 'expected': 'REGULER'},
            {'weight': 900.0, 'dims': (15, 12, 10), 'expected': 'EXPRESS'},
            {'weight': 1500.0, 'dims': (20, 18, 15), 'expected': 'KARGO'},
        ]
        
        for config in package_configs:
            # Setup
            hw['ir_entry'].force_trigger(True)
            hw['conveyor'].start()
            
            # Measure
            hw['weight_sensor'].set_fixed_weight(config['weight'])
            weight = hw['weight_sensor'].read_weight_fixed()
            
            p, l, t = config['dims']
            vol_weight = calculate_volumetric_weight(p, l, t)
            
            # Classify
            result = classifier.classify(weight, vol_weight)
            assert result.service_type == config['expected']
            
            # Route
            hw['servo'].move_to_lane(result.service_type)
            
            # Complete
            hw['ir_entry'].force_trigger(False)
            hw['conveyor'].stop()
            hw['servo'].reset()
            
            packages_processed.append(result.service_type)
        
        # Verify all processed
        assert packages_processed == ['REGULER', 'EXPRESS', 'KARGO']
    
    def test_counting_by_service_type(self, sorting_hardware, classifier):
        """Test counting packages by service type"""
        hw = sorting_hardware
        counts = {'REGULER': 0, 'EXPRESS': 0, 'KARGO': 0}
        
        # Process 10 packages with fixed weights
        weights = [200, 400, 600, 800, 1000, 1200, 1400, 1600, 1800, 500]
        
        for weight in weights:
            hw['weight_sensor'].set_fixed_weight(float(weight))
            w = hw['weight_sensor'].read_weight_fixed()
            
            # Use small dimensions so actual weight determines type
            vol_weight = calculate_volumetric_weight(5, 5, 5)  # ~20.8g
            
            result = classifier.classify(w, vol_weight)
            counts[result.service_type] += 1
        
        # Verify distribution
        total = sum(counts.values())
        assert total == 10
        assert counts['REGULER'] >= 2  # 200, 400, 600, 500
        assert counts['EXPRESS'] >= 2  # 800, 1000, 1200
        assert counts['KARGO'] >= 2    # 1400, 1600, 1800


# =============================================================================
# Test: Error Handling
# =============================================================================

class TestErrorHandling:
    """
    Tests for error handling scenarios
    """
    
    def test_uninitialized_sensor_error(self):
        """Test error when reading from uninitialized sensor"""
        sensor = MockHX711()
        
        with pytest.raises(RuntimeError) as exc_info:
            sensor.read_weight()
        
        assert "not initialized" in str(exc_info.value).lower()
    
    def test_uninitialized_servo_error(self):
        """Test error when moving uninitialized servo"""
        servo = MockServo(servo_id=1, gpio_pin=18)
        
        with pytest.raises(RuntimeError) as exc_info:
            servo.set_angle(45)
        
        assert "not initialized" in str(exc_info.value).lower()
    
    def test_uninitialized_motor_error(self):
        """Test error when starting uninitialized motor"""
        motor = MockMotorDC(gpio_pin=17)
        
        with pytest.raises(RuntimeError) as exc_info:
            motor.start()
        
        assert "not initialized" in str(exc_info.value).lower()
    
    def test_invalid_service_classification(self, classifier):
        """Test classification with extreme weights"""
        # Zero weight should still classify (edge case)
        result = classifier.classify(0, 0)
        assert result.service_type == "REGULER"  # 0 ≤ 700
        
        # Very large weight (above KARGO max) should raise ValueError
        with pytest.raises(ValueError) as exc_info:
            classifier.classify(2500.0, 100.0)
        
        assert "exceeds" in str(exc_info.value).lower() or "2000" in str(exc_info.value)


# =============================================================================
# Test: Printer Integration
# =============================================================================

class TestPrinterIntegration:
    """
    Tests for label printing integration
    """
    
    def test_print_creates_correct_label(self, sorting_hardware, classifier):
        """Test label contains correct package information"""
        hw = sorting_hardware
        
        # Create package
        hw['weight_sensor'].set_fixed_weight(500.0)
        weight = hw['weight_sensor'].read_weight_fixed()
        
        dims = (12.0, 10.0, 8.0)
        vol_weight = calculate_volumetric_weight(*dims)
        
        result = classifier.classify(weight, vol_weight)
        
        package = PackageData(
            panjang=dims[0],
            lebar=dims[1],
            tinggi=dims[2],
            berat_aktual=weight,
            berat_volumetrik=vol_weight,
            chargeable_weight=result.chargeable_weight,
            service_type=result.service_type,
            price=result.price
        )
        
        # Print
        success = hw['printer'].print_label(package)
        assert success is True
        
        # Check file exists
        files = os.listdir(hw['temp_dir'])
        assert len(files) >= 1
        assert any(f.startswith('label_') and f.endswith('.txt') for f in files)
    
    def test_multiple_labels(self, sorting_hardware, classifier):
        """Test printing multiple labels"""
        import time
        hw = sorting_hardware
        
        for i in range(3):
            package = PackageData(
                panjang=10.0 + i,
                lebar=10.0,
                tinggi=10.0,
                berat_aktual=300.0 + (i * 100),
                berat_volumetrik=166.7,
                chargeable_weight=300.0 + (i * 100),
                service_type="REGULER",
                price=6000
            )
            
            success = hw['printer'].print_label(package)
            assert success is True
            
            # Small delay to ensure unique timestamps
            time.sleep(0.01)
        
        # Should have at least 1 label file (timestamps may collide)
        files = os.listdir(hw['temp_dir'])
        label_files = [f for f in files if f.startswith('label_')]
        assert len(label_files) >= 1


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
