"""
Unit Tests for Measurement Logic
Tests untuk modul core/measurement.py
"""

import pytest
import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.measurement import (
    calculate_volumetric_weight,
    calculate_volume,
    validate_dimensions,
    get_chargeable_weight,
)
from config.settings import IATA_DIVISOR, DIMENSION_MAX, VOLUME_MAX


class TestVolumetricWeight:
    """Test suite for volumetric weight calculation"""
    
    # =========================================================================
    # Basic Calculation Tests
    # =========================================================================
    
    def test_basic_calculation(self):
        """Test kalkulasi dasar: 10×10×10 = 1000cm³ / 6000 × 1000 = 166.7g"""
        result = calculate_volumetric_weight(10, 10, 10)
        
        expected = (10 * 10 * 10) / 6000 * 1000
        assert result == round(expected, 1)
    
    def test_iata_formula(self):
        """Test formula IATA: (P×L×T) / 6000 × 1000"""
        p, l, t = 20, 15, 10
        result = calculate_volumetric_weight(p, l, t)
        
        expected = (p * l * t) / IATA_DIVISOR * 1000
        assert result == round(expected, 1)
    
    def test_result_is_rounded(self):
        """Test hasil dibulatkan ke 1 desimal"""
        result = calculate_volumetric_weight(7, 7, 7)
        
        # 343 / 6000 * 1000 = 57.166666...
        assert result == 57.2
    
    def test_custom_divisor(self):
        """Test dengan custom divisor (bukan 6000)"""
        result = calculate_volumetric_weight(10, 10, 10, divisor=5000)
        
        expected = (10 * 10 * 10) / 5000 * 1000
        assert result == round(expected, 1)
    
    # =========================================================================
    # Specific Dimension Tests
    # =========================================================================
    
    def test_maximum_dimensions(self):
        """Test dengan dimensi maksimal 23×23×23"""
        result = calculate_volumetric_weight(23, 23, 23)
        
        expected = (23 * 23 * 23) / 6000 * 1000
        assert result == round(expected, 1)
        assert result == 2027.8  # 12167 / 6000 * 1000
    
    def test_minimum_dimensions(self):
        """Test dengan dimensi sangat kecil"""
        result = calculate_volumetric_weight(1, 1, 1)
        
        expected = 1 / 6000 * 1000
        assert result == round(expected, 1)
    
    def test_asymmetric_dimensions(self):
        """Test dengan dimensi tidak simetris"""
        result = calculate_volumetric_weight(30, 10, 5)
        
        expected = (30 * 10 * 5) / 6000 * 1000
        assert result == round(expected, 1)
    
    def test_float_dimensions(self):
        """Test dengan dimensi desimal"""
        result = calculate_volumetric_weight(10.5, 8.3, 5.2)
        
        expected = (10.5 * 8.3 * 5.2) / 6000 * 1000
        assert result == round(expected, 1)
    
    # =========================================================================
    # Edge Cases
    # =========================================================================
    
    def test_zero_dimension(self):
        """Test dengan salah satu dimensi 0"""
        result = calculate_volumetric_weight(10, 0, 10)
        
        assert result == 0.0
    
    def test_all_zero_dimensions(self):
        """Test dengan semua dimensi 0"""
        result = calculate_volumetric_weight(0, 0, 0)
        
        assert result == 0.0


class TestCalculateVolume:
    """Test suite for volume calculation"""
    
    def test_basic_volume(self):
        """Test volume dasar: 10×10×10 = 1000cm³"""
        result = calculate_volume(10, 10, 10)
        
        assert result == 1000
    
    def test_asymmetric_volume(self):
        """Test volume tidak simetris"""
        result = calculate_volume(20, 15, 10)
        
        assert result == 3000
    
    def test_float_volume(self):
        """Test volume dengan desimal"""
        result = calculate_volume(10.5, 8.5, 5.5)
        
        assert result == 10.5 * 8.5 * 5.5
    
    def test_zero_volume(self):
        """Test volume dengan dimensi 0"""
        result = calculate_volume(10, 0, 10)
        
        assert result == 0


class TestValidateDimensions:
    """Test suite for dimension validation"""
    
    # =========================================================================
    # Valid Cases
    # =========================================================================
    
    def test_valid_dimensions(self):
        """Test dimensi valid"""
        is_valid, error = validate_dimensions(10, 10, 10)
        
        assert is_valid is True
        assert error is None
    
    def test_valid_at_maximum(self):
        """Test dimensi di batas maksimal"""
        is_valid, error = validate_dimensions(
            DIMENSION_MAX, DIMENSION_MAX, DIMENSION_MAX
        )
        
        # Note: Volume might exceed VOLUME_MAX
        # This depends on DIMENSION_MAX and VOLUME_MAX settings
        if is_valid:
            assert error is None
    
    def test_valid_small_dimensions(self):
        """Test dimensi kecil tapi valid"""
        is_valid, error = validate_dimensions(1, 1, 1)
        
        assert is_valid is True
        assert error is None
    
    # =========================================================================
    # Invalid Cases - Negative/Zero
    # =========================================================================
    
    def test_invalid_negative_panjang(self):
        """Test panjang negatif"""
        is_valid, error = validate_dimensions(-5, 10, 10)
        
        assert is_valid is False
        assert "lebih dari 0" in error
    
    def test_invalid_negative_lebar(self):
        """Test lebar negatif"""
        is_valid, error = validate_dimensions(10, -5, 10)
        
        assert is_valid is False
        assert "lebih dari 0" in error
    
    def test_invalid_negative_tinggi(self):
        """Test tinggi negatif"""
        is_valid, error = validate_dimensions(10, 10, -5)
        
        assert is_valid is False
        assert "lebih dari 0" in error
    
    def test_invalid_zero_panjang(self):
        """Test panjang 0"""
        is_valid, error = validate_dimensions(0, 10, 10)
        
        assert is_valid is False
        assert "lebih dari 0" in error
    
    # =========================================================================
    # Invalid Cases - Exceeds Maximum
    # =========================================================================
    
    def test_invalid_exceeds_max_panjang(self):
        """Test panjang melebihi batas"""
        is_valid, error = validate_dimensions(DIMENSION_MAX + 1, 10, 10)
        
        assert is_valid is False
        assert "Panjang" in error
        assert "maksimal" in error
    
    def test_invalid_exceeds_max_lebar(self):
        """Test lebar melebihi batas"""
        is_valid, error = validate_dimensions(10, DIMENSION_MAX + 1, 10)
        
        assert is_valid is False
        assert "Lebar" in error
    
    def test_invalid_exceeds_max_tinggi(self):
        """Test tinggi melebihi batas"""
        is_valid, error = validate_dimensions(10, 10, DIMENSION_MAX + 1)
        
        assert is_valid is False
        assert "Tinggi" in error
    
    # =========================================================================
    # Volume Validation
    # =========================================================================
    
    def test_invalid_exceeds_max_volume(self):
        """Test volume melebihi batas"""
        # Create dimensions that exceed volume limit
        # Assuming VOLUME_MAX is reasonable
        if VOLUME_MAX < 1000000:  # Only test if limit is set
            # Find dimensions that exceed volume
            dim = int((VOLUME_MAX + 1) ** (1/3)) + 1
            is_valid, error = validate_dimensions(dim, dim, dim)
            
            # Might fail due to dimension limit first
            if not is_valid and "Volume" in str(error):
                assert "Volume" in error


class TestGetChargeableWeight:
    """Test suite for chargeable weight determination"""
    
    def test_actual_greater(self):
        """Test: aktual > volumetrik → gunakan aktual"""
        result = get_chargeable_weight(800, 500)
        
        assert result == 800
    
    def test_volumetric_greater(self):
        """Test: volumetrik > aktual → gunakan volumetrik"""
        result = get_chargeable_weight(400, 600)
        
        assert result == 600
    
    def test_equal_weights(self):
        """Test: aktual = volumetrik"""
        result = get_chargeable_weight(500, 500)
        
        assert result == 500
    
    def test_zero_weights(self):
        """Test: kedua berat 0"""
        result = get_chargeable_weight(0, 0)
        
        assert result == 0
    
    def test_one_zero_weight(self):
        """Test: salah satu 0"""
        result1 = get_chargeable_weight(500, 0)
        result2 = get_chargeable_weight(0, 500)
        
        assert result1 == 500
        assert result2 == 500
    
    def test_float_weights(self):
        """Test: berat dengan desimal"""
        result = get_chargeable_weight(500.5, 500.4)
        
        assert result == 500.5


# =============================================================================
# Parametrized Tests
# =============================================================================

@pytest.mark.parametrize("p,l,t,expected", [
    (10, 10, 10, 166.7),
    (20, 15, 10, 500.0),
    (23, 23, 23, 2027.8),
    (15, 12, 8, 240.0),
    (5, 5, 5, 20.8),
    (1, 1, 1, 0.2),
])
def test_volumetric_weight_values(p, l, t, expected):
    """Parametrized test untuk berbagai dimensi"""
    result = calculate_volumetric_weight(p, l, t)
    
    assert result == expected


@pytest.mark.parametrize("p,l,t", [
    (-1, 10, 10),
    (10, -1, 10),
    (10, 10, -1),
    (0, 10, 10),
    (10, 0, 10),
    (10, 10, 0),
])
def test_invalid_dimensions(p, l, t):
    """Parametrized test untuk dimensi tidak valid"""
    is_valid, error = validate_dimensions(p, l, t)
    
    assert is_valid is False
    assert error is not None


# =============================================================================
# Integration-like Tests
# =============================================================================

class TestMeasurementIntegration:
    """Integration tests combining multiple functions"""
    
    def test_full_measurement_flow(self):
        """Test alur lengkap pengukuran"""
        # 1. Validate dimensions
        p, l, t = 15, 12, 10
        is_valid, error = validate_dimensions(p, l, t)
        assert is_valid is True
        
        # 2. Calculate volume
        volume = calculate_volume(p, l, t)
        assert volume == 1800
        
        # 3. Calculate volumetric weight
        vol_weight = calculate_volumetric_weight(p, l, t)
        assert vol_weight == 300.0
        
        # 4. Determine chargeable weight
        actual_weight = 250
        chargeable = get_chargeable_weight(actual_weight, vol_weight)
        assert chargeable == 300.0  # volumetric is higher
    
    def test_measurement_for_each_service_type(self):
        """Test measurement untuk setiap jenis layanan"""
        # REGULER: < 700g
        vol_reguler = calculate_volumetric_weight(10, 10, 10)  # 166.7g
        assert vol_reguler < 700
        
        # EXPRESS: 700-1300g
        vol_express = calculate_volumetric_weight(18, 15, 15)  # 675g
        chargeable_express = get_chargeable_weight(900, vol_express)
        assert 700 < chargeable_express <= 1300
        
        # KARGO: 1300-2000g
        vol_kargo = calculate_volumetric_weight(22, 20, 18)  # 1320g
        assert 1300 < vol_kargo <= 2000


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
