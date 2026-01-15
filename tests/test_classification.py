"""
Unit Tests for Classification Logic
Tests untuk modul core/classification.py
"""

import pytest
import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.classification import (
    Classifier,
    ClassificationResult,
    classify_package,
    get_classifier,
)
from config.settings import (
    WEIGHT_REGULER_MAX,
    WEIGHT_EXPRESS_MAX,
    WEIGHT_KARGO_MAX,
    PRICE_REGULER,
    PRICE_EXPRESS,
    PRICE_KARGO,
)


class TestClassifier:
    """Test suite for Classifier class"""
    
    @pytest.fixture
    def classifier(self):
        """Create a fresh Classifier instance"""
        return Classifier()
    
    # =========================================================================
    # REGULER Classification Tests
    # =========================================================================
    
    def test_reguler_minimum_weight(self, classifier):
        """Test REGULER dengan berat minimum"""
        result = classifier.classify(berat_aktual=50, berat_volumetrik=50)
        
        assert result.service_type == Classifier.REGULER
        assert result.price == PRICE_REGULER
        assert result.chargeable_weight == 50
    
    def test_reguler_maximum_weight(self, classifier):
        """Test REGULER di batas maksimal (700g)"""
        result = classifier.classify(
            berat_aktual=WEIGHT_REGULER_MAX,
            berat_volumetrik=WEIGHT_REGULER_MAX
        )
        
        assert result.service_type == Classifier.REGULER
        assert result.price == PRICE_REGULER
        assert result.chargeable_weight == WEIGHT_REGULER_MAX
    
    def test_reguler_price(self, classifier):
        """Test harga REGULER = Rp 6,000"""
        result = classifier.classify(berat_aktual=500, berat_volumetrik=400)
        
        assert result.price == 6000
    
    # =========================================================================
    # EXPRESS Classification Tests
    # =========================================================================
    
    def test_express_minimum_weight(self, classifier):
        """Test EXPRESS di batas minimum (701g)"""
        result = classifier.classify(
            berat_aktual=WEIGHT_REGULER_MAX + 1,
            berat_volumetrik=0
        )
        
        assert result.service_type == Classifier.EXPRESS
        assert result.price == PRICE_EXPRESS
    
    def test_express_maximum_weight(self, classifier):
        """Test EXPRESS di batas maksimal (1300g)"""
        result = classifier.classify(
            berat_aktual=WEIGHT_EXPRESS_MAX,
            berat_volumetrik=WEIGHT_EXPRESS_MAX
        )
        
        assert result.service_type == Classifier.EXPRESS
        assert result.price == PRICE_EXPRESS
    
    def test_express_price(self, classifier):
        """Test harga EXPRESS = Rp 12,000"""
        result = classifier.classify(berat_aktual=1000, berat_volumetrik=900)
        
        assert result.price == 12000
    
    # =========================================================================
    # KARGO Classification Tests
    # =========================================================================
    
    def test_kargo_minimum_weight(self, classifier):
        """Test KARGO di batas minimum (1301g)"""
        result = classifier.classify(
            berat_aktual=WEIGHT_EXPRESS_MAX + 1,
            berat_volumetrik=0
        )
        
        assert result.service_type == Classifier.KARGO
        assert result.price == PRICE_KARGO
    
    def test_kargo_maximum_weight(self, classifier):
        """Test KARGO di batas maksimal (2000g)"""
        result = classifier.classify(
            berat_aktual=WEIGHT_KARGO_MAX,
            berat_volumetrik=WEIGHT_KARGO_MAX
        )
        
        assert result.service_type == Classifier.KARGO
        assert result.price == PRICE_KARGO
    
    def test_kargo_price(self, classifier):
        """Test harga KARGO = Rp 5,000"""
        result = classifier.classify(berat_aktual=1800, berat_volumetrik=1500)
        
        assert result.price == 5000
    
    # =========================================================================
    # Chargeable Weight Tests
    # =========================================================================
    
    def test_chargeable_weight_uses_actual_when_higher(self, classifier):
        """Test: chargeable = aktual ketika aktual > volumetrik"""
        result = classifier.classify(berat_aktual=800, berat_volumetrik=500)
        
        assert result.chargeable_weight == 800
    
    def test_chargeable_weight_uses_volumetric_when_higher(self, classifier):
        """Test: chargeable = volumetrik ketika volumetrik > aktual"""
        result = classifier.classify(berat_aktual=400, berat_volumetrik=600)
        
        assert result.chargeable_weight == 600
    
    def test_chargeable_weight_equal(self, classifier):
        """Test: chargeable ketika aktual = volumetrik"""
        result = classifier.classify(berat_aktual=500, berat_volumetrik=500)
        
        assert result.chargeable_weight == 500
    
    def test_volumetric_determines_service_type(self, classifier):
        """Test: volumetrik bisa menentukan service type berbeda dari aktual"""
        # Aktual 500g (REGULER), tapi volumetrik 800g (EXPRESS)
        result = classifier.classify(berat_aktual=500, berat_volumetrik=800)
        
        assert result.service_type == Classifier.EXPRESS
        assert result.chargeable_weight == 800
    
    # =========================================================================
    # Edge Cases & Error Handling
    # =========================================================================
    
    def test_exceeds_maximum_weight(self, classifier):
        """Test: berat melebihi maksimal 2000g harus raise error"""
        with pytest.raises(ValueError) as excinfo:
            classifier.classify(berat_aktual=2500, berat_volumetrik=0)
        
        assert "exceeds maximum" in str(excinfo.value)
    
    def test_zero_weight(self, classifier):
        """Test: berat 0g masih valid (masuk REGULER)"""
        result = classifier.classify(berat_aktual=0, berat_volumetrik=0)
        
        assert result.service_type == Classifier.REGULER
        assert result.chargeable_weight == 0
    
    def test_float_weights(self, classifier):
        """Test: berat dengan desimal"""
        result = classifier.classify(berat_aktual=699.9, berat_volumetrik=700.0)
        
        assert result.service_type == Classifier.REGULER
        assert result.chargeable_weight == 700.0
    
    def test_boundary_700_to_701(self, classifier):
        """Test boundary: 700g (REGULER) vs 700.1g (EXPRESS)"""
        result_700 = classifier.classify(berat_aktual=700, berat_volumetrik=0)
        result_701 = classifier.classify(berat_aktual=700.1, berat_volumetrik=0)
        
        assert result_700.service_type == Classifier.REGULER
        assert result_701.service_type == Classifier.EXPRESS
    
    def test_boundary_1300_to_1301(self, classifier):
        """Test boundary: 1300g (EXPRESS) vs 1300.1g (KARGO)"""
        result_1300 = classifier.classify(berat_aktual=1300, berat_volumetrik=0)
        result_1301 = classifier.classify(berat_aktual=1300.1, berat_volumetrik=0)
        
        assert result_1300.service_type == Classifier.EXPRESS
        assert result_1301.service_type == Classifier.KARGO
    
    # =========================================================================
    # Utility Methods
    # =========================================================================
    
    def test_get_service_color(self, classifier):
        """Test color codes untuk UI"""
        assert classifier.get_service_color(Classifier.REGULER) == "#28a745"
        assert classifier.get_service_color(Classifier.EXPRESS) == "#ffc107"
        assert classifier.get_service_color(Classifier.KARGO) == "#dc3545"
    
    def test_get_service_color_unknown(self, classifier):
        """Test color fallback untuk unknown service"""
        assert classifier.get_service_color("UNKNOWN") == "#6c757d"


class TestConvenienceFunctions:
    """Test convenience functions"""
    
    def test_classify_package_function(self):
        """Test classify_package() convenience function"""
        result = classify_package(berat_aktual=500, berat_volumetrik=400)
        
        assert isinstance(result, ClassificationResult)
        assert result.service_type == Classifier.REGULER
    
    def test_get_classifier_singleton(self):
        """Test get_classifier() returns singleton"""
        c1 = get_classifier()
        c2 = get_classifier()
        
        assert c1 is c2


class TestClassificationResult:
    """Test ClassificationResult dataclass"""
    
    def test_dataclass_fields(self):
        """Test ClassificationResult memiliki field yang benar"""
        result = ClassificationResult(
            service_type="REGULER",
            price=6000,
            chargeable_weight=500.5
        )
        
        assert result.service_type == "REGULER"
        assert result.price == 6000
        assert result.chargeable_weight == 500.5
    
    def test_dataclass_equality(self):
        """Test ClassificationResult equality"""
        result1 = ClassificationResult("REGULER", 6000, 500)
        result2 = ClassificationResult("REGULER", 6000, 500)
        
        assert result1 == result2


# =============================================================================
# Parametrized Tests untuk Coverage Lengkap
# =============================================================================

@pytest.mark.parametrize("aktual,volumetrik,expected_type,expected_price", [
    # REGULER cases
    (100, 100, "REGULER", 6000),
    (500, 300, "REGULER", 6000),
    (700, 700, "REGULER", 6000),
    (300, 700, "REGULER", 6000),
    
    # EXPRESS cases
    (800, 500, "EXPRESS", 12000),
    (1000, 1000, "EXPRESS", 12000),
    (1300, 1300, "EXPRESS", 12000),
    (500, 1000, "EXPRESS", 12000),
    
    # KARGO cases
    (1500, 1000, "KARGO", 5000),
    (1800, 1800, "KARGO", 5000),
    (2000, 2000, "KARGO", 5000),
    (1000, 1500, "KARGO", 5000),
])
def test_classification_matrix(aktual, volumetrik, expected_type, expected_price):
    """Parametrized test untuk berbagai kombinasi berat"""
    result = classify_package(aktual, volumetrik)
    
    assert result.service_type == expected_type
    assert result.price == expected_price
    assert result.chargeable_weight == max(aktual, volumetrik)


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
