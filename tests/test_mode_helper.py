"""
Tests for web.mode_helper.get_system_mode_info().

Strategy: monkeypatch module-level constants HARDWARE_MODE / MEASUREMENT_MODE
on the imported web.mode_helper module, since config is read once at import.
"""
import pytest

from web import mode_helper


@pytest.fixture
def reset_mode_module(monkeypatch):
    yield monkeypatch


def test_file_bridge_branch_when_measurement_mode_file(reset_mode_module):
    reset_mode_module.setattr(mode_helper, "HARDWARE_MODE", "mock")
    reset_mode_module.setattr(mode_helper, "MEASUREMENT_MODE", "file")

    info = mode_helper.get_system_mode_info()

    assert info["mode_id"] == "file"
    assert info["label"] == "Mesin Ukur"
    assert info["description"] == "Data dari alat ukur"
    assert info["dot_class"] == "status-dot--active"


def test_file_bridge_branch_when_real_and_auto(reset_mode_module):
    reset_mode_module.setattr(mode_helper, "HARDWARE_MODE", "real")
    reset_mode_module.setattr(mode_helper, "MEASUREMENT_MODE", "auto")

    info = mode_helper.get_system_mode_info()

    assert info["mode_id"] == "file"
    assert info["dot_class"] == "status-dot--active"


def test_mock_branch_when_hardware_mock_and_measurement_mock(reset_mode_module):
    reset_mode_module.setattr(mode_helper, "HARDWARE_MODE", "mock")
    reset_mode_module.setattr(mode_helper, "MEASUREMENT_MODE", "mock")

    info = mode_helper.get_system_mode_info()

    assert info["mode_id"] == "mock"
    assert info["label"] == "Demo"
    assert info["description"] == "Data simulasi untuk demo"
    assert info["dot_class"] == "status-dot--warning"


def test_mock_branch_when_hardware_mock_and_auto(reset_mode_module):
    reset_mode_module.setattr(mode_helper, "HARDWARE_MODE", "mock")
    reset_mode_module.setattr(mode_helper, "MEASUREMENT_MODE", "auto")

    info = mode_helper.get_system_mode_info()

    assert info["mode_id"] == "mock"
    assert info["label"] == "Demo"


def test_unknown_branch_when_hardware_real_and_mock(reset_mode_module):
    reset_mode_module.setattr(mode_helper, "HARDWARE_MODE", "real")
    reset_mode_module.setattr(mode_helper, "MEASUREMENT_MODE", "mock")

    info = mode_helper.get_system_mode_info()

    assert info["mode_id"] == "unknown"
    assert info["label"] == "Tidak Diketahui"
    assert info["description"] == "Konfigurasi tidak dikenali"
    assert info["dot_class"] == "status-dot--error"


def test_returned_keys_are_complete():
    info = mode_helper.get_system_mode_info()

    assert set(info.keys()) == {"mode_id", "label", "description", "dot_class"}
