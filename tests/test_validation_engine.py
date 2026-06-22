"""
Unit Tests for web/validation_engine.py (Fitur C - validasi Mitra vs MPC)
Laptop-safe: pure function, no hardware.
"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from web.validation_engine import (
    compare_measurements,
    extract_measurement,
    normalize_dimensions,
    is_package_present,
    STATUS_VALID,
    STATUS_PERLU_REVIEW,
    STATUS_TIDAK_SESUAI,
)

_TOL = {"dimensi_cm": 1.0, "berat_aktual_g": 50.0, "berat_tagihan_g": 100.0}


def _m(panjang=10, lebar=10, tinggi=10, berat_aktual=500,
       berat_volumetrik=200, chargeable_weight=500):
    return {
        "panjang": panjang, "lebar": lebar, "tinggi": tinggi,
        "berat_aktual": berat_aktual, "berat_volumetrik": berat_volumetrik,
        "chargeable_weight": chargeable_weight,
    }


class TestCompareMeasurements:
    def test_identical_is_valid(self):
        r = compare_measurements(_m(), _m(), _TOL)
        assert r["status"] == STATUS_VALID
        assert r["breaches"] == []

    def test_within_tolerance_is_valid(self):
        mitra = _m(panjang=10.0, berat_aktual=500, chargeable_weight=500)
        mpc = _m(panjang=10.8, berat_aktual=540, chargeable_weight=560)
        r = compare_measurements(mitra, mpc, _TOL)
        assert r["status"] == STATUS_VALID

    def test_dimension_breach_is_perlu_review(self):
        mitra = _m(panjang=10)
        mpc = _m(panjang=12)  # selisih 2 > 1cm, tapi chargeable sama
        r = compare_measurements(mitra, mpc, _TOL)
        assert r["status"] == STATUS_PERLU_REVIEW
        assert "panjang" in r["breaches"]

    def test_actual_weight_breach_is_perlu_review(self):
        mitra = _m(berat_aktual=500)
        mpc = _m(berat_aktual=600)  # selisih 100 > 50g, chargeable sama
        r = compare_measurements(mitra, mpc, _TOL)
        assert r["status"] == STATUS_PERLU_REVIEW
        assert "berat_aktual" in r["breaches"]

    def test_chargeable_breach_is_tidak_sesuai(self):
        mitra = _m(chargeable_weight=500)
        mpc = _m(chargeable_weight=700)  # selisih 200 > 100g
        r = compare_measurements(mitra, mpc, _TOL)
        assert r["status"] == STATUS_TIDAK_SESUAI
        assert "chargeable_weight" in r["breaches"]

    def test_chargeable_breach_overrides_dimension(self):
        # Both dimension AND chargeable breach -> tidak_sesuai wins
        mitra = _m(panjang=10, chargeable_weight=500)
        mpc = _m(panjang=15, chargeable_weight=800)
        r = compare_measurements(mitra, mpc, _TOL)
        assert r["status"] == STATUS_TIDAK_SESUAI

    def test_selisih_computed(self):
        r = compare_measurements(_m(panjang=10), _m(panjang=11.5), _TOL)
        assert r["selisih"]["panjang"] == 1.5

    def test_boundary_exactly_at_tolerance_is_valid(self):
        # diff == tolerance is NOT a breach (uses > not >=)
        mitra = _m(panjang=10)
        mpc = _m(panjang=11)  # diff exactly 1.0 == tol
        r = compare_measurements(mitra, mpc, _TOL)
        assert r["status"] == STATUS_VALID

    def test_handles_missing_fields(self):
        r = compare_measurements({}, {}, _TOL)
        assert r["status"] == STATUS_VALID

    def test_handles_none_tolerances_uses_defaults(self):
        r = compare_measurements(_m(), _m(), None)
        assert r["status"] == STATUS_VALID
        assert r["tolerances_used"]["dimensi_cm"] == 1.0


class TestExtractMeasurement:
    def test_extracts_from_envelope(self):
        package = {
            "dimensions": {"panjang": 10.1, "lebar": 8.2, "tinggi": 5.0},
            "weight": {"aktual": 500, "volumetrik": 200, "chargeable": 500},
        }
        m = extract_measurement(package)
        assert m["panjang"] == 10.1
        assert m["berat_aktual"] == 500
        assert m["chargeable_weight"] == 500

    def test_handles_empty_package(self):
        m = extract_measurement({})
        assert m["panjang"] == 0.0
        assert m["chargeable_weight"] == 0.0


class TestNormalizeDimensions:
    def test_sorted_descending(self):
        m = normalize_dimensions(_m(panjang=5, lebar=20, tinggi=10))
        assert m["panjang"] == 20
        assert m["lebar"] == 10
        assert m["tinggi"] == 5

    def test_other_fields_unchanged(self):
        m = normalize_dimensions(_m(panjang=5, lebar=20, tinggi=10, berat_aktual=750,
                                    berat_volumetrik=300, chargeable_weight=750))
        assert m["berat_aktual"] == 750
        assert m["berat_volumetrik"] == 300
        assert m["chargeable_weight"] == 750

    def test_already_sorted_unchanged(self):
        m = normalize_dimensions(_m(panjang=30, lebar=20, tinggi=10))
        assert (m["panjang"], m["lebar"], m["tinggi"]) == (30, 20, 10)

    def test_returns_copy_not_mutate(self):
        original = _m(panjang=5, lebar=20, tinggi=10)
        normalize_dimensions(original)
        assert original["panjang"] == 5

    def test_orientasi_tertukar_normalize_true_is_valid(self):
        mitra = _m(panjang=30, lebar=20, tinggi=10)
        mpc = _m(panjang=20, lebar=10, tinggi=30)
        r = compare_measurements(mitra, mpc, _TOL, normalize_orientation=True)
        assert r["status"] == STATUS_VALID
        assert r["breaches"] == []

    def test_orientasi_tertukar_normalize_false_is_breach(self):
        mitra = _m(panjang=30, lebar=20, tinggi=10)
        mpc = _m(panjang=20, lebar=10, tinggi=30)
        r = compare_measurements(mitra, mpc, _TOL, normalize_orientation=False)
        assert r["status"] != STATUS_VALID
        assert len(r["breaches"]) > 0


class TestIsPackagePresent:
    def test_normal_package_returns_true(self):
        assert is_package_present(_m(panjang=20, lebar=15, tinggi=10, berat_aktual=500)) is True

    def test_empty_tool_no_weight_returns_false(self):
        assert is_package_present(_m(berat_aktual=0)) is False

    def test_below_min_weight_returns_false(self):
        assert is_package_present(_m(berat_aktual=5)) is False

    def test_exactly_at_min_weight_returns_true(self):
        assert is_package_present(_m(berat_aktual=10.0), min_weight_g=10.0) is True

    def test_dimension_too_small_returns_false(self):
        assert is_package_present(_m(panjang=0.1, berat_aktual=500)) is False

    def test_custom_thresholds(self):
        assert is_package_present(_m(berat_aktual=8, panjang=1), min_weight_g=5.0, min_dim_cm=0.5) is True
        assert is_package_present(_m(berat_aktual=4, panjang=1), min_weight_g=5.0, min_dim_cm=0.5) is False

    def test_none_measurement_returns_false(self):
        assert is_package_present(None) is False

    def test_empty_dict_returns_false(self):
        assert is_package_present({}) is False
