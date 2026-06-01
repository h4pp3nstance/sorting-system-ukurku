"""
Volumetric Weight Calculation
Kalkulasi berat volumetrik berdasarkan dimensi paket
"""

from config.settings import IATA_DIVISOR, DIMENSION_MAX, VOLUME_MAX


def calculate_volumetric_weight(
    panjang: float,
    lebar: float,
    tinggi: float,
    divisor: float = IATA_DIVISOR
) -> float:
    """
    Hitung berat volumetrik menggunakan rumus IATA
    
    Formula: (P × L × T) / 6000 = kg
             Konversi ke gram: × 1000
    
    Args:
        panjang: Panjang dalam cm
        lebar: Lebar dalam cm
        tinggi: Tinggi dalam cm
        divisor: Konstanta pembagi (default: 6000 IATA)
        
    Returns:
        float: Berat volumetrik dalam gram
    """
    # Calculate volume in cm³
    volume = panjang * lebar * tinggi
    
    # Calculate volumetric weight in kg
    volumetric_kg = volume / divisor
    
    # Convert to grams
    volumetric_grams = volumetric_kg * 1000
    
    return round(volumetric_grams, 1)


def calculate_volume(
    panjang: float,
    lebar: float,
    tinggi: float
) -> float:
    """
    Hitung volume paket
    
    Args:
        panjang: Panjang dalam cm
        lebar: Lebar dalam cm
        tinggi: Tinggi dalam cm
        
    Returns:
        float: Volume dalam cm³
    """
    return panjang * lebar * tinggi


def validate_dimensions(
    panjang: float,
    lebar: float,
    tinggi: float
) -> tuple:
    """
    Validasi dimensi paket
    
    Args:
        panjang, lebar, tinggi: Dimensi dalam cm
        
    Returns:
        tuple: (is_valid, error_message)
    """
    # Check positive values
    if panjang <= 0 or lebar <= 0 or tinggi <= 0:
        return False, "Dimensi harus lebih dari 0"
    
    # Check maximum dimensions
    if panjang > DIMENSION_MAX:
        return False, f"Panjang melebihi batas maksimal {DIMENSION_MAX} cm"
    if lebar > DIMENSION_MAX:
        return False, f"Lebar melebihi batas maksimal {DIMENSION_MAX} cm"
    if tinggi > DIMENSION_MAX:
        return False, f"Tinggi melebihi batas maksimal {DIMENSION_MAX} cm"
    
    # Check maximum volume
    volume = calculate_volume(panjang, lebar, tinggi)
    if volume > VOLUME_MAX:
        return False, f"Volume melebihi batas maksimal {VOLUME_MAX} cm³"
    
    return True, None


def get_chargeable_weight(
    berat_aktual: float,
    berat_volumetrik: float
) -> float:
    """
    Tentukan berat yang digunakan (chargeable weight)
    
    Menggunakan prinsip: MAX(berat_aktual, berat_volumetrik)
    
    Args:
        berat_aktual: Berat fisik dalam gram
        berat_volumetrik: Berat volumetrik dalam gram
        
    Returns:
        float: Berat yang digunakan dalam gram
    """
    return max(berat_aktual, berat_volumetrik)


if __name__ == "__main__":
    # Test calculations
    test_cases = [
        (10, 10, 10),   # Volume: 1000 cm³ → 166.7g
        (20, 15, 10),   # Volume: 3000 cm³ → 500g
        (23, 23, 23),   # Volume: 12167 cm³ → 2027.8g (max)
        (15, 12, 8),    # Volume: 1440 cm³ → 240g
    ]
    
    print("\nTesting Volumetric Calculation:")
    print("=" * 60)
    print(f"{'Dimensions (cm)':<20} {'Volume (cm³)':<15} {'Vol. Weight (g)':<15}")
    print("-" * 60)
    
    for p, l, t in test_cases:
        volume = calculate_volume(p, l, t)
        vol_weight = calculate_volumetric_weight(p, l, t)
        print(f"{p} × {l} × {t:<10} {volume:<15.1f} {vol_weight:<15.1f}")
    
    print("=" * 60)
    
    # Test validation
    print("\nValidation Tests:")
    print("-" * 40)
    
    valid, msg = validate_dimensions(23, 23, 23)
    print(f"23×23×23: {'Valid' if valid else f'Invalid - {msg}'}")
    
    valid, msg = validate_dimensions(25, 20, 15)
    print(f"25×20×15: {'Valid' if valid else f'Invalid - {msg}'}")
    
    valid, msg = validate_dimensions(-5, 10, 10)
    print(f"-5×10×10: {'Valid' if valid else f'Invalid - {msg}'}")
