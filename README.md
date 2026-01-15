# Sorting System - Package Measurement and Automatic Sorting

Sistem pengukuran volume dan berat paket serta penyortiran otomatis berbasis Raspberry Pi.

## 🚀 Quick Start

### 1. Setup Environment

```bash
# Navigate to project
cd sorting_system

# Create virtual environment
python3 -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

### 2. Run in Mock Mode

```bash
# Set environment (default is mock)
export HARDWARE_MODE=mock

# Run main program
python main.py
```

### 3. Run Tests

```bash
# Test classification logic
python -m core.classification

# Test measurement calculations
python -m core.measurement
```

## 📁 Project Structure

```
sorting_system/
├── config/           # Configuration
│   ├── settings.py   # App settings, GPIO pins, thresholds
│   └── __init__.py
├── hal/              # Hardware Abstraction Layer
│   ├── interfaces.py # Abstract interfaces
│   ├── mock/         # Mock implementations for testing
│   │   ├── mock_hx711.py
│   │   ├── mock_camera.py
│   │   ├── mock_gpio.py
│   │   └── mock_printer.py
│   └── real/         # Real hardware implementations (TODO)
├── core/             # Business logic
│   ├── classification.py  # Service type classification
│   └── measurement.py     # Volumetric calculation
├── main.py           # Application entry point
└── requirements.txt  # Python dependencies
```

## ⚙️ Configuration

Edit `config/settings.py` or use environment variables:

| Variable | Default | Description |
|----------|---------|-------------|
| `HARDWARE_MODE` | `mock` | `mock` or `real` |
| `WEB_HOST` | `0.0.0.0` | Web server host |
| `WEB_PORT` | `5000` | Web server port |
| `FIREBASE_ENABLED` | `false` | Enable Firebase |

## 📦 Classification Rules

| Service | Weight Range | Price |
|---------|--------------|-------|
| REGULER | ≤ 700g | Rp 6.000 |
| EXPRESS | 701-1300g | Rp 12.000 |
| KARGO | 1301-2000g | Rp 5.000 |

## 🔧 GPIO Mapping

| GPIO | Component |
|------|-----------|
| 17 | Relay (Motor DC) |
| 18, 19, 20 | Servos |
| 5, 6, 12, 13 | IR Sensors |
| 23, 24 | HX711 |
