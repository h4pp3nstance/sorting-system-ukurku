"""
Unit Tests for web/measurement_engine.py (Opsi C in-process layer)
Hanya menguji bagian yang TIDAK butuh hardware (laptop-safe):
- map_session_result (pure mapping)
- measure_real / get_session graceful failure tanpa tahap14_session
"""

import pytest
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from web import measurement_engine as engine
from web.measurement_engine import (
    map_session_result,
    MeasurementEngineError,
    MeasurementUnavailableError,
)


class TestMapSessionResult:
    """map_session_result adalah pure function, fully testable di laptop."""

    def _valid_raw(self):
        return {
            'panjang_cm': 10.123,
            'lebar_cm': 8.456,
            'tinggi_cm': 5.0,
            'berat_aktual_g': 523.45,
            'berat_volumetrik_g': 120.0,
            'chargeable_weight_g': 523.45,
            'chargeable_source': 'actual',
            'measurement_id': 'integrated_20260531_120000_123456',
            'timestamp': '2026-05-31 12:00:00',
            'detection_image': 'hasil_tahap14/archive/detection_x.jpg',
        }

    def test_maps_all_fields(self):
        result = map_session_result(self._valid_raw())
        assert result['panjang'] == 10.12
        assert result['lebar'] == 8.46
        assert result['tinggi'] == 5.0
        assert result['berat_aktual'] == 523.5
        assert result['berat_volumetrik'] == 120.0
        assert result['chargeable_weight'] == 523.5
        assert result['chargeable_source'] == 'actual'
        assert result['measurement_id'] == 'integrated_20260531_120000_123456'
        assert result['timestamp'] == '2026-05-31 12:00:00'

    def test_rounds_dimensions_to_2dp(self):
        result = map_session_result(self._valid_raw())
        assert result['panjang'] == 10.12
        assert result['lebar'] == 8.46

    def test_rounds_weights_to_1dp(self):
        result = map_session_result(self._valid_raw())
        assert result['berat_aktual'] == 523.5

    def test_strips_leading_separator_from_image(self):
        raw = self._valid_raw()
        raw['detection_image'] = os.sep + 'abs/path/detection.jpg'
        result = map_session_result(raw)
        assert not result['detection_image'].startswith(os.sep)

    def test_missing_detection_image_ok(self):
        raw = self._valid_raw()
        del raw['detection_image']
        result = map_session_result(raw)
        assert result['detection_image'] == ''

    def test_default_chargeable_source_when_absent(self):
        raw = self._valid_raw()
        del raw['chargeable_source']
        result = map_session_result(raw)
        assert result['chargeable_source'] == 'unknown'

    def test_raises_on_missing_required_field(self):
        raw = self._valid_raw()
        del raw['chargeable_weight_g']
        with pytest.raises(MeasurementEngineError):
            map_session_result(raw)

    def test_raises_lists_missing_fields(self):
        raw = self._valid_raw()
        del raw['panjang_cm']
        del raw['tinggi_cm']
        with pytest.raises(MeasurementEngineError) as exc:
            map_session_result(raw)
        assert 'panjang_cm' in str(exc.value)
        assert 'tinggi_cm' in str(exc.value)


class TestMeasureRealLaptopSafe:
    """Di laptop, tahap14_session + hardware tidak ada -> graceful error."""

    def setup_method(self):
        engine.reset_session()

    def teardown_method(self):
        engine.reset_session()

    def test_get_session_raises_unavailable_without_base(self, monkeypatch):
        monkeypatch.setattr(engine, '_resolve_program_python_base', lambda: '')
        with pytest.raises(MeasurementUnavailableError):
            engine.get_session()

    def test_get_session_raises_unavailable_when_module_missing(self, monkeypatch):
        # base ada tapi tahap14_session tidak importable -> Unavailable
        monkeypatch.setattr(
            engine, '_resolve_program_python_base',
            lambda: os.path.dirname(os.path.abspath(__file__))
        )
        with pytest.raises(MeasurementUnavailableError):
            engine.get_session()

    def test_measure_real_propagates_unavailable(self, monkeypatch):
        monkeypatch.setattr(engine, '_resolve_program_python_base', lambda: '')
        with pytest.raises(MeasurementUnavailableError):
            engine.measure_real()
