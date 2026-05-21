"""
Tests for file-based measurement bridge.
"""

import json
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from web.measurement_bridge import (  # noqa: E402
    MeasurementBridgeError,
    get_measurement_from_file,
    should_use_file_bridge,
)


def write_measurement(path):
    data = {
        "panjang_cm": 10.123,
        "lebar_cm": 8.456,
        "tinggi_cm": 4.789,
        "berat_aktual_g": 500.12,
        "berat_volumetrik_g": 67.89,
        "chargeable_weight_g": 500.12,
        "chargeable_source": "actual",
        "measurement_id": "integrated_test_001",
        "timestamp": "2026-05-21 09:00:00",
        "detection_image": "hasil_tahap14/archive/detection_test.jpg",
    }
    path.write_text(json.dumps(data), encoding="utf-8")
    return data


def test_bridge_maps_tahap14_json_to_ui_format(tmp_path):
    source = tmp_path / "latest_integrated_chargeable.json"
    write_measurement(source)

    result = get_measurement_from_file(str(source), "/program-python", 999999)

    assert result.panjang == 10.12
    assert result.lebar == 8.46
    assert result.tinggi == 4.79
    assert result.berat_aktual == 500.1
    assert result.berat_volumetrik == 67.9
    assert result.chargeable_weight == 500.1
    assert result.chargeable_source == "actual"
    assert result.measurement_id == "integrated_test_001"
    assert result.detection_image == "hasil_tahap14/archive/detection_test.jpg"


def test_bridge_reports_missing_file_in_indonesian(tmp_path):
    missing = tmp_path / "missing.json"

    with pytest.raises(MeasurementBridgeError) as error:
        get_measurement_from_file(str(missing), "", 999999)

    assert "File pengukuran tidak ditemukan" in str(error.value)


def test_bridge_rejects_package_below_minimum_weight(tmp_path):
    source = tmp_path / "latest_integrated_chargeable.json"
    data = write_measurement(source)
    data["berat_aktual_g"] = 0
    data["tinggi_cm"] = 0
    source.write_text(json.dumps(data), encoding="utf-8")

    with pytest.raises(MeasurementBridgeError) as error:
        get_measurement_from_file(str(source), "", 999999)

    assert "Paket belum terbaca" in str(error.value)


def test_bridge_mode_selection():
    assert should_use_file_bridge("mock", "file") is True
    assert should_use_file_bridge("real", "mock") is False
    assert should_use_file_bridge("real", "auto") is True
    assert should_use_file_bridge("mock", "auto") is False
