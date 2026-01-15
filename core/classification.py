"""
Classification Logic
Klasifikasi jenis layanan pengiriman berdasarkan berat
"""

from dataclasses import dataclass
from typing import Tuple
from config.settings import (
    WEIGHT_REGULER_MAX,
    WEIGHT_EXPRESS_MAX,
    WEIGHT_KARGO_MAX,
    PRICE_REGULER,
    PRICE_EXPRESS,
    PRICE_KARGO,
)


@dataclass
class ClassificationResult:
    """Hasil klasifikasi"""
    service_type: str  # REGULER, EXPRESS, KARGO
    price: int         # Harga dalam Rupiah
    chargeable_weight: float  # Berat yang digunakan (gram)


class Classifier:
    """
    Classifier untuk menentukan jenis layanan pengiriman
    """
    
    # Service types
    REGULER = "REGULER"
    EXPRESS = "EXPRESS"
    KARGO = "KARGO"
    
    def __init__(self):
        """Initialize classifier dengan threshold default"""
        self.thresholds = {
            self.REGULER: WEIGHT_REGULER_MAX,
            self.EXPRESS: WEIGHT_EXPRESS_MAX,
            self.KARGO: WEIGHT_KARGO_MAX,
        }
        self.prices = {
            self.REGULER: PRICE_REGULER,
            self.EXPRESS: PRICE_EXPRESS,
            self.KARGO: PRICE_KARGO,
        }
    
    def classify(
        self,
        berat_aktual: float,
        berat_volumetrik: float
    ) -> ClassificationResult:
        """
        Klasifikasi paket berdasarkan berat
        
        Args:
            berat_aktual: Berat aktual dalam gram
            berat_volumetrik: Berat volumetrik dalam gram
            
        Returns:
            ClassificationResult: Hasil klasifikasi
        """
        # Determine chargeable weight (max of actual vs volumetric)
        chargeable_weight = max(berat_aktual, berat_volumetrik)
        
        # Classify based on weight
        if chargeable_weight <= self.thresholds[self.REGULER]:
            service_type = self.REGULER
        elif chargeable_weight <= self.thresholds[self.EXPRESS]:
            service_type = self.EXPRESS
        elif chargeable_weight <= self.thresholds[self.KARGO]:
            service_type = self.KARGO
        else:
            raise ValueError(
                f"Weight {chargeable_weight}g exceeds maximum "
                f"{self.thresholds[self.KARGO]}g"
            )
        
        return ClassificationResult(
            service_type=service_type,
            price=self.prices[service_type],
            chargeable_weight=chargeable_weight
        )
    
    def get_service_color(self, service_type: str) -> str:
        """Get color code for service type (for UI)"""
        colors = {
            self.REGULER: "#28a745",  # Green
            self.EXPRESS: "#ffc107",  # Yellow
            self.KARGO: "#dc3545",    # Red
        }
        return colors.get(service_type, "#6c757d")


# Singleton instance
_classifier = None


def get_classifier() -> Classifier:
    """Get singleton classifier instance"""
    global _classifier
    if _classifier is None:
        _classifier = Classifier()
    return _classifier


def classify_package(
    berat_aktual: float,
    berat_volumetrik: float
) -> ClassificationResult:
    """
    Convenience function untuk klasifikasi
    
    Args:
        berat_aktual: Berat aktual (gram)
        berat_volumetrik: Berat volumetrik (gram)
        
    Returns:
        ClassificationResult
    """
    return get_classifier().classify(berat_aktual, berat_volumetrik)


if __name__ == "__main__":
    # Test classification
    test_cases = [
        (300, 200),   # Should be REGULER
        (500, 800),   # Should be EXPRESS (volumetrik > aktual)
        (1500, 1000), # Should be KARGO
        (600, 600),   # Should be REGULER
        (1000, 1200), # Should be EXPRESS
    ]
    
    print("\nTesting Classification Logic:")
    print("=" * 50)
    
    for aktual, vol in test_cases:
        result = classify_package(aktual, vol)
        print(f"Aktual: {aktual}g, Vol: {vol}g → "
              f"{result.service_type} (Rp {result.price:,})")
    
    print("=" * 50)
