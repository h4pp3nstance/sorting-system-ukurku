"""
Unit Tests for Computer Vision Module
Tests untuk cv/dimension_detector.py, cv/calibrator.py, cv/preprocessor.py
"""

import pytest
import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Check if OpenCV is available
try:
    import cv2
    import numpy as np
    CV2_AVAILABLE = True
except ImportError:
    CV2_AVAILABLE = False
    np = None


class TestDimensionResult:
    """Test DimensionResult dataclass"""
    
    def test_default_values(self):
        """Test default initialization"""
        from cv.dimension_detector import DimensionResult
        
        result = DimensionResult()
        
        assert result.length_cm == 0.0
        assert result.width_cm == 0.0
        assert result.height_cm == 0.0
        assert result.confidence == 0.0
        assert result.success == False
    
    def test_volume_calculation(self):
        """Test volume calculation"""
        from cv.dimension_detector import DimensionResult
        
        result = DimensionResult(
            length_cm=10.0,
            width_cm=5.0,
            height_cm=2.0,
            success=True
        )
        
        assert result.volume_cm3 == 100.0  # 10 * 5 * 2
    
    def test_volumetric_weight_calculation(self):
        """Test volumetric weight formula"""
        from cv.dimension_detector import DimensionResult
        
        # 20 × 10 × 5 = 1000 cm³
        # Volumetric weight = (1000 / 6000) × 1000 = 166.67g
        result = DimensionResult(
            length_cm=20.0,
            width_cm=10.0,
            height_cm=5.0,
            success=True
        )
        
        expected = (1000 / 6000) * 1000  # 166.67
        assert abs(result.volumetric_weight_grams - expected) < 0.1
    
    def test_to_dict(self):
        """Test conversion to dictionary"""
        from cv.dimension_detector import DimensionResult
        
        result = DimensionResult(
            length_cm=15.0,
            width_cm=10.0,
            height_cm=8.0,
            confidence=0.95,
            success=True
        )
        
        d = result.to_dict()
        
        assert d['length_cm'] == 15.0
        assert d['width_cm'] == 10.0
        assert d['height_cm'] == 8.0
        assert d['success'] == True
        assert 'volume_cm3' in d
        assert 'volumetric_weight_g' in d


class TestCalibrator:
    """Test Calibrator class"""
    
    def test_mock_calibrator_init(self):
        """Test mock calibrator initialization"""
        from cv.calibrator import create_calibrator
        
        cal = create_calibrator("top", use_mock=True)
        
        assert cal.camera_id == "top"
        assert cal.pixels_per_cm == 50.0  # Default
    
    def test_pixels_to_cm_conversion(self):
        """Test pixel to cm conversion"""
        from cv.calibrator import create_calibrator
        
        cal = create_calibrator("top", use_mock=True)
        cal.set_pixels_per_cm(50.0)  # 50 pixels = 1 cm
        
        result = cal.pixels_to_cm(100)
        assert result == 2.0  # 100 px / 50 px/cm = 2 cm
    
    def test_cm_to_pixels_conversion(self):
        """Test cm to pixel conversion"""
        from cv.calibrator import create_calibrator
        
        cal = create_calibrator("top", use_mock=True)
        cal.set_pixels_per_cm(50.0)
        
        result = cal.cm_to_pixels(5.0)
        assert result == 250.0  # 5 cm * 50 px/cm = 250 px
    
    def test_calibrate_from_reference_mock(self):
        """Test mock calibration always succeeds"""
        from cv.calibrator import create_calibrator
        
        cal = create_calibrator("top", use_mock=True)
        
        result = cal.calibrate_from_reference(None, 10.0)
        assert result == True
    
    def test_to_dict(self):
        """Test export to dictionary"""
        from cv.calibrator import create_calibrator
        
        cal = create_calibrator("side", use_mock=True)
        cal.set_pixels_per_cm(45.0)
        
        d = cal.to_dict()
        
        assert d['camera_id'] == "side"
        assert d['pixels_per_cm'] == 45.0


class TestImagePreprocessor:
    """Test ImagePreprocessor class"""
    
    def test_mock_preprocessor_init(self):
        """Test mock preprocessor initialization"""
        from cv.preprocessor import create_preprocessor
        
        prep = create_preprocessor(use_mock=True)
        
        # Mock should not raise
        result = prep.preprocess(None)
        assert result is None
    
    @pytest.mark.skipif(not CV2_AVAILABLE, reason="OpenCV not available")
    def test_to_grayscale(self):
        """Test grayscale conversion"""
        from cv.preprocessor import ImagePreprocessor
        
        prep = ImagePreprocessor()
        
        # Create color image
        color_img = np.zeros((100, 100, 3), dtype=np.uint8)
        color_img[:, :, 0] = 255  # Blue channel
        
        gray = prep.to_grayscale(color_img)
        
        assert len(gray.shape) == 2  # Should be 2D
        assert gray.shape == (100, 100)
    
    @pytest.mark.skipif(not CV2_AVAILABLE, reason="OpenCV not available")
    def test_apply_blur(self):
        """Test Gaussian blur"""
        from cv.preprocessor import ImagePreprocessor
        
        prep = ImagePreprocessor()
        
        # Create noisy image
        img = np.random.randint(0, 255, (100, 100), dtype=np.uint8)
        
        blurred = prep.apply_blur(img)
        
        # Blurred image should have less variance
        assert blurred.std() < img.std()
    
    @pytest.mark.skipif(not CV2_AVAILABLE, reason="OpenCV not available")
    def test_detect_edges(self):
        """Test Canny edge detection"""
        from cv.preprocessor import ImagePreprocessor
        
        prep = ImagePreprocessor()
        
        # Create image with sharp edge
        img = np.zeros((100, 100), dtype=np.uint8)
        img[:, 50:] = 255  # Right half white
        
        edges = prep.detect_edges(img)
        
        # Should detect vertical edge around x=50
        assert edges[:, 48:52].sum() > 0


class TestDimensionDetector:
    """Test DimensionDetector class"""
    
    def test_mock_detector_init(self):
        """Test mock detector initialization"""
        from cv.dimension_detector import create_dimension_detector
        
        detector = create_dimension_detector(use_mock=True)
        
        assert detector._use_mock == True
    
    def test_mock_detect_from_top(self):
        """Test mock top camera detection"""
        from cv.dimension_detector import create_dimension_detector
        
        detector = create_dimension_detector(use_mock=True)
        
        result = detector.detect_from_top(None)
        
        assert result.success == True
        assert result.length_cm > 0
        assert result.width_cm > 0
        assert result.length_cm >= result.width_cm  # Length >= width
        assert result.confidence > 0
    
    def test_mock_detect_from_side(self):
        """Test mock side camera detection"""
        from cv.dimension_detector import create_dimension_detector
        
        detector = create_dimension_detector(use_mock=True)
        
        result = detector.detect_from_side(None)
        
        assert result.success == True
        assert result.height_cm > 0
        assert result.confidence > 0
    
    def test_mock_detect_dimensions_combined(self):
        """Test combined detection from both cameras"""
        from cv.dimension_detector import create_dimension_detector
        
        detector = create_dimension_detector(use_mock=True)
        
        result = detector.detect_dimensions(None, None)
        
        assert result.success == True
        assert result.length_cm > 0
        assert result.width_cm > 0
        assert result.height_cm > 0
        assert result.volume_cm3 > 0
    
    def test_dimension_bounds(self):
        """Test that mock dimensions are within reasonable bounds"""
        from cv.dimension_detector import create_dimension_detector
        
        detector = create_dimension_detector(use_mock=True)
        
        # Run multiple times to check bounds
        for _ in range(10):
            result = detector.detect_dimensions(None, None)
            
            # Dimensions should be reasonable for packages
            assert 5 <= result.length_cm <= 30
            assert 5 <= result.width_cm <= 25
            assert 3 <= result.height_cm <= 25
    
    @pytest.mark.skipif(not CV2_AVAILABLE, reason="OpenCV not available")
    def test_real_detector_with_synthetic_image(self):
        """Test real detector with synthetic test image"""
        from cv.dimension_detector import DimensionDetector
        from cv.calibrator import Calibrator
        
        # Create synthetic image with box
        img = np.zeros((480, 640, 3), dtype=np.uint8)
        img[:] = (240, 240, 240)  # Light gray background
        
        # Draw a brown box (200x150 pixels)
        cv2.rectangle(img, (200, 150), (400, 300), (50, 100, 150), -1)
        
        detector = DimensionDetector()
        detector.calibrator_top.set_pixels_per_cm(20.0)  # 20px = 1cm
        
        result = detector.detect_from_top(img)
        
        # Box is 200x150 pixels = 10x7.5 cm at 20px/cm
        # Allow some tolerance
        if result.success:
            assert 8 <= result.length_cm <= 12
            assert 6 <= result.width_cm <= 9


class TestPreprocessConfig:
    """Test PreprocessConfig dataclass"""
    
    def test_default_config(self):
        """Test default configuration values"""
        from cv.preprocessor import PreprocessConfig
        
        config = PreprocessConfig()
        
        assert config.blur_kernel == 5
        assert config.canny_low == 50
        assert config.canny_high == 150
        assert config.morph_kernel_size == 3
    
    def test_custom_config(self):
        """Test custom configuration"""
        from cv.preprocessor import PreprocessConfig
        
        config = PreprocessConfig(
            blur_kernel=7,
            canny_low=30,
            canny_high=100
        )
        
        assert config.blur_kernel == 7
        assert config.canny_low == 30
        assert config.canny_high == 100


class TestCalibrationData:
    """Test CalibrationData dataclass"""
    
    def test_default_calibration(self):
        """Test default calibration values"""
        from cv.calibrator import CalibrationData
        
        data = CalibrationData()
        
        assert data.pixels_per_cm_top == 50.0
        assert data.pixels_per_cm_side == 50.0
        assert data.camera_height_top == 30.0


class TestIntegration:
    """Integration tests for CV pipeline"""
    
    def test_full_mock_pipeline(self):
        """Test complete detection pipeline with mock"""
        from cv import DimensionDetector, create_dimension_detector
        
        detector = create_dimension_detector(use_mock=True)
        
        # Simulate capturing from both cameras
        result = detector.detect_dimensions(
            image_top=None,
            image_side=None
        )
        
        # Verify complete result
        assert result.success
        assert result.length_cm > 0
        assert result.width_cm > 0
        assert result.height_cm > 0
        
        # Verify volumetric calculation
        expected_volume = result.length_cm * result.width_cm * result.height_cm
        assert abs(result.volume_cm3 - expected_volume) < 0.01
    
    def test_result_to_measurement_integration(self):
        """Test CV result integration with measurement module"""
        from cv import create_dimension_detector
        from core.measurement import calculate_volumetric_weight
        
        detector = create_dimension_detector(use_mock=True)
        
        # Get dimensions from CV
        cv_result = detector.detect_dimensions(None, None)
        
        # Calculate volumetric weight using measurement module
        vol_weight = calculate_volumetric_weight(
            cv_result.length_cm,
            cv_result.width_cm,
            cv_result.height_cm
        )
        
        # Should match CV result's calculation (within rounding tolerance)
        assert abs(vol_weight - cv_result.volumetric_weight_grams) < 1.0


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
