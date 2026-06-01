"""
Config Package Exports
"""

from .settings import (
    HardwareMode,
    HARDWARE_MODE,
    is_mock_mode,
    print_config,
    # Classification
    WEIGHT_MIN,
    WEIGHT_MAX,
    WEIGHT_REGULER_MAX,
    WEIGHT_EXPRESS_MAX,
    WEIGHT_KARGO_MAX,
    # Pricing
    PRICE_REGULER,
    PRICE_EXPRESS,
    PRICE_KARGO,
    # Dimensions
    DIMENSION_MAX,
    VOLUME_MAX,
    IATA_DIVISOR,
    # GPIO
    GPIO_RELAY,
    GPIO_SERVO_1,
    GPIO_SERVO_2,
    GPIO_SERVO_3,
    GPIO_IR_1,
    GPIO_IR_2,
    GPIO_IR_3,
    GPIO_IR_4,
    GPIO_HX711_DT,
    GPIO_HX711_SCK,
    # Servo angles
    SERVO_ANGLE_REGULER,
    SERVO_ANGLE_EXPRESS,
    SERVO_ANGLE_KARGO,
    SERVO_ANGLE_RESET,
    # Web
    WEB_HOST,
    WEB_PORT,
    WEB_DEBUG,
    # Paths
    BASE_DIR,
    ASSETS_DIR,
    TEST_IMAGES_DIR,
    OUTPUT_DIR,
    LABELS_DIR,
)

__all__ = [
    'HardwareMode',
    'HARDWARE_MODE',
    'is_mock_mode',
    'print_config',
]
