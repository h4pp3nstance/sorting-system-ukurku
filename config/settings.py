"""
Application Configuration
"""

import os
from enum import Enum


class HardwareMode(Enum):
    """Hardware operation mode"""
    MOCK = "mock"
    REAL = "real"


# ============================================================
# HARDWARE MODE
# Set via environment variable: HARDWARE_MODE=mock or HARDWARE_MODE=real
# ============================================================
HARDWARE_MODE = os.getenv("HARDWARE_MODE", HardwareMode.MOCK.value)


# ============================================================
# CLASSIFICATION THRESHOLDS (in grams)
# ============================================================
WEIGHT_MIN = 50          # Minimum weight
WEIGHT_MAX = 2000        # Maximum weight
WEIGHT_REGULER_MAX = 700       # Reguler: <= 700g
WEIGHT_EXPRESS_MAX = 1300      # Express: 701-1300g
WEIGHT_KARGO_MAX = 2000        # Kargo: 1301-2000g


# ============================================================
# PRICING (in Rupiah)
# ============================================================
PRICE_REGULER = 6000
PRICE_EXPRESS = 12000
PRICE_KARGO = 5000


# ============================================================
# DIMENSION LIMITS (in cm)
# ============================================================
DIMENSION_MAX = 23  # Max untuk P, L, atau T
VOLUME_MAX = 12000  # Max volume dalam cm³


# ============================================================
# VOLUMETRIC CONSTANT
# ============================================================
IATA_DIVISOR = 6000  # cm³/kg (IATA standard)


# ============================================================
# GPIO PIN ASSIGNMENTS
# ============================================================
GPIO_RELAY = 17          # Motor DC control

GPIO_SERVO_1 = 18        # Servo 1 (Reguler)
GPIO_SERVO_2 = 19        # Servo 2 (Express)
GPIO_SERVO_3 = 20        # Servo 3 (Kargo)

GPIO_IR_1 = 5            # IR Sensor 1
GPIO_IR_2 = 6            # IR Sensor 2
GPIO_IR_3 = 12           # IR Sensor 3
GPIO_IR_4 = 13           # IR Sensor 4

GPIO_HX711_DT = 23       # HX711 Data
GPIO_HX711_SCK = 24      # HX711 Clock


# ============================================================
# SERVO ANGLES
# ============================================================
SERVO_ANGLE_REGULER = 45
SERVO_ANGLE_EXPRESS = 90
SERVO_ANGLE_KARGO = 135
SERVO_ANGLE_RESET = 90


# ============================================================
# WEB SERVER
# ============================================================
WEB_HOST = os.getenv("WEB_HOST", "0.0.0.0")
WEB_PORT = int(os.getenv("WEB_PORT", "5000"))
WEB_DEBUG = os.getenv("WEB_DEBUG", "true").lower() == "true"


# ============================================================
# FIREBASE (placeholder - akan diisi dengan credentials)
# ============================================================
FIREBASE_ENABLED = os.getenv("FIREBASE_ENABLED", "false").lower() == "true"
FIREBASE_CREDENTIALS_PATH = os.getenv("FIREBASE_CREDENTIALS", "config/firebase_credentials.json")
FIREBASE_DATABASE_URL = os.getenv("FIREBASE_DATABASE_URL", "")


# ============================================================
# PATHS
# ============================================================
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ASSETS_DIR = os.path.join(BASE_DIR, "assets")
TEST_IMAGES_DIR = os.path.join(ASSETS_DIR, "test_images")
OUTPUT_DIR = os.path.join(BASE_DIR, "output")
LABELS_DIR = os.path.join(OUTPUT_DIR, "labels")


# ============================================================
# HELPER FUNCTION
# ============================================================
def is_mock_mode() -> bool:
    """Check if running in mock mode"""
    return HARDWARE_MODE == HardwareMode.MOCK.value


def print_config():
    """Print current configuration"""
    print("\n" + "=" * 50)
    print("CONFIGURATION")
    print("=" * 50)
    print(f"Hardware Mode: {HARDWARE_MODE}")
    print(f"Web Server: {WEB_HOST}:{WEB_PORT}")
    print(f"Firebase Enabled: {FIREBASE_ENABLED}")
    print(f"Base Directory: {BASE_DIR}")
    print("=" * 50 + "\n")


if __name__ == "__main__":
    print_config()
