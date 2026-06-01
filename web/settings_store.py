"""
Settings Store - konfigurasi runtime yang bisa diubah Admin.

Kelola config/app_settings.json:
- toleransi validasi (dimensi/berat aktual/berat tagihan) -> dipakai Dashboard MPC
- tarif layanan (REGULER/EXPRESS/KARGO)

Auto-seed default dari config/settings.py saat pertama jalan.
Pure functions (tanpa Flask/hardware) -> testable di laptop.
"""

import json
import os


_BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_SETTINGS_PATH = os.path.join(_BASE_DIR, "config", "app_settings.json")


def _default_settings():
    """Default settings, seed dari konstanta config/settings.py."""
    try:
        from config.settings import (
            PRICE_REGULER, PRICE_EXPRESS, PRICE_KARGO
        )
    except ImportError:
        PRICE_REGULER, PRICE_EXPRESS, PRICE_KARGO = 6000, 12000, 5000

    return {
        "toleransi": {
            "dimensi_cm": 1.0,
            "berat_aktual_g": 50.0,
            "berat_tagihan_g": 100.0,
        },
        "tarif": {
            "REGULER": int(PRICE_REGULER),
            "EXPRESS": int(PRICE_EXPRESS),
            "KARGO": int(PRICE_KARGO),
        },
    }


def _seed_settings_file(path):
    data = _default_settings()
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    return data


def _merge_defaults(loaded):
    """Pastikan semua key default ada walau file lama belum lengkap."""
    defaults = _default_settings()
    result = {}
    for section, default_section in defaults.items():
        merged = dict(default_section)
        loaded_section = loaded.get(section, {})
        if isinstance(loaded_section, dict):
            for key in default_section:
                if key in loaded_section:
                    merged[key] = loaded_section[key]
        result[section] = merged
    return result


def load_settings():
    """Load settings, seed default jika belum ada / rusak."""
    if not os.path.exists(_SETTINGS_PATH):
        return _seed_settings_file(_SETTINGS_PATH)
    try:
        with open(_SETTINGS_PATH, "r", encoding="utf-8") as f:
            loaded = json.load(f)
        if not isinstance(loaded, dict) or not loaded:
            return _seed_settings_file(_SETTINGS_PATH)
        return _merge_defaults(loaded)
    except (json.JSONDecodeError, OSError):
        return _seed_settings_file(_SETTINGS_PATH)


def save_settings(settings):
    """Tulis settings utuh ke disk (setelah merge default)."""
    merged = _merge_defaults(settings if isinstance(settings, dict) else {})
    os.makedirs(os.path.dirname(_SETTINGS_PATH), exist_ok=True)
    with open(_SETTINGS_PATH, "w", encoding="utf-8") as f:
        json.dump(merged, f, indent=2, ensure_ascii=False)
    return merged


def _coerce_number(value, fallback):
    try:
        return float(value)
    except (TypeError, ValueError):
        return fallback


def update_tolerances(dimensi_cm=None, berat_aktual_g=None, berat_tagihan_g=None):
    """Update sebagian/seluruh toleransi; nilai None tidak diubah."""
    settings = load_settings()
    tol = settings["toleransi"]
    if dimensi_cm is not None:
        tol["dimensi_cm"] = _coerce_number(dimensi_cm, tol["dimensi_cm"])
    if berat_aktual_g is not None:
        tol["berat_aktual_g"] = _coerce_number(berat_aktual_g, tol["berat_aktual_g"])
    if berat_tagihan_g is not None:
        tol["berat_tagihan_g"] = _coerce_number(berat_tagihan_g, tol["berat_tagihan_g"])
    return save_settings(settings)


def update_tariffs(reguler=None, express=None, kargo=None):
    """Update sebagian/seluruh tarif; nilai None tidak diubah."""
    settings = load_settings()
    tarif = settings["tarif"]
    if reguler is not None:
        tarif["REGULER"] = int(_coerce_number(reguler, tarif["REGULER"]))
    if express is not None:
        tarif["EXPRESS"] = int(_coerce_number(express, tarif["EXPRESS"]))
    if kargo is not None:
        tarif["KARGO"] = int(_coerce_number(kargo, tarif["KARGO"]))
    return save_settings(settings)


def get_tolerances():
    return load_settings()["toleransi"]


def get_tariffs():
    return load_settings()["tarif"]
