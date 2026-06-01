"""
Application Configuration
"""

import os
from enum import Enum


BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


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
# MEASUREMENT SOURCE (File-based Integration Bridge)
# ============================================================

def _find_program_python_base():
    """
    Auto-detect program-python base directory.
    Priority:
    1. Environment variable PROGRAM_PYTHON_BASE
    2. Sibling folder ../program-python
    3. $HOME/program-python
    4. Empty string (not found)
    """
    # 1. Check environment variable
    env_path = os.getenv("PROGRAM_PYTHON_BASE", "").strip()
    if env_path:
        return os.path.abspath(os.path.expanduser(env_path))
    
    # 2. Check sibling folder
    sibling_path = os.path.abspath(os.path.join(BASE_DIR, "..", "program-python"))
    if os.path.isdir(sibling_path):
        return sibling_path
    
    # 3. Check home directory
    home_path = os.path.join(os.path.expanduser("~"), "program-python")
    if os.path.isdir(home_path):
        return home_path
    
    # 4. Not found
    return ""


# Base path program-python untuk resolve relative image paths
PROGRAM_PYTHON_BASE = _find_program_python_base()

# Path ke file JSON hasil pengukuran dari program-python (tahap14)
# Set via environment variable atau gunakan default path
_measurement_source_env = os.getenv("MEASUREMENT_SOURCE_PATH", "").strip()
if _measurement_source_env:
    MEASUREMENT_SOURCE_PATH = os.path.abspath(os.path.expanduser(_measurement_source_env))
elif PROGRAM_PYTHON_BASE:
    MEASUREMENT_SOURCE_PATH = os.path.join(
        PROGRAM_PYTHON_BASE,
        "hasil_tahap14",
        "latest_integrated_chargeable.json",
    )
else:
    MEASUREMENT_SOURCE_PATH = ""

# Mode pengukuran: "mock" = data acak, "file" = baca dari JSON tahap14
# Jika HARDWARE_MODE=real dan MEASUREMENT_MODE tidak di-set, default ke "file"
MEASUREMENT_MODE = os.getenv("MEASUREMENT_MODE", "auto")

# Batas umur data (detik) - jika file lebih tua dari ini, dianggap stale
MEASUREMENT_MAX_AGE_SECONDS = int(os.getenv("MEASUREMENT_MAX_AGE_SECONDS", "300"))


# ============================================================
# PATHS
# ============================================================
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
    print(f"Base Directory: {BASE_DIR}")
    print("=" * 50 + "\n")


if __name__ == "__main__":
    print_config()
