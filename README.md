# 📦 Sorting System - UkurKu

[![Open in GitHub Codespaces](https://github.com/codespaces/badge.svg)](https://codespaces.new/h4pp3nstance/sorting-system-ukurku)
[![Python Tests](https://img.shields.io/badge/tests-211%20passed-brightgreen)](tests/)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

Smart IoT Package Sorting System with **Firebase Integration** - Raspberry Pi based weight and dimension measurement.

> 🎯 **Sistem pengukuran volume dan berat paket serta penyortiran otomatis** berbasis Raspberry Pi dengan dashboard real-time.

## 🚀 Quick Start

### Option 1: GitHub Codespaces (Recommended for Demo)

1. Click the **"Open in GitHub Codespaces"** badge above
2. Wait for environment setup (~2 minutes)
3. Run the dashboard:
   ```bash
   python run_web.py
   ```
4. Open the forwarded port (5000) to see the dashboard

### Option 2: Local Development

```bash
# Navigate to project
cd sorting_system

# Create virtual environment
python3 -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Run web dashboard
python run_web.py
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
# Run all 211 tests
python -m pytest tests/ -v

# Test specific module
python -m pytest tests/test_api.py -v
```

## ✨ Features

- **📊 Real-time Dashboard** - Carbon Design System UI with live updates (SSE)
- **⚖️ Weight Measurement** - HX711 load cell integration
- **📐 Dimension Detection** - Camera-based volume calculation
- **🔥 Firebase Sync** - Cloud database for history & analytics
- **📝 Logging System** - Rotating file logs with Firebase sync
- **🧪 Comprehensive Tests** - 211 unit & integration tests

## 📁 Project Structure

```
sorting_system/
├── .devcontainer/    # GitHub Codespaces configuration
├── config/           # Configuration
│   ├── settings.py   # App settings, GPIO pins, thresholds
│   └── firebase_rules.json  # Firebase database rules
├── core/             # Business logic
│   ├── classification.py  # Service type classification
│   ├── measurement.py     # Volumetric calculation
│   └── logger.py          # Logging system
├── hal/              # Hardware Abstraction Layer
│   ├── interfaces.py # Abstract interfaces
│   ├── mock/         # Mock implementations for testing
│   │   ├── mock_hx711.py
│   │   ├── mock_camera.py
│   │   ├── mock_gpio.py
│   │   └── mock_printer.py
│   └── real/         # Real hardware implementations
├── storage/          # Data persistence
│   └── firebase_handler.py  # Firebase CRUD operations
├── web/              # Flask web application
│   ├── app.py        # Flask app factory
│   ├── routes.py     # API endpoints
│   └── templates/    # Jinja2 HTML templates
├── tests/            # Unit & integration tests (211 tests)
├── docs/             # Documentation
├── main.py           # Application entry point
├── run_web.py        # Web server runner
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

## 🛠️ Tech Stack

- **Backend**: Python 3.11+, Flask 3.0
- **Frontend**: Carbon Design System (IBM)
- **Database**: Firebase Realtime Database
- **Hardware**: Raspberry Pi 4B, HX711, Servo, IR Sensors
- **Testing**: pytest (211 tests)

## 📖 Documentation

- [Progress Report](docs/PROGRESS_REPORT.md)
- [Logging Architecture](docs/LOGGING_ARCHITECTURE.md)
- [Firebase Optimization](docs/firebase_optimization.md)

## 📜 License

MIT License - See [LICENSE](LICENSE) for details.
